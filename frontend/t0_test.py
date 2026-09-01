"""T0 smoke tests for the frontend (no VM required).

  T0-1  collect_status() fallback: case_result_map.json missing -> all 待判定
  T0-2  /api/overview via Flask test client
  T0-3  field_coverage parsing from an existing match_result.json
"""
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent           # E:/EDR/frontend
ROOT = _HERE.parent / 'EDRTest' / 'automation'    # E:/EDR/EDRTest/automation
for p in (ROOT, ROOT / 'core', ROOT / 'tools', _HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from status import collect_status


def t0_collect_status():
    st = collect_status()
    s = st['summary']
    print(f"[T0-1] collect_status: {len(st['modules'])} modules, summary={s}")
    for m in st['modules']:
        print(f"        {m['module']:<14} {len(m['cases'])} cases")
    # fallback: case_result_map.json missing -> every case 待判定
    assert s['collected'] == 0 and s['not_collected'] == 0, s
    assert s['pending'] == s['total'], s
    for m in st['modules']:
        for c in m['cases']:
            assert c['binary'] == '待判定', f"{c['case_id']}={c['binary']}"
    print(f"[T0-1 PASS] fallback: all {s['total']} cases 待判定")


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
    assert total == 53, f"expected 53 cases, got {total}"
    print("[T0-2 PASS] /api/overview 16 modules / 53 cases")


def t0_field_table():
    runs = ROOT / 'runs'
    found = None
    for mp in runs.rglob('match_result.json'):
        found = mp
        break
    if found is None:
        print("[T0-3 SKIP] no match_result.json found under runs/")
        return
    doc = json.loads(found.read_text(encoding='utf-8-sig'))
    fc = doc.get('field_coverage', [])
    phases = doc.get('phases', [])
    if not fc and phases:
        fc = phases[0].get('field_coverage', [])
    print(f"[T0-3] from {found.relative_to(ROOT)}: "
          f"verdict={doc.get('verdict') or doc.get('overall_verdict')}, field_coverage={len(fc)}")
    assert fc, "field_coverage empty"
    keys = set(fc[0].keys())
    assert {'field', 'required', 'rule', 'actual_value', 'status'} <= keys, keys
    print(f"[T0-3 PASS] field keys: {sorted(keys)}")


if __name__ == '__main__':
    t0_collect_status()
    t0_overview()
    t0_field_table()
    print("\nALL T0 PASS")
