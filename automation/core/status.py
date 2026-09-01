"""status.py — read-only aggregation of every case's status for the frontend.

collect_status() scans test_cases.json + runs/<module>/<case>/ +
config/case_result_map.json and returns a JSON-ready grid of every module and
case, with a binary result of 采集 (collected) / 未采集 (not collected) /
待判定 (pending).

Binary mapping is user-authored in config/case_result_map.json:
    { "REG-MODIFY-001": "采集", "DRIVER-UNLOAD-001": "未采集", ... }
Cases absent from the map default to 待判定. When the file does not exist,
every case defaults to 待判定 (graceful fallback, never raises).
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent      # core/
ROOT = _HERE.parent                           # automation/
CONFIG = ROOT / 'config'
# 运行产物统一在 results/runs/（与 frontend/server.py 的 RUNS 一致）。
# 曾误指 automation/runs/（空目录），导致 /api/overview 全部状态读不出来。
RUNS = ROOT.parent / 'results' / 'runs'

# Display name for every module (16 total).
MODULE_DISPLAY = {
    'Process':       'Process Activity',
    'File':          'File Manipulation',
    'Account':       'User Account Activity',
    'Network':       'Network Activity',
    'Hash':          'Hash Algorithms',
    'Registry':      'Registry Activity',
    'ScheduleTask': 'Schedule Task Activity',
    'Service':       'Service Activity',
    'Driver':        'Driver/Module Activity',
    'Device':        'Device Operations',
    'GPO':           'Other Relevant Events',
    'Pipe':          'Named Pipe Activity',
    'EDRSysOps':     'EDR SysOps',
    'WMI':           'WMI Activity',
    'BIT':          'BIT JOBS Activity',
    'PowerShell':    'PowerShell Activity',
}

# Reserved modules — no sample / not yet in test_cases.json.
# Each entry: (module_key, [(case_id, display_name), ...]).
RESERVED_MODULES = [
    ('Device', [
        ('DEVICE-USB-UNMOUNT-001', 'USB Device Unmount'),
        ('DEVICE-USB-MOUNT-001', 'USB Device Mount'),
    ]),
    ('EDRSysOps', [
        ('AGENT-START-001', 'Agent Start'),
        ('AGENT-STOP-001', 'Agent Stop'),
        ('AGENT-INSTALL-001', 'Agent Install'),
        ('AGENT-UNINSTALL-001', 'Agent Uninstall'),
        ('AGENT-KEEPALIVE-001', 'Agent Keep-Alive'),
        ('AGENT-ERROR-001', 'Agent Errors'),
    ]),
]


def _load_case_result_map() -> dict:
    p = CONFIG / 'case_result_map.json'
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}
    if isinstance(data, dict):
        # v2.0.0: {"_meta": {...}, "cases": {case_id: {"verdict", "uncertain", ...}}}
        if 'cases' in data:
            return data['cases']
        # legacy: flat {case_id: "采集"} or {"results": {...}}
        return data.get('results', data) if 'results' in data else data
    return {}


def _load_classmate_baseline() -> dict:
    """同学实测映射：case_id -> {behavior, verdict, operation, note}（演示期兜底参照）。"""
    p = CONFIG / 'classmate_baseline.json'
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}
    return data.get('cases', {}) if isinstance(data, dict) else {}


def _verdict_to_binary(value) -> str:
    """Map a case_result_map entry to the frontend binary status.

    v2.0.0 entry is a dict {"verdict": "通过"/"通过(部分)?"/"未通过", ...};
    legacy entry is a flat string "采集"/"未采集".
    统一说法：采集通过 / 采集未通过 / 待测。
    """
    if isinstance(value, str):
        v = value
    elif isinstance(value, dict):
        v = value.get('verdict', '') or ''
    else:
        return '待判定'
    if v in ('采集', '通过', '对', '疑问', '部分', '通过(部分)?'):
        return '采集通过'
    if v in ('未采集', '未通过', '错'):
        return '采集未通过'
    return '待判定'


def _capability_to_binary(match_doc, has_stdout=False, result_map_entry=None, classmate_entry=None) -> str:
    """能力判定 → 前端状态：采集通过 / 采集未通过 / 待判定。

    优先级：case_result_map 定稿（含人工实测直填的手动 case）> match 能力结论
    > 同学 baseline 兜底（演示期暂时保留）> 待判定。
    """
    b = _verdict_to_binary(result_map_entry)
    if b != '待判定':
        return b
    if match_doc:
        cap = match_doc.get('capability_detected')
        if cap is True:
            return '采集通过'
        if cap is False:
            return '采集未通过'
    # 没有定稿结论时，演示期用同学 baseline 顶包（暂时保留）
    if isinstance(classmate_entry, dict):
        v = classmate_entry.get('verdict', '')
        if v in ('有', '?'):
            return '采集通过'
        if v == '无':
            return '采集未通过'
    return '待判定'


def _load_test_cases() -> list[dict]:
    p = CONFIG / 'test_cases.json'
    try:
        data = json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception:
        return []
    return data.get('cases', []) if isinstance(data, dict) else data


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:
        return None


def _verdict_meta(doc) -> dict:
    """Extract verdict icon/name/capability_state from match_result.json.

    Single-phase match_result.json stores verdict as a plain string plus
    verdict_icon / capability_state siblings; fullcycle stores overall_verdict
    / overall_icon / overall_capability_state. Handle both.
    """
    if not isinstance(doc, dict):
        return {}
    v = doc.get('verdict')
    if isinstance(v, str):
        return {
            'name': v,
            'icon': doc.get('verdict_icon'),
            'capability_state': doc.get('capability_state'),
        }
    if isinstance(v, dict):
        return {
            'name': v.get('name'),
            'icon': v.get('icon'),
            'capability_state': v.get('capability_state'),
        }
    if doc.get('overall_verdict'):
        return {
            'name': doc.get('overall_verdict'),
            'icon': doc.get('overall_icon'),
            'capability_state': doc.get('overall_capability_state'),
        }
    return {}


def _result_entry(value) -> dict:
    """Return the three-state conclusion (对/疑问/错) from case_result_map.

    The v2.0.0 map entry is a dict {verdict, uncertain, note, situations};
    legacy entries are flat strings. Used by the frontend top badge, which
    must show the *conclusion* (three-state), not the *match engine* verdict
    (five-state) that lives in match_result.json.
    """
    if isinstance(value, dict):
        return {
            'verdict': value.get('verdict', ''),
            'uncertain': bool(value.get('uncertain', False)),
            'note': value.get('note', ''),
            'situations': value.get('situations', {}),
            'analysis': value.get('result_analysis') or {},
        }
    if isinstance(value, str):
        return {'verdict': value, 'uncertain': False, 'note': '', 'situations': {}}
    return {'verdict': '', 'uncertain': False, 'note': '', 'situations': {}}


def _summary(modules: list) -> dict:
    total = collected = not_collected = pending = 0
    for m in modules:
        for c in m['cases']:
            total += 1
            if c['binary'] == '采集通过':
                collected += 1
            elif c['binary'] == '采集未通过':
                not_collected += 1
            else:
                pending += 1
    return {
        'total': total,
        'collected': collected,
        'not_collected': not_collected,
        'pending': pending,
    }


def collect_status() -> dict:
    """Aggregate status for every case (integrated + reserved).

    Returns::

        {
          'modules': [
            {'module': 'Registry', 'display': 'Registry Activity', 'cases': [
               {'case_id': ..., 'display': ..., 'action': ..., 'program': ...,
                'snapshot': ..., 'integrated': bool,
                'binary': '采集'|'未采集'|'待判定',
                'run_state': 'never'|'delivered'|'matched',
                'has_stdout': bool, 'has_match_result': bool,
                'verdict': {'name','icon','capability_state'}},
               ...]},
          ],
          'summary': {'total', 'collected', 'not_collected', 'pending'},
        }
    """
    result_map = _load_case_result_map()
    classmate = _load_classmate_baseline()
    cases = _load_test_cases()

    modules: dict[str, list] = {}

    for c in cases:
        module = c.get('module') or 'Unknown'
        case_id = c.get('id') or ''
        if not case_id:
            continue

        out_dir = RUNS / module / case_id
        stdout_path = out_dir / f'{case_id}_stdout.txt'
        match_path = out_dir / 'match_result.json'

        match_doc = _read_json(match_path)
        run_state = 'matched' if match_path.exists() else (
            'delivered' if stdout_path.exists() else 'never'
        )

        modules.setdefault(module, []).append({
            'case_id': case_id,
            'module': module,
            'display': c.get('behavior') or case_id,
            'action': c.get('action', ''),
            'program': c.get('program', ''),
            'snapshot': c.get('snapshot', ''),
            'integrated': True,
            # 圆点/状态跟 match 走：match 匹配(能力存在)=绿，不匹配=红，
            # 跑过样本没 match=待匹配，完全没跑才用 case_result_map 兑底。
            'binary': _capability_to_binary(match_doc, stdout_path.exists(), result_map.get(case_id), classmate.get(case_id)),
            'run_state': run_state,
            'has_stdout': stdout_path.exists(),
            'has_match_result': match_path.exists(),
            'verdict': _verdict_meta(match_doc),
            'result': _result_entry(result_map.get(case_id)),
            # v2 判定在 match_result.json 的 match_stats 嵌套层（非顶层）
            'capability_v2': ((match_doc or {}).get('match_stats') or {}).get('capability_v2'),
            'collected_v2': ((match_doc or {}).get('match_stats') or {}).get('collected_v2'),
            'classmate': classmate.get(case_id, {}),
        })

    # Reserved modules (behaviours not yet in test_cases.json).
    for module, behaviors in RESERVED_MODULES:
        for case_id, display in behaviors:
            modules.setdefault(module, []).append({
                'case_id': case_id,
                'module': module,
                'display': display,
                'action': '',
                'program': '',
                'snapshot': '',
                'integrated': False,
                'binary': _capability_to_binary(None, False, result_map.get(case_id), classmate.get(case_id)),
                'run_state': 'never',
                'has_stdout': False,
                'has_match_result': False,
                'verdict': {},
                'result': _result_entry(result_map.get(case_id)),
                'capability_v2': None,
                'collected_v2': None,
                'classmate': classmate.get(case_id, {}),
            })

    result = []
    for module in modules:
        case_list = sorted(modules[module], key=lambda x: x['case_id'])
        result.append({
            'module': module,
            'display': MODULE_DISPLAY.get(module, module),
            'cases': case_list,
        })
    result.sort(key=lambda m: m['display'])

    return {'modules': result, 'summary': _summary(result)}
