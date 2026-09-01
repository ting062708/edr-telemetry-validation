#!/usr/bin/env python
"""自动化生成 EDR 采集能力验证报告。

数据源：
  - config/test_cases.json        36 个 case 定义
  - config/case_result_map.json   人工定稿（对/错/疑问 + note）
  - runs/<module>/<case>/match_result.json  自动匹配结果（capability_detected/anchor/anomaly/value_scan）
  - config/baseline.json          baseline 快照（存在则输出 diff 摘要）

输出：
  - runs/REPORT.md                Markdown 报告
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT.parent / 'results' / 'runs'
CONFIG = ROOT / 'config'

# 四态 -> emoji
BIN_ICON = {'采集通过': '🟢', '采集未通过': '🔴', '待匹配': '🟡', '待测': '⚪'}


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def _load_cases() -> list[dict]:
    doc = _read_json(CONFIG / 'test_cases.json')
    if not doc:
        return []
    return doc.get('cases', [])


def _binary(match_doc, result_entry) -> str:
    if match_doc:
        cap = match_doc.get('capability_detected')
        if cap is True:
            return '采集通过'
        if cap is False:
            return '采集未通过'
    # case_result_map 兜底
    v = result_entry.get('verdict', '') if isinstance(result_entry, dict) else ''
    if v in ('对', '采集', '通过'):
        return '采集通过'
    if v in ('错', '未采集', '未通过'):
        return '采集未通过'
    return '待测'


def main() -> int:
    cases = _load_cases()
    baseline = _read_json(CONFIG / 'baseline.json')

    # 复用 status.py 的四态判定（采集通过/采集未通过/待匹配/待测）
    import status as _st
    binary_map = {}
    try:
        for m in _st.collect_status()['modules']:
            for c in m['cases']:
                binary_map[c['case_id']] = c['binary']
    except Exception:
        pass

    rows = []
    for c in cases:
        cid = c.get('id', '')
        module = c.get('module', '')
        action = c.get('action', '')
        mr_path = RUNS / module / cid / 'match_result.json'
        mr = _read_json(mr_path)
        bin_state = binary_map.get(cid, '待测')
        anomaly = (mr or {}).get('anomaly', '')
        anchor = (mr or {}).get('anchor_detected')
        vs = (mr or {}).get('value_scan', {}) or {}
        hit = [k for k, v in vs.items() if v.get('found')]
        miss = [k for k, v in vs.items() if not v.get('found')]
        rows.append({
            'module': module, 'case_id': cid, 'action': action,
            'binary': bin_state, 'anchor': anchor, 'anomaly': anomaly,
            'hit': hit, 'miss': miss,
        })

    # 概览统计
    cnt = {k: 0 for k in ('采集通过', '采集未通过', '待匹配', '待测')}
    for r in rows:
        cnt[r['binary']] = cnt.get(r['binary'], 0) + 1

    L = []
    L.append('# EDR 采集能力验证报告')
    L.append('')
    L.append(f'> 生成时间：{datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")}')
    L.append(f'> 覆盖用例：{len(rows)} / 36（另有预留模块 17 个未接入）')
    L.append('')
    L.append('## 概览')
    L.append('')
    L.append('| 状态 | 数量 |')
    L.append('|---|---|')
    for k in ('采集通过', '采集未通过', '待匹配', '待测'):
        L.append(f'| {BIN_ICON[k]} {k} | {cnt[k]} |')
    L.append('')

    # 各模块能力矩阵
    L.append('## 能力矩阵')
    L.append('')
    by_module: dict[str, list] = {}
    for r in rows:
        by_module.setdefault(r['module'], []).append(r)
    for m, rs in by_module.items():
        L.append(f'### {m}')
        L.append('')
        L.append('| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |')
        L.append('|---|---|---|---|---|')
        for r in rs:
            anchor_txt = {True: '是', False: '否', None: '—'}.get(r['anchor'], '—')
            L.append(
                f"| {r['case_id']} | {r['action']} | {BIN_ICON[r['binary']]} {r['binary']} "
                f"| {anchor_txt} | {len(r['hit'])}/{len(r['miss'])} |"
            )
        L.append('')

    # 异常采集现象清单
    anomalies = [r for r in rows if r['anomaly']]
    L.append('## 异常采集现象')
    L.append('')
    if anomalies:
        for r in anomalies:
            L.append(f"- **{r['case_id']}**（{r['binary']}）：{r['anomaly']}")
    else:
        L.append('（暂无）')
    L.append('')

    # baseline diff 摘要
    if baseline and baseline.get('verdicts'):
        bv = baseline['verdicts']
        changed = []
        for r in rows:
            old = bv.get(r['case_id'])
            if old and old != r['binary']:
                changed.append((r['case_id'], old, r['binary']))
        L.append('## baseline 对比')
        L.append('')
        if changed:
            for cid, old, new in changed:
                L.append(f'- {cid}: {old} → {new}')
        else:
            L.append('（与 baseline 无差异）')
        L.append('')

    out = RUNS / 'REPORT.md'
    out.write_text('\n'.join(L), encoding='utf-8')
    print(f'报告已生成: {out}')
    print(f'概览: {cnt}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
