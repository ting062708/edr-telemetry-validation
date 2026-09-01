#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sysmon_evidence.py — 批量扫描所有 case 的 sysmon evtx，产出 L2 佐证矩阵。

sysmon evtx 由 runner 在每个 case 运行后自动采集（runs/<module>/<case>/sysmon_<case>.evtx）。
本工具把全部 evtx 解析，按 config/sysmon_baseline.json 的『能力→EventID』映射，
产出每个 case 的 sysmon 证据（采到哪些行为），作为 IOA 采集能力的第二证据通道。

用法：
    python tools/sysmon_evidence.py [--out config/sysmon_evidence.json] [--case xxx]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # automation/
CONFIG = HERE / 'config'
RUNS = HERE / 'runs'

sys.path.insert(0, str(HERE / 'tools'))
from parse_evtx import read_evtx  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='批量扫描 sysmon evtx → 佐证矩阵')
    ap.add_argument('--out', default=str(CONFIG / 'sysmon_evidence.json'))
    ap.add_argument('--case', help='只扫单个 case（默认全量）')
    ap.add_argument('--max', type=int, default=0, help='最多扫 N 个（调试用，0=不限）')
    args = ap.parse_args()

    baseline = json.loads((CONFIG / 'sysmon_baseline.json').read_text(encoding='utf-8'))
    bcases = baseline.get('cases', {})
    eid_names = baseline.get('_meta', {}).get('sysmon_event_id', {})

    evtx_files = []
    if args.case:
        for m in RUNS.iterdir():
            p = m / args.case / ('sysmon_%s.evtx' % args.case)
            if p.exists():
                evtx_files = [p]
                break
    else:
        evtx_files = list(RUNS.rglob('sysmon_*.evtx'))
    if args.max:
        evtx_files = evtx_files[:args.max]

    matrix = {}
    for p in evtx_files:
        case_id = p.name.replace('sysmon_', '').replace('.evtx', '')
        try:
            events = read_evtx(str(p))
        except Exception as exc:
            matrix[case_id] = {'error': str(exc)[:150]}
            continue
        dist = Counter(e['EventID'] for e in events)
        baseline_ids = bcases.get(case_id, {}).get('event_ids', [])
        matched = [eid for eid in baseline_ids if dist.get(eid)]
        matrix[case_id] = {
            'total': len(events),
            'event_ids': {str(k): v for k, v in sorted(dist.items())},
            'baseline_ids': baseline_ids,
            'matched': matched,
            'captured': bool(matched),
            'note': bcases.get(case_id, {}).get('note', ''),
        }

    Path(args.out).write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2), encoding='utf-8')
    print('已写出 %d 个 case 的 sysmon 证据到 %s' % (len(matrix), args.out))
    print()
    print('%-26s %-8s %-30s %s' % ('CASE', '总条数', '命中Sysmon事件', '结论'))
    print('-' * 90)
    for cid in sorted(matrix):
        v = matrix[cid]
        if 'error' in v:
            print('%-26s %-8s %-30s %s' % (cid, 'ERR', '', v['error']))
            continue
        hits = ' '.join('%s(%s)' % (eid, eid_names.get(str(eid), '?')) for eid in v['matched']) or '—'
        print('%-26s %-8d %-30s %s' % (cid, v['total'], hits, '采到' if v['captured'] else '未采到'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
