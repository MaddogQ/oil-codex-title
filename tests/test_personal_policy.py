"""确定性元数据、完成状态写入和保护边界；语义评测见合成 fixtures。"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import oil_codex_title as title
import codex_adapter as adapter
import test_title as fixtures

CANONICAL = '[分析] Codex｜Luna 后台调用'


def candidate(status='active', action='keep', text=CANONICAL):
    return {'action': action, 'title': text, 'status': status, 'reason': '合成案例'}, {}


@contextmanager
def los_angeles():
    # POSIX 使用系统时区规则；Windows 以实际本机 Pacific 时区运行，其他时区跳过。
    if hasattr(time, 'tzset'):
        try:
            with patch.dict(os.environ, {'TZ': 'America/Los_Angeles'}):
                time.tzset()
                yield
        finally:
            time.tzset()
    else:
        offsets = [datetime(2026, month, 4, tzinfo=timezone.utc).astimezone().utcoffset()
                   for month in (1, 9)]
        if offsets != [timedelta(hours=-8), timedelta(hours=-7)]:
            raise unittest.SkipTest('本机非 Pacific 时区；跨平台 CI 在 POSIX 使用 TZ')
        yield


class DateTests(unittest.TestCase):
    def test_utc_offset_epoch_and_updated_at(self):
        with los_angeles():
            for stamp in ('2026-09-05T05:30:00Z', '2026-09-04T22:30:00-07:00',
                          datetime(2026, 9, 5, 5, 30, tzinfo=timezone.utc).timestamp()):
                with self.subTest(stamp=stamp):
                    self.assertEqual(title.created_date({'createdAt': stamp, 'updatedAt': 1900000000}), '260904')

    def test_historical_dst_not_current_fixed_offset(self):
        with los_angeles():
            for stamp, expected in (
                ('2026-01-05T07:30:00Z', '260104'),
                ('2026-09-05T07:30:00Z', '260905'),
                ('2026-03-08T09:59:00Z', '260308'),
                ('2026-03-08T10:01:00Z', '260308'),
                ('2026-11-01T08:59:00Z', '261101'),
                ('2026-11-01T09:01:00Z', '261101'),
            ):
                with self.subTest(stamp=stamp):
                    self.assertEqual(title.created_date({'createdAt': stamp}), expected)

    def test_missing_invalid_naive_and_boolean_metadata_rejected(self):
        for stamp in (None, True, False, '', '2026-09-04', '2026-09-04T22:30:00',
                      'bad', [], {}, float('inf'), float('nan'), 10**100):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                title.created_date({'createdAt': stamp, 'updatedAt': 1788586200})

    def test_adapter_passes_real_metadata_without_replacing_created_at(self):
        backend = adapter.CodexBackend('unused')
        data = {'createdAt': 1788586200, 'updatedAt': 1900000000, 'turns': []}
        backend.call = Mock(return_value={'thread': data})
        self.assertIs(backend.read(fixtures.ID), data)
        backend.call.assert_called_once_with('thread/read', {'threadId': fixtures.ID, 'includeTurns': True})


class ValidationTests(unittest.TestCase):
    def test_nine_categories_and_exact_display_structure(self):
        self.assertEqual(len(title.CATEGORIES), 9)
        for category in title.CATEGORIES:
            text = f'[{category}] Codex｜标题规则'
            for status, prefix in (('active', ''), ('completed', '✓ ')):
                result = title.display_title(text, '260904', status)
                self.assertEqual(result, prefix + '260904 ' + text)
                self.assertEqual(result.count('｜'), 1)
                self.assertEqual(result.count('✓'), int(status == 'completed'))

    def test_rejects_model_dates_marks_categories_and_sensitive_content(self):
        for text in ('[测试] Codex｜规则', '260904 ' + CANONICAL, '✓ ' + CANONICAL,
                     '✓ ✓ ' + CANONICAL, '[分析] Codex｜260904', '[分析] Codex｜2026-09-04',
                     '[分析] Codex｜9月4日', '[分析] Codex｜✓ 已完', '[分析] Codex｜🎬 规则',
                     '[分析] Codex｜规则｜测试', '[分析] Codex|规则', '[分析] ｜规则',
                     '[分析] Codex｜', '[分析] Codex ｜规则', '[分析] Codex｜\u202e规则',
                     '[分析] /home/private｜规则', r'[分析] C:\private\app｜规则',
                     '[分析] a@b.com｜规则', '[分析] sk-secret｜规则'):
            for action in ('rename', 'keep'):
                with self.subTest(text=text, action=action), self.assertRaises(ValueError):
                    title.validate_candidate(candidate(action=action, text=text)[0], CANONICAL)

    def test_length_reserves_completed_prefix(self):
        text = '[分析] ' + 'a' * 32 + '｜b'
        self.assertEqual(len(text), 39)
        self.assertEqual(len(title.display_title(text, '260904', 'completed')), 48)
        self.assertEqual(len(title.display_title(text, '260904', 'active')), 46)
        with self.assertRaises(ValueError):
            title.display_title(text + 'c', '260904', 'active')

    def test_missing_or_invalid_completion_field_rejected(self):
        for value in (None, 'done', True, [], {}):
            data = candidate()[0]
            data['status'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                title.validate_candidate(data, '')
        data.pop('status')
        with self.assertRaises(ValueError):
            title.validate_candidate(data, '')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.backend = fixtures.FakeBackend()
        self.backend.thread['createdAt'] = '2026-09-04T12:00:00Z'
        self.config = title.DEFAULTS.copy()

    def tearDown(self):
        self.tmp.cleanup()

    def process(self, model=None, **kwargs):
        return title.process_thread(self.backend, model or (lambda _: candidate(action='rename')),
                                    fixtures.ID, self.root, self.config, apply=True, **kwargs)

    def state(self):
        return title.read_json(title.state_path(self.root, fixtures.ID))

    def append(self, text, assistant='本轮结束'):
        self.backend.thread['turns'].append({'id': str(len(self.backend.thread['turns'])),
            'status': 'completed', 'items': [
                {'type': 'userMessage', 'content': [{'type': 'text', 'text': text}]},
                {'type': 'agentMessage', 'phase': 'final_answer', 'text': assistant}]})

    def test_new_thread_and_completion_only_roundtrip_stable_date(self):
        self.process()
        date = title.created_date(self.backend.thread)
        self.assertEqual(self.backend.thread['name'], date + ' ' + CANONICAL)
        self.append('验收通过，收尾吧')
        done = self.process(lambda _: candidate('completed'))
        self.assertEqual(done['status'], 'renamed')
        self.assertEqual(done['action'], 'keep')
        self.assertEqual(done['completion_status'], 'completed')
        self.assertEqual(done['title'], '✓ ' + date + ' ' + CANONICAL)
        self.backend.thread['updatedAt'] = 1900000000
        self.append('现在增加边界测试')
        active = self.process(lambda _: candidate('active'))
        self.assertEqual(active['status'], 'renamed')
        self.assertEqual(active['title'], date + ' ' + CANONICAL)
        self.assertEqual(self.state()['created_date'], date)
        self.assertEqual(self.state()['completion_status'], 'active')
        self.assertEqual(self.state()['canonical_title'], CANONICAL)
        self.assertEqual(self.state()['display_title'], active['title'])
        self.assertEqual(len(self.backend.writes), 3)
        self.assertFalse(self.backend.archived)

    def test_updated_at_only_does_not_trigger_model(self):
        self.process()
        self.backend.thread['updatedAt'] = 1900000000
        self.assertEqual(self.process(lambda _: self.fail('updatedAt 不是命名证据'))['status'], 'unchanged')

    def test_completion_phrases_reach_model_and_state_writer(self):
        # 这是输入路由/持久化测试，不以 mock 声称验证模型语义；另有 --live fixtures。
        for phrase in ('可以了，谢谢', '确认了，可以不用追踪了', '验收通过，收尾吧',
                       '验收没问题，可以收尾', '这个通过了，结束吧', '可以收尾了',
                       '谢谢', 'thanks', 'thank you'):
            with self.subTest(phrase=phrase):
                self.backend = fixtures.FakeBackend()
                title.state_path(self.root, fixtures.ID).unlink(missing_ok=True)
                self.process()
                self.append(phrase)
                model = Mock(return_value=candidate('completed'))
                result = self.process(model)
                model.assert_called_once()
                self.assertEqual(result['completion_status'], 'completed')
                self.assertEqual(result['title'].count('✓'), 1)

    def test_substantive_followups_reach_model_and_stay_active(self):
        self.process()
        for text in ('这个功能验收通过，接下来处理另一个问题', '好的，下一步看登录页',
                     '这个改好了，现在修复注册', '为登录模块增加实现'):
            self.append(text)
            model = Mock(return_value=candidate('active'))
            result = self.process(model)
            model.assert_called_once()
            self.assertEqual(result['completion_status'], 'active')
            self.assertFalse(result['title'].startswith('✓'))

    def test_completed_continue_and_substantive_requests_cannot_skip(self):
        for text in ('继续', '可以，继续', 'continue', '实现一个新功能'):
            self.process()
            self.append('验收通过，收尾吧')
            self.process(lambda _: candidate('completed'))
            self.append(text)
            model = Mock(return_value=candidate('active'))
            self.assertEqual(self.process(model)['status'], 'renamed')
            model.assert_called_once()

    def test_active_plain_confirmation_preserves_optimization(self):
        self.process()
        for text in ('可以，继续', '继续'):
            self.append(text)
            result = self.process(lambda _: self.fail('纯继续可跳过'))
            self.assertEqual(result['skip_reason'], 'confirmation_only')
            self.assertEqual(result['completion_status'], 'active')

    def test_truncated_or_partial_context_cannot_complete(self):
        self.process()
        for partial in (False, True):
            self.append('验收通过，收尾吧' if partial else '验收通过，收尾吧。' + '说明。' * 500 + '现在处理登录页')
            if partial:
                self.backend.thread['turns'][-1]['itemsView'] = 'summary'
            result = self.process(lambda _: candidate('completed'))
            self.assertEqual(result['completion_status'], 'active')
            self.assertFalse(result['title'].startswith('✓'))

    def test_short_confirmation_cannot_hide_prior_truncated_pending_work(self):
        self.process()
        self.append('验收通过，收尾吧。' + '说明。' * 500 + '接下来处理登录页')
        self.append('收到')
        result = self.process(lambda _: candidate('completed'))
        self.assertEqual(result['completion_status'], 'active')
        self.assertFalse(result['title'].startswith('✓'))

    def test_missing_created_at_never_uses_state_title_or_updated_at(self):
        self.process()
        before = self.state()
        del self.backend.thread['createdAt']
        self.backend.thread['updatedAt'] = 1900000000
        self.append('验收通过，收尾吧')
        result = self.process(lambda _: self.fail('没有可靠创建时间不调用模型'))
        self.assertEqual(result['status'], 'metadata_unavailable')
        self.assertEqual(self.state(), before)

    def test_created_date_mismatch_preserves_original_date_and_title(self):
        self.process()
        before = self.state()
        self.backend.thread['createdAt'] = '2026-10-01T12:00:00Z'
        self.append('继续做这件事')
        self.assertEqual(self.process(lambda _: self.fail())['status'], 'metadata_changed')
        self.assertEqual(self.state(), before)

    def test_old_state_and_emoji_keep_do_not_migrate_display(self):
        old = '🧩 Codex｜Luna 后台调用'
        self.backend.thread['name'] = old
        title.atomic_json(title.state_path(self.root, fixtures.ID), {'policy_version': 8,
            'last_seen_title': old, 'last_generated_title': old, 'last_fingerprint': 'old'})
        result = self.process(lambda _: candidate())
        self.assertEqual(result['status'], 'kept')
        self.assertEqual(result['title'], old)
        self.assertEqual(self.backend.writes, [])
        self.assertEqual(self.state()['completion_status'], 'active')
        self.assertEqual(self.state()['created_date'], title.created_date(self.backend.thread))
        self.assertEqual(self.process(lambda _: self.fail())['status'], 'unchanged')

    def test_legacy_keep_preserves_established_canonical_on_completion(self):
        self.backend.thread['name'] = '🔎 Codex｜Luna 后台调用'
        self.process(lambda _: candidate())
        self.append('验收通过，收尾吧')
        model = Mock(return_value=candidate('completed', text='[分析] Codex｜测试'))
        result = self.process(model)
        self.assertEqual(model.call_args.args[0]['current_canonical_title'], CANONICAL)
        self.assertEqual(result['canonical_title'], CANONICAL)
        self.assertEqual(result['title'], '✓ ' + title.created_date(self.backend.thread) + ' ' + CANONICAL)

    def test_missing_completion_state_still_removes_completed_marker(self):
        self.process()
        self.append('验收通过，收尾吧')
        self.process(lambda _: candidate('completed'))
        state = self.state()
        state.pop('completion_status')
        title.atomic_json(title.state_path(self.root, fixtures.ID), state)
        self.append('现在增加一个新功能')
        result = self.process(lambda _: candidate('active'))
        self.assertEqual(result['status'], 'renamed')
        self.assertEqual(result['title'], state['created_date'] + ' ' + CANONICAL)
        self.assertEqual(self.state()['completion_status'], 'active')

    def test_legacy_completion_is_state_driven_not_format_cleanup(self):
        self.backend.thread['name'] = '🧩 Codex｜Luna 后台调用'
        self.append('验收通过，收尾吧')
        result = self.process(lambda _: candidate('completed'))
        self.assertEqual(result['status'], 'renamed')
        self.assertTrue(result['title'].startswith('✓ '))

    def test_completion_update_obeys_stale_pause_lock_archive(self):
        for change in ('turn', 'title', 'pause', 'lock', 'archive', 'date'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                self.backend = fixtures.FakeBackend()
                self.process()
                self.append('验收通过，收尾吧')
                def model(_):
                    if change == 'turn': self.append('还有新任务')
                    if change == 'title': self.backend.thread['name'] = '手动标题'
                    if change == 'pause': title.atomic_json(self.root / 'config.json', {'enabled': False})
                    if change == 'lock': title.atomic_json(title.state_path(self.root, fixtures.ID), {**self.state(), 'locked': True})
                    if change == 'archive': self.backend.archived = True
                    if change == 'date': self.backend.thread['createdAt'] = '2026-10-01T12:00:00Z'
                    return candidate('completed')
                result = self.process(model)
                expected = {'pause': 'disabled', 'lock': 'locked', 'archive': 'archived'}.get(change, 'stale_result')
                self.assertEqual(result['status'], expected)
                self.assertEqual(len(self.backend.writes), 1)
                self.assertEqual(self.state()['completion_status'], 'active')

    def test_write_crash_recovers_pending_metadata_without_manual_lock(self):
        self.process()
        self.append('验收通过，收尾吧')
        rename = self.backend.rename
        def crash(tid, text):
            rename(tid, text)
            raise KeyboardInterrupt()
        with patch.object(self.backend, 'rename', side_effect=crash), self.assertRaises(KeyboardInterrupt):
            self.process(lambda _: candidate('completed'))
        self.assertEqual(self.state()['completion_status'], 'active')
        self.assertEqual(self.state()['pending_metadata']['completion_status'], 'completed')
        result = self.process(lambda _: candidate('completed'))
        self.assertEqual(result['status'], 'kept')
        self.assertEqual(self.state()['completion_status'], 'completed')
        self.assertNotIn('pending_metadata', self.state())
        self.assertFalse(self.state().get('locked'))
        self.assertEqual(len(self.backend.writes), 2)

    def test_successful_keep_discards_old_failed_pending_write(self):
        self.process()
        self.append('验收通过，收尾吧')
        with patch.object(self.backend, 'rename', side_effect=adapter.BackendError('写入前失败')):
            with self.assertRaises(adapter.BackendError):
                self.process(lambda _: candidate('completed'))
        failed_title = self.state()['pending_title']
        self.append('继续增加测试')
        self.assertEqual(self.process(lambda _: candidate())['status'], 'kept')
        self.assertNotIn('pending_title', self.state())
        self.assertNotIn('pending_metadata', self.state())
        self.backend.thread['name'] = failed_title
        self.assertEqual(self.process(lambda _: self.fail())['status'], 'manual_title')
        self.assertTrue(self.state()['locked'])

    def test_no_other_history_is_read_or_modified(self):
        other = title.state_path(self.root, fixtures.NEW_TURN)
        title.atomic_json(other, {'last_seen_title': '历史标题', 'policy_version': 8})
        before = other.read_bytes()
        with patch.object(self.backend, 'read', wraps=self.backend.read) as read:
            self.process()
        self.assertTrue(all(call.args == (fixtures.ID,) for call in read.call_args_list))
        self.assertEqual(other.read_bytes(), before)

    def test_preview_status_is_not_model_completion_status(self):
        result = title.process_thread(self.backend, lambda _: candidate('completed'), fixtures.ID,
                                      self.root, self.config)
        self.assertEqual(result['status'], 'preview')
        self.assertEqual(result['completion_status'], 'completed')
        self.assertFalse(title.state_path(self.root, fixtures.ID).exists())

    def test_model_cli_policy_unchanged_and_schema_extended(self):
        def run(args, **kwargs):
            self.assertEqual(args[args.index('-m') + 1], self.config['model'])
            self.assertIn('model_reasoning_effort="low"', args)
            self.assertIn('service_tier="priority"', args)
            for flag in ('--ephemeral', '--ignore-user-config', '--skip-git-repo-check', '--sandbox'):
                self.assertIn(flag, args)
            schema = json.loads(Path(args[args.index('--output-schema') + 1]).read_text(encoding='utf-8'))
            self.assertEqual(schema['properties']['status']['enum'], ['active', 'completed'])
            Path(args[args.index('--output-last-message') + 1]).write_text(json.dumps(candidate()[0]), encoding='utf-8')
            return SimpleNamespace(returncode=0, stdout='')
        with patch.object(adapter.subprocess, 'run', side_effect=run):
            adapter.generate_title('unused', self.config, {'original_goal': '分析 Codex 后台调用'}, title.ROOT)


if __name__ == '__main__':
    unittest.main()
