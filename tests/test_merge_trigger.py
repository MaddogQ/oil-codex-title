"""PR 合并报告触发回归；所有案例合成，模型调用使用替身。"""
import unittest
from unittest.mock import Mock

import test_title as fixtures
from test_title import TURN, NEW_TURN, proposal
import oil_codex_title as title


class MergeTriggerTests(unittest.TestCase):
    setUp = fixtures.TitleTests.setUp
    tearDown = fixtures.TitleTests.tearDown
    process = fixtures.TitleTests.process
    def set_report(self, request, report):
        items = self.backend.thread['turns'][0]['items']
        items[0]['content'][0]['text'] = request
        items[1]['text'] = report

    def test_merge_reports_trigger_for_both_requests_and_deduplicate(self):
        for request in ('直接合并然后收尾吧', '验收通过，合入并收尾吧'):
            with self.subTest(request=request):
                self.set_report(request, 'PR #42 已合入 `main`。Remaining: None.')
                model = Mock(side_effect=proposal)
                result = self.process(model, apply=True, event_turn=TURN, stop_only=True)
                self.assertEqual(result['status'], 'renamed')
                self.assertEqual(result['completion_status'], 'active')
                self.assertEqual(self.process(model, apply=True, session_end=True)['status'], 'unchanged')
                self.assertEqual(model.call_count, 1)
                # 下一个独立案例重新建立状态。
                self.tearDown()
                self.setUp()

    def test_non_merge_reports_do_not_trigger(self):
        for report in ('准备把 PR 合入 main', 'PR 自动合并已启用，等待检查',
                       'PR 合入 main 失败', 'PR #42 已合入 develop',
                       '任务已经完成', '示例：PR #42 已合入 main',
                       '> PR #42 已合入 main', 'PR #42 尚未合入 main',
                       'PR #42 已合入 main-backup', 'PR #42 已合入 main/preview',
                       'PR #42 已合入 main.backup'):
            with self.subTest(report=report):
                self.set_report('验收通过，合入并收尾吧', report)
                self.assertEqual(self.process(lambda _: self.fail('不应调用模型'),
                    apply=True, event_turn=TURN, stop_only=True)['status'], 'awaiting_session_end')

    def test_old_report_and_commentary_do_not_trigger(self):
        self.set_report('合并吧', 'PR #42 已合入 main')
        self.backend.thread['turns'][0]['items'][1]['phase'] = 'commentary'
        self.assertEqual(self.process(lambda _: self.fail(), event_turn=TURN,
            stop_only=True)['status'], 'awaiting_session_end')
        self.backend.thread['turns'].append({'id': NEW_TURN, 'status': 'completed', 'items': [
            {'type': 'userMessage', 'content': [{'type': 'text', 'text': '继续修复布局'}]},
            {'type': 'agentMessage', 'phase': 'final_answer', 'text': '已修复布局'}]})
        self.assertEqual(self.process(lambda _: self.fail(), event_turn=NEW_TURN,
            stop_only=True)['status'], 'awaiting_session_end')

    def test_truncated_final_cannot_complete(self):
        self.set_report('合入并收尾吧', 'PR #42 已合入 main。' + '验证通过。' * 110 + '仍需部署验收。')
        def completed(context):
            self.assertFalse(context['completion_context_complete'])
            candidate, usage = proposal(context)
            return {**candidate, 'status': 'completed'}, usage
        result = self.process(completed, apply=True, event_turn=TURN, stop_only=True)
        self.assertEqual(result['completion_status'], 'active')

    def test_success_report_with_remaining_work_only_triggers_evaluation(self):
        self.set_report('合入 main 后继续部署', 'PR #42 已合入 main，但部署失败，仍需修复。')
        model = Mock(side_effect=proposal)
        result = self.process(model, apply=True, event_turn=TURN, stop_only=True)
        self.assertEqual(result['completion_status'], 'active')
        self.assertEqual(model.call_count, 1)

    def test_formatted_and_english_reports(self):
        for report in ('### Done\n\n[PR #42](https://example.com/pr/42) 已合入 `main`。',
                       'PR #42 已合并，当前 main 已同步。',
                       '已将 PR #42 合入 main。', 'PR #42 has been merged into main.'):
            with self.subTest(report=report):
                self.set_report('合并并收尾', report)
                self.assertTrue(title.reports_main_merge(self.backend.thread['turns'][0]))

    def test_model_can_mark_success_completed(self):
        self.set_report('验收通过，合入并收尾吧', 'PR #42 已合入 main。无剩余工作。')
        def completed(context):
            candidate, usage = proposal(context)
            return {**candidate, 'status': 'completed'}, usage
        result = self.process(completed, apply=True, event_turn=TURN, stop_only=True)
        self.assertEqual(result['completion_status'], 'completed')
        self.assertTrue(self.backend.thread['name'].startswith('✓ '))

    def test_explicit_user_closure_survives_long_assistant_report(self):
        self.set_report('验收通过，收尾吧', '实现说明。' * 120)
        result = self.process(apply=True, event_turn=TURN, stop_only=True)
        self.assertEqual(result['completion_status'], 'completed')

    def test_old_long_report_does_not_veto_latest_delivery(self):
        self.set_report('请修复布局', '实现说明。' * 120)
        self.backend.thread['turns'].append({'id': NEW_TURN, 'status': 'completed', 'items': [
            {'type': 'userMessage', 'content': [{'type': 'text', 'text': '合入并收尾吧'}]},
            {'type': 'agentMessage', 'phase': 'final_answer', 'text': 'PR #42 已合入 main。'}]})
        context = title.snapshot(self.backend.thread, self.config)['context']
        self.assertTrue(context['completion_context_complete'])
