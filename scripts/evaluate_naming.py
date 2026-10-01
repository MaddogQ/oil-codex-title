#!/usr/bin/env python3
"""用合成案例评测独立命名模型；显式 --live 才会消耗账号额度。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import re
from pathlib import Path
import statistics
import time
from codex_adapter import find_codex, generate_title
from oil_codex_title import DEFAULTS, validate_candidate
ROOT = Path(__file__).resolve().parents[1]


def candidate_errors(candidate, case):
    expected = case['expected']
    title = candidate['title']
    body = title.split(' ', 1)[1] if title else ''
    errors = []
    if candidate['action'] != expected['action']: errors.append('动作不符')
    if candidate['status'] != expected['status']: errors.append('完成状态不符')
    if expected.get('category') and not title.startswith('[' + expected['category'] + '] '):
        errors.append('主线类别不符')
    for word in expected.get('contains', []):
        if word.casefold() not in title.casefold(): errors.append('缺少对象：' + word)
    for word in expected.get('reject', []):
        if word.casefold() in title.casefold(): errors.append('错误主线：' + word)
    # 类别名称固定为中文，语言断言只检查对象与目标。
    if expected.get('title_pattern') and not re.search(expected['title_pattern'], body):
        errors.append('标题语言或文字范围不符')
    if candidate['action'] == 'rename' and title in case['context'].get('conflicting_titles', []):
        errors.append('未区分冲突')
    if 'exact_title' in expected and title != expected['exact_title']:
        errors.append('稳定标题或迁移主线变化')
    for word in expected.get('object_contains', []):
        if word.casefold() not in body.split('｜')[0].casefold(): errors.append('对象未前置：' + word)
    return errors


def self_check():
    case = {'context': {}, 'expected': {'action': 'keep', 'status': 'completed',
            'category': '分析', 'exact_title': '[分析] Codex｜Luna calling',
            'title_pattern': r'^(?!.*[\u3400-\u9fff])[^｜]*｜[A-Za-z][\x20-\x7e]*$'}}
    candidate = {'action': 'keep', 'status': 'completed', 'title': '[分析] Codex｜Luna calling'}
    assert not candidate_errors(candidate, case)
    assert '完成状态不符' in candidate_errors({**candidate, 'status': 'active'}, case)
    assert '主线类别不符' in candidate_errors({**candidate, 'title': '[实现] Codex｜Luna calling'}, case)
    empty = {'context': {}, 'expected': {'action': 'keep', 'status': 'active', 'exact_title': ''}}
    assert not candidate_errors({'action': 'keep', 'status': 'active', 'title': ''}, empty)
    print('评估器状态、类别、语言与空标题自检通过。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='允许实际调用已配置的命名模型')
    parser.add_argument('--self-check', action='store_true', help='离线检查评估器断言，不调用模型')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/naming-evaluation.json')
    parser.add_argument('--cases', type=Path, default=ROOT / 'tests/fixtures/naming_cases.json', help='合成案例文件，可单独评测语言等规则')
    parser.add_argument('--workers', type=int, default=4, choices=range(1,9))
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not args.live:
        print(f'共 {len(cases)} 个合成案例；加 --live 才调用模型。')
        return
    binary = find_codex()
    def run(case):
        start = time.monotonic()
        candidate, usage = None, {}
        try:
            candidate, usage = generate_title(binary, DEFAULTS, case['context'], ROOT)
            # 检查模型实际输出，不让 keep 回填现有 canonical 掩盖错误。
            candidate = validate_candidate(candidate, '')
            errors = candidate_errors(candidate, case)
            return {'case': case['id'], **candidate, 'passed': not errors, 'errors':errors,
                    'seconds':round(time.monotonic()-start,2),'usage':usage}
        except Exception as exc:
            return {'case':case['id'],'passed':False,'errors':[str(exc)],
                    'candidate':candidate,'usage':usage,'seconds':round(time.monotonic()-start,2)}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(run,cases))
    report = {'model':DEFAULTS['model'],'service_tier':DEFAULTS['service_tier'],
              'cases':len(rows),'passed':sum(r['passed'] for r in rows),
              'model_cases':sum(bool(r.get('usage')) for r in rows),
              'median_seconds':round(statistics.median(r['seconds'] for r in rows),2),
              'notice':'确定性过滤与命名模型的合成案例单次检查，不代表普遍准确率，也不验证桌面显示。',
              'results':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False))
    for row in rows:
        print(json.dumps({k:v for k,v in row.items() if k!='usage'},ensure_ascii=False))
    return 0 if report['passed']==len(rows) else 1

if __name__=='__main__':
    raise SystemExit(main())
