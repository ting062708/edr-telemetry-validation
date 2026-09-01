"""audit_hashes.py — audit & fix sample EXE hashes in test_cases.json.

For each unique `program` in test_cases.json, locate the EXE under
samples_root, compute its MD5/SHA256, and compare against every case's
`sample_md5` / `sample_sha256` / `match.actor_md5`.

CLI usage (run from the automation root):
    python tools/audit_hashes.py            # report only (dry-run)
    python tools/audit_hashes.py --update   # report + write back corrected hashes

Importable API (used by the web frontend's "update sample" endpoint):
    from tools.audit_hashes import audit_and_update
    report = audit_and_update(update=True)                     # fix everything
    report = audit_and_update(update=True, programs=['ImageLoadTest.exe'])
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # tools/
ROOT = HERE.parent                                 # automation/
CONFIG = ROOT / 'config'
TEST_CASES = CONFIG / 'test_cases.json'
VM_CONFIG = CONFIG / 'vm_config.json'
# Fallback when vm_config.json is missing / has no samples_root.
DEFAULT_SAMPLES_ROOT = ROOT.parent / 'samples'


def _md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest().upper()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest().upper()


def _samples_root() -> Path:
    if VM_CONFIG.exists():
        try:
            cfg = json.loads(VM_CONFIG.read_text(encoding='utf-8-sig'))
            if cfg.get('samples_root'):
                return Path(cfg['samples_root'])
        except Exception:
            pass
    return DEFAULT_SAMPLES_ROOT


def _find_exe(root: Path, name: str) -> Path | None:
    if not root.exists():
        return None
    hits = sorted(p for p in root.rglob(name) if p.is_file())
    return hits[0] if hits else None


def audit_and_update(
    test_cases_path: Path | None = None,
    samples_root: Path | None = None,
    update: bool = False,
    programs: list[str] | None = None,
) -> dict:
    """Audit (and optionally fix) sample EXE hashes against test_cases.json.

    Returns a JSON-serialisable report::

        {
            'samples_root': str,
            'total_cases': int,
            'programs': {
                '<program>': {
                    'exe_path': str | None,
                    'md5': str | None,
                    'sha256': str | None,
                    'case_ids': [...],
                    'status': 'ok' | 'stale' | 'missing',
                    'updated_cases': [...],   # present only when update=True and stale
                },
            },
            'summary': {'ok': int, 'stale': int, 'missing': int, 'updated': int},
        }
    """
    tc_path = Path(test_cases_path) if test_cases_path else TEST_CASES
    root = Path(samples_root) if samples_root else _samples_root()
    prog_filter = set(programs) if programs else None

    data = json.loads(tc_path.read_text(encoding='utf-8-sig'))
    if isinstance(data, list):
        cases = data
    elif isinstance(data, dict):
        cases = data.get('cases', [])
    else:
        cases = []

    by_program: dict[str, list[dict]] = {}
    for c in cases:
        by_program.setdefault(c.get('program', ''), []).append(c)

    report: dict = {
        'samples_root': str(root),
        'total_cases': len(cases),
        'programs': {},
        'summary': {'ok': 0, 'stale': 0, 'missing': 0, 'updated': 0},
    }
    programs_report = report['programs']

    for prog in sorted(by_program):
        if prog_filter and prog not in prog_filter:
            continue

        prog_cases = by_program[prog]
        case_ids = [c['id'] for c in prog_cases]
        exe = _find_exe(root, prog)

        if exe is None:
            programs_report[prog] = {
                'exe_path': None,
                'md5': None,
                'sha256': None,
                'case_ids': case_ids,
                'status': 'missing',
            }
            report['summary']['missing'] += 1
            continue

        md5 = _md5(exe)
        sha = _sha256(exe)

        stale = []
        for c in prog_cases:
            m = c.get('match') or {}
            if (c.get('sample_md5') != md5
                    or c.get('sample_sha256') != sha
                    or m.get('actor_md5') != md5):
                stale.append(c)

        entry = {
            'exe_path': str(exe),
            'md5': md5,
            'sha256': sha,
            'case_ids': case_ids,
            'status': 'ok' if not stale else 'stale',
        }

        if stale:
            report['summary']['stale'] += 1
            if update:
                for c in stale:
                    c['sample_md5'] = md5
                    c['sample_sha256'] = sha
                    m = c.get('match')
                    if m is not None:
                        # actor_md5 anchors the matcher to the exact EXE; add it
                        # when missing so anchoring stays consistent.
                        m['actor_md5'] = md5
                entry['updated_cases'] = [c['id'] for c in stale]
                report['summary']['updated'] += len(stale)
        else:
            report['summary']['ok'] += 1

        programs_report[prog] = entry

    if update and report['summary']['updated']:
        tc_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )

    return report


def main() -> int:
    ap = argparse.ArgumentParser(description='Audit/fix sample EXE hashes in test_cases.json')
    ap.add_argument('--update', action='store_true', help='write back corrected hashes')
    args = ap.parse_args()

    report = audit_and_update(update=args.update)

    print(f"samples_root = {report['samples_root']}")
    print(f"total cases  = {report['total_cases']}\n")

    for prog, entry in report['programs'].items():
        status = entry['status']
        if status == 'missing':
            print(f"[MISSING] {prog}  (no EXE under {report['samples_root']})")
            continue
        if status == 'ok':
            print(f"[OK]     {prog}  ({Path(entry['exe_path']).name})  md5={entry['md5']}")
            continue
        print(f"[STALE]  {prog}  ({entry['exe_path']})")
        print(f"         actual md5={entry['md5']}")
        print(f"         actual sha={entry['sha256']}")
        if 'updated_cases' in entry:
            print(f"         updated: {', '.join(entry['updated_cases'])}")
        print()

    s = report['summary']
    print(f"Summary: {s['ok']} OK, {s['stale']} stale, {s['missing']} missing EXE")
    if args.update and s['updated']:
        print(f"Updated {s['updated']} case(s) in {TEST_CASES}")
    elif args.update:
        print('Nothing to update.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
