"""T0 smoke tests for the frontend (no VM required).

  T0-1  collect_status() invariants on real data (16 modules，总数随配置动态算)
  T0-2  /api/overview via Flask test client
  T0-3  field coverage parsing from an existing match_result.json
  T0-4  status.RUNS 与 server.RUNS 指向同一目录（防 P0 路径漂移回归）

历史说明：T0-1 曾断言「collected==0 全部待判定」——那是 case_result_map/runs
均为空时的兜底态。2026-09-01 status.py 的 RUNS 路径修复后，概览读到真实
数据（collected>0），原断言前提已失效，改为校验不变量。
2026-09-02 用户新增 5 个变体 case（REG-CREATE-002 等，45→50），总数断言
由写死 53 改为从 test_cases.json + RESERVED_MODULES 动态计算。
"""
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent           # E:/EDR/frontend
ROOT = _HERE.parent / 'automation'    # E:/EDR/automation
for p in (ROOT, ROOT / 'core', ROOT / 'tools', _HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from status import collect_status, RESERVED_MODULES, _load_test_cases

BINARY_VALUES = {'采集通过', '采集未通过', '待判定'}
RUN_STATES = {'never', 'delivered', 'matched'}


def _expected_total() -> int:
    """期望 case 总数 = test_cases.json + RESERVED_MODULES（随配置动态算，不写死）。"""
    return len(_load_test_cases()) + sum(len(b) for _, b in RESERVED_MODULES)


def t0_collect_status():
    st = collect_status()
    s = st['summary']
    print(f"[T0-1] collect_status: {len(st['modules'])} modules, summary={s}")
    assert len(st['modules']) == 16, f"expected 16 modules, got {len(st['modules'])}"
    exp = _expected_total()
    assert s['total'] == exp, f"expected {exp} cases, got {s['total']}"
    assert s['collected'] + s['not_collected'] + s['pending'] == s['total'], s
    for m in st['modules']:
        for c in m['cases']:
            assert c['binary'] in BINARY_VALUES, f"{c['case_id']} binary={c['binary']}"
            assert c['run_state'] in RUN_STATES, f"{c['case_id']} run_state={c['run_state']}"
            # 有 match_result 的 case 不应停留在 never
            if c['has_match_result']:
                assert c['run_state'] == 'matched', c['case_id']
    print(f"[T0-1 PASS] invariants: {s['total']} cases "
          f"(collected={s['collected']}, not_collected={s['not_collected']}, pending={s['pending']})")


def t0_overview():
    try:
        from server import app
    except Exception as e:  # noqa: BLE001
        print(f"[T0-2 SKIP] Flask import failed: {e}")
        return
    client = app.test_client()
    resp = client.get('/api/overview')
    assert resp.status_code == 200, resp.status_code
    data = resp.get_json()
    n_modules = len(data['modules'])
    total = data['summary']['total']
    print(f"[T0-2] /api/overview -> {n_modules} modules / {total} cases")
    assert n_modules == 16, f"expected 16 modules, got {n_modules}"
    exp = _expected_total()
    assert total == exp, f"expected {exp} cases, got {total}"
    # 新增只读端点冒烟
    assert client.get('/api/sysmon_evidence').status_code == 200
    assert client.get('/api/manual').status_code == 200
    assert client.get('/api/analysis').status_code == 200
    assert client.get('/api/classmate_baseline').status_code == 200
    v = client.get('/api/case/REG-CREATE-001/variants')
    assert v.status_code == 200 and v.get_json().get('variants') == [], v.get_json()
    # analysis 合并语义：只更新 payload 出现的字段，三字段全空才删除（测试后还原现场）
    from server import ANALYSIS
    existed = ANALYSIS.exists()
    orig = ANALYSIS.read_text(encoding='utf-8') if existed else None
    try:
        r = client.post('/api/case/__T0__/analysis', json={'mapping': '映射笔记X'})
        assert r.status_code == 200 and r.get_json()['ok']
        r = client.post('/api/case/__T0__/analysis', json={'map_name': 'EvtX', 'analysis': '分析X'})
        cur = client.get('/api/analysis').get_json()['cases']['__T0__']
        assert cur['mapping'] == '映射笔记X' and cur['map_name'] == 'EvtX' \
            and cur['analysis'] == '分析X', cur
        client.post('/api/case/__T0__/analysis',
                    json={'map_name': '', 'mapping': '', 'analysis': ''})
        assert '__T0__' not in client.get('/api/analysis').get_json()['cases']
    finally:
        if existed:
            ANALYSIS.write_text(orig, encoding='utf-8')
        elif ANALYSIS.exists():
            ANALYSIS.unlink()
    print(f"[T0-2 PASS] /api/overview 16 modules / {total} cases + 新端点可用 + analysis 合并语义")


def t0_field_table():
    runs = ROOT.parent / 'results' / 'runs'
    found = None
    for mp in sorted(runs.rglob('match_result.json')):
        doc = json.loads(mp.read_text(encoding='utf-8-sig'))
        # 找一个带字段覆盖信息的（legacy field_coverage 或 v2 observed_fields）
        if doc.get('field_coverage') or (doc.get('observed_fields') or {}).get('declared'):
            found, found_doc = mp, doc
            break
    if found is None:
        print("[T0-3 SKIP] no match_result.json with field coverage found")
        return
    doc = found_doc
    fc = doc.get('field_coverage', [])
    phases = doc.get('phases', [])
    if not fc and phases:
        fc = phases[0].get('field_coverage', [])
    print(f"[T0-3] from {found.relative_to(ROOT.parent)}: "
          f"verdict={doc.get('verdict') or doc.get('overall_verdict')}")
    if fc:
        keys = set(fc[0].keys())
        assert {'field', 'required', 'rule', 'actual_value', 'status'} <= keys, keys
        print(f"[T0-3 PASS] legacy field_coverage keys: {sorted(keys)}")
    else:
        declared = doc['observed_fields']['declared']
        assert isinstance(declared, list) and declared, "observed_fields.declared empty"
        total = doc['observed_fields'].get('total', len(declared))
        print(f"[T0-3 PASS] v2 observed_fields: {len(declared)} declared / total={total}")


def t0_runs_path_consistency():
    """status.py 与 server.py 必须读同一个 runs 目录。

    2026-09-01 P0：status.RUNS 曾指 automation/runs/（空目录），server 写
    results/runs/，导致 /api/overview 全部状态读不出来。此测试防回归。
    """
    import status as status_mod
    import server as server_mod
    print(f"[T0-4] status.RUNS={status_mod.RUNS}")
    print(f"       server.RUNS={server_mod.RUNS}")
    assert status_mod.RUNS == server_mod.RUNS, (
        f"RUNS 路径不一致: status={status_mod.RUNS} vs server={server_mod.RUNS}")
    assert (status_mod.RUNS).is_dir(), f"RUNS 目录不存在: {status_mod.RUNS}"
    print("[T0-4 PASS] RUNS 路径一致且存在")


if __name__ == '__main__':
    t0_collect_status()
    t0_overview()
    t0_field_table()
    t0_runs_path_consistency()
    print("\nALL T0 PASS")
