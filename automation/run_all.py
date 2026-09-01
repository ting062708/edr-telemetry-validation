"""
run_all.py — Minimal black-box batch orchestrator for EDR Telemetry validation.

A thin wrapper: it shells out to runner/telemetry_runner.py (never re-implements
its logic), keeps a checkpoint state file so runs are resumable, and can
aggregate all verdicts into one capability matrix CSV.

Commands
--------
  python run_all.py deliver --module Registry              # batch deliver (skip done)
  python run_all.py deliver --module Registry --case REG-MODIFY-001
  python run_all.py deliver --module Registry --resume     # continue from state
  python run_all.py deliver --module Registry --no-restore # skip per-case snapshot restore
  python run_all.py deliver --module Registry --dry-run    # list only
  python run_all.py match  --module Registry [--json <export.json>]
  python run_all.py status  [--module Registry]
  python run_all.py matrix  [--module Registry]            # -> runs/capability_matrix.csv

State is stored in runs/progress.json (nothing is re-run unless you force it).
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_HERE     = Path(__file__).resolve().parent
_RUNNER   = _HERE / 'runner' / 'telemetry_runner.py'
_CONFIG   = _HERE / 'config'
_RUNS     = _HERE / 'runs'
_PROGRESS = _RUNS / 'progress.json'
_BASELINE = _CONFIG / 'baseline.json'

S_PENDING      = 'pending'
S_DELIVERED    = 'delivered'
S_MATCHED      = 'matched'
S_FAIL_DELIVER = 'failed_deliver'
S_FAIL_MATCH   = 'failed_match'


def _load_cases() -> list[dict]:
    with (_CONFIG / 'test_cases.json').open('r', encoding='utf-8') as fh:
        data = json.load(fh)
    return data.get('cases', [])


def _load_progress() -> dict:
    if _PROGRESS.exists():
        with _PROGRESS.open('r', encoding='utf-8') as fh:
            return json.load(fh)
    return {}


def _save_progress(progress: dict) -> None:
    _RUNS.mkdir(parents=True, exist_ok=True)
    with _PROGRESS.open('w', encoding='utf-8') as fh:
        json.dump(progress, fh, ensure_ascii=False, indent=2)


def _set_status(progress: dict, case_id: str, status: str) -> None:
    entry = progress.setdefault(case_id, {})
    entry['status'] = status
    entry['updated'] = datetime.now().isoformat(timespec='seconds')
    _save_progress(progress)


def _run(cmd: list[str]) -> int:
    print('\n' + '=' * 64)
    print('$ ' + ' '.join(cmd))
    print('=' * 64)
    return subprocess.call(cmd)


def _select(cases: list[dict], args, progress: dict) -> list[dict]:
    out = []
    for c in cases:
        if args.module and c.get('module', '').lower() != args.module.lower():
            continue
        if getattr(args, 'case', None) and c['id'] != args.case:
            continue
        if getattr(args, 'resume', False):
            st = progress.get(c['id'], {}).get('status', S_PENDING)
            if args.command == 'deliver' and st in (S_DELIVERED, S_MATCHED):
                continue
            if args.command == 'match' and st == S_MATCHED:
                continue
        out.append(c)
    return out


def _out_dir(c: dict) -> Path:
    return _RUNS / c.get('module', 'Unknown') / c['id']


def _stdout_path(c: dict) -> Path:
    return _out_dir(c) / f"{c['id']}_stdout.txt"


def cmd_deliver(args) -> int:
    cases = _load_cases()
    progress = _load_progress()
    selected = _select(cases, args, progress)
    if not selected:
        print('Nothing to deliver.')
        return 0

    # Track the last selected case per module, so --shutdown-after powers off
    # once per module (after its final case), not after every single case.
    last_index_per_module: dict = {}
    for i, c in enumerate(selected):
        last_index_per_module[c.get('module', '')] = i

    restore_done = args.no_restore  # if no_restore, never restore
    for i, c in enumerate(selected):
        cmd = [sys.executable, str(_RUNNER), 'deliver', '--case', c['id']]
        if restore_done:
            cmd.append('--no-restore-snapshot')
        shutdown = bool(args.shutdown_after and
                        last_index_per_module.get(c.get('module', '')) == i)
        if shutdown:
            cmd.append('--shutdown-after')
        if args.dry_run:
            print(f'[dry-run] would deliver {c["id"]}'
                  f'{" + shutdown-after" if shutdown else ""}')
            continue
        # case 边界标记：前端据此把每个 case 的输出归档到对应终端卡片
        print(f'===CASE-BEGIN {c["id"]}===', flush=True)
        rc = _run(cmd)
        print(f'===CASE-END {c["id"]} rc={rc}===', flush=True)
        restore_done = True
        _set_status(progress, c['id'], S_DELIVERED if rc == 0 else S_FAIL_DELIVER)
    return 0


def cmd_match(args) -> int:
    cases = _load_cases()
    progress = _load_progress()
    selected = _select(cases, args, progress)
    if not selected:
        print('Nothing to match.')
        return 0

    for c in selected:
        stdout = _stdout_path(c)
        if not stdout.exists():
            print(f'[skip] {c["id"]}: stdout not found: {stdout}')
            continue
        cmd = [
            sys.executable, str(_RUNNER), 'match',
            '--case', c['id'],
            '--stdout', str(stdout),
        ]
        if args.json:
            cmd += ['--json', args.json]
        else:
            cmd += ['--non-interactive']
        cmd += ['--out-dir', str(_out_dir(c))]
        if args.dry_run:
            print(f'[dry-run] would match {c["id"]}')
            continue
        print(f'===CASE-BEGIN {c["id"]}===', flush=True)
        rc = _run(cmd)
        print(f'===CASE-END {c["id"]} rc={rc}===', flush=True)
        _set_status(progress, c['id'], S_MATCHED if rc == 0 else S_FAIL_MATCH)
    return 0


def cmd_status(args) -> int:
    cases = _load_cases()
    progress = _load_progress()
    print(f'\n{"CASE":<22} {"MODULE":<10} {"STATUS":<16} UPDATED')
    print('-' * 64)
    for c in cases:
        if args.module and c.get('module', '').lower() != args.module.lower():
            continue
        e = progress.get(c['id'], {})
        print(f'{c["id"]:<22} {c.get("module", ""):<10} '
              f'{e.get("status", S_PENDING):<16} {e.get("updated", "-")}')
    print()
    return 0


def _extract_verdict(doc: dict) -> tuple[str, str, str]:
    v = doc.get('verdict', '')
    if isinstance(v, dict):
        name = v.get('name', '')
        cap = v.get('capability_state', '')
    else:
        name = str(v)
        cap = doc.get('capability_state', '')
    cov = doc.get('coverage_status', '')
    ms = doc.get('match_stats', {})
    if not cov and isinstance(ms, dict):
        cov = ms.get('coverage_status', '')
    return name, cap, cov


# ── Baseline / regression diff ────────────────────────────────────────

_CAP_RANK = {
    'NOT_IMPLEMENTED': 0,
    'PARTIALLY_IMPLEMENTED': 1,
    'IMPLEMENTED': 2,
    'VIA_WINDOWS_EVENTLOG': 2,   # collected via Windows event log == collected
}
_SKIP_STATES = {'PENDING', 'ERROR_SAMPLE', 'ERROR_LOG_INPUT', 'AMBIGUOUS'}


def _verdict_name(doc: dict) -> str:
    """Read the capability verdict name from a match_result.json doc.

    Single-phase cases store it under `verdict` (str); fullcycle cases under
    `overall_verdict`. Returns 'PENDING' when absent/unparseable.
    """
    v = doc.get('verdict')
    if isinstance(v, dict):
        v = v.get('name')
    if not v:
        v = doc.get('overall_verdict')
    return (str(v).strip().upper() or 'PENDING')


def _compute_rule_fingerprint() -> dict:
    """SHA-256 fingerprint of the match-rule inputs (mappings/ + test_cases.json).

    Lets diff distinguish a real capability change from a verdict change caused
    by editing match rules / mappings.
    """
    import hashlib

    def _file_hash(p: Path) -> str:
        h = hashlib.sha256()
        with p.open('rb') as fh:
            for chunk in iter(lambda: fh.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()

    def _dir_hash(d: Path) -> str:
        h = hashlib.sha256()
        for p in sorted(d.rglob('*.json')):
            h.update(p.relative_to(d).as_posix().encode('utf-8'))
            h.update(_file_hash(p).encode('ascii'))
        return h.hexdigest()

    mappings = _CONFIG / 'mappings'
    return {
        'mappings':   _dir_hash(mappings) if mappings.is_dir() else '',
        'test_cases': _file_hash(_CONFIG / 'test_cases.json'),
    }


def _collect_current_verdicts(cases: list[dict]) -> dict:
    """Read the current verdict per case from match_result.json.

    Returns {case_id: verdict_name}, with None for cases that have no
    match_result.json yet.
    """
    out: dict = {}
    for c in cases:
        mr = _out_dir(c) / 'match_result.json'
        if mr.exists():
            with mr.open('r', encoding='utf-8') as fh:
                out[c['id']] = _verdict_name(json.load(fh))
        else:
            out[c['id']] = None
    return out


def _classify_change(before: str, after: str, rules_same: bool) -> str:
    """Classify a verdict change between baseline and current.

    Returns: unchanged | improved | regressed | rule_changed | skip
    """
    if not rules_same:
        return 'rule_changed'
    if (before is None or after is None
            or before in _SKIP_STATES or after in _SKIP_STATES):
        return 'skip'
    b, a = _CAP_RANK.get(before), _CAP_RANK.get(after)
    if b is None or a is None:
        return 'skip'
    if a > b:
        return 'improved'
    if a < b:
        return 'regressed'
    return 'unchanged'


def _extract_capability(doc: dict) -> str:
    """从 match_result.json 提取能力判定：采集通过 / 采集未通过 / 待测。

    能力判定是 baseline 的主结论（capability_detected）：
    True=IOA 具备该行为采集能力；False=不具备；无值=待测。
    """
    cap = doc.get('capability_detected')
    if cap is True:
        return '采集通过'
    if cap is False:
        return '采集未通过'
    return '待测'


def cmd_matrix(args) -> int:
    if getattr(args, 'diff', False):
        return _cmd_diff(args)
    cases = _load_cases()
    rows = []
    for c in cases:
        if args.module and c.get('module', '').lower() != args.module.lower():
            continue
        mr = _out_dir(c) / 'match_result.json'
        name = cap = cov = capability = ''
        if mr.exists():
            with mr.open('r', encoding='utf-8') as fh:
                doc = json.load(fh)
                name, cap, cov = _extract_verdict(doc)
                capability = _extract_capability(doc)
        rows.append({
            'module': c.get('module', ''),
            'case_id': c['id'],
            'action': c.get('action', ''),
            'capability': capability,
            'verdict': name,
            'coverage_status': cov,
        })

    out_path = _RUNS / 'capability_matrix.csv'
    fields = ['module', 'case_id', 'action', 'capability', 'verdict', 'coverage_status']
    with out_path.open('w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f'\nWrote {len(rows)} rows -> {out_path}\n')
    for r in rows:
        print(f'  {r["case_id"]:<20} {r["capability"] or "-":<12} {r["verdict"] or "-":<14} {r["coverage_status"] or "-"}')
    print()
    return 0


def cmd_baseline(args) -> int:
    """Snapshot the current capability verdicts into config/baseline.json.

    Manual command: you run it at a known-good point in time (e.g. after a
    full clean pass against a trusted IOA build). Never auto-updated, so the
    baseline stays a fixed reference for diff.
    """
    from collections import Counter
    cases = _load_cases()
    verdicts = _collect_current_verdicts(cases)
    fp = _compute_rule_fingerprint()
    _BASELINE.write_text(json.dumps({
        'created': datetime.now().isoformat(timespec='seconds'),
        'rule_fingerprint': fp,
        'verdicts': verdicts,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    counts = Counter(
        v for v in verdicts.values() if v and v not in _SKIP_STATES
    )
    total = sum(counts.values())
    print(f'\nBaseline saved -> {_BASELINE}')
    print(f'  fingerprint : mappings={fp["mappings"][:12]}... '
          f'test_cases={fp["test_cases"][:12]}...')
    print(f'  cases       : {len(verdicts)} total, {total} with a capability verdict')
    for k in sorted(counts, key=lambda kv: -_CAP_RANK.get(kv, -1)):
        print(f'    {k:<22} {counts[k]}')
    print()
    return 0


def _cmd_diff(args) -> int:
    from collections import Counter
    if not _BASELINE.exists():
        print('No baseline found. Run "run_all.py baseline" first '
              '(at a known-good point in time).')
        return 1
    baseline = json.loads(_BASELINE.read_text(encoding='utf-8'))
    base_verdicts = baseline.get('verdicts', {})
    base_fp = baseline.get('rule_fingerprint', {})
    cur_fp = _compute_rule_fingerprint()
    rules_same = (base_fp == cur_fp)
    cases = _load_cases()
    cur_verdicts = _collect_current_verdicts(cases)

    _TAG = {
        'regressed': 'REGRESS', 'improved': 'IMPROVE', 'unchanged': 'same',
        'rule_changed': 'RULE-CHANGED', 'skip': 'skip',
    }
    rows = []
    for c in cases:
        cid = c['id']
        before = base_verdicts.get(cid)
        after = cur_verdicts.get(cid)
        rows.append({
            'case_id': cid,
            'module':  c.get('module', ''),
            'before':  before,
            'after':   after,
            'change':  _classify_change(before, after, rules_same),
        })

    out_path = _RUNS / 'regression_diff.json'
    out_path.write_text(json.dumps({
        'created':          datetime.now().isoformat(timespec='seconds'),
        'baseline_created': baseline.get('created'),
        'rules_changed':    not rules_same,
        'rows':             rows,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    counts = Counter(r['change'] for r in rows)
    print(f'\nBaseline : {baseline.get("created", "?")}')
    rules_msg = ('unchanged' if rules_same else
                 'CHANGED since baseline - differences may be rule-driven, '
                 'review before trusting')
    print(f'Rules    : {rules_msg}')
    print('Summary  : ' + '  '.join(
        f'{k}={v}' for k, v in sorted(counts.items())
    ))
    print(f'Output   : {out_path}\n')
    for r in rows:
        if r['change'] in ('unchanged', 'skip'):
            continue
        tag = _TAG.get(r['change'], r['change'])
        print(f'  {tag:<14} {r["case_id"]:<20} '
              f'{r["before"] or "-":<24} -> {r["after"] or "-"}')
    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='run_all',
        description='Batch orchestrator for EDR telemetry validation',
    )
    sub = p.add_subparsers(dest='command', required=True)

    d = sub.add_parser('deliver', help='Batch deliver samples to VM')
    d.add_argument('--module', default=None, help='Module filter (e.g. Registry)')
    d.add_argument('--case', default=None, help='Single case id')
    d.add_argument('--resume', action='store_true', help='Skip already delivered/matched')
    d.add_argument('--no-restore', action='store_true', help='Skip snapshot restore entirely')
    d.add_argument('--shutdown-after', action='store_true',
                   help='Power off VM after each module\'s final case (clear persistent behavior)')
    d.add_argument('--dry-run', action='store_true', help='List only, do not execute')

    m = sub.add_parser('match', help='Batch match against a single IOA JSON export')
    m.add_argument('--module', default=None, help='Module filter')
    m.add_argument('--case', default=None, help='Single case id')
    m.add_argument('--json', default=None, help='Path to IOA JSON export (optional; auto-detects latest)')
    m.add_argument('--resume', action='store_true', help='Skip already matched')
    m.add_argument('--dry-run', action='store_true', help='List only')

    s = sub.add_parser('status', help='Show per-case progress')
    s.add_argument('--module', default=None, help='Module filter')

    mx = sub.add_parser('matrix', help='Aggregate match_result.json into capability_matrix.csv')
    mx.add_argument('--module', default=None, help='Module filter')
    mx.add_argument('--diff', action='store_true',
                    help='Compare current verdicts against config/baseline.json (regression check)')

    b = sub.add_parser('baseline', help='Snapshot current verdicts into config/baseline.json (manual)')

    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.command == 'deliver':
        sys.exit(cmd_deliver(args))
    elif args.command == 'match':
        sys.exit(cmd_match(args))
    elif args.command == 'status':
        sys.exit(cmd_status(args))
    elif args.command == 'matrix':
        sys.exit(cmd_matrix(args))
    elif args.command == 'baseline':
        sys.exit(cmd_baseline(args))


if __name__ == '__main__':
    main()
