"""
telemetry_runner.py

CLI entry-point for EDR Telemetry validation.

Sub-commands
------------
run   – Discover sample, deliver to VM, capture stdout, then immediately
        match against a supplied IOA JSON export.

        python telemetry_runner.py run \\
            --case REG-MODIFY-001 \\
            --json  E:\\EDR\\logs\\Registry\\json\\export.json \\
            --vm-config config\\vm_config.json \\
            --out-dir runs\\Registry\\REG-MODIFY-001

match – Match a pre-captured stdout against an IOA JSON (no VM needed).

        python telemetry_runner.py match \\
            --case  REG-MODIFY-001 \\
            --stdout runs\\...\\REG-MODIFY-001_stdout.txt \\
            --json   log\\Registry\\json\\export.json

inspect-csv – Print column headers of a CSV export.

        python telemetry_runner.py inspect-csv --csv export.csv

Output files written to --out-dir (default: cwd):
  run_metadata.json       – parsed stdout fields
  normalized_events.json  – all events after normalisation
  match_result.json       – verdict + field coverage
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Fix Windows console encoding for Unicode output ───────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() in ('gbk', 'cp936', 'cp950'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() in ('gbk', 'cp936', 'cp950'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# ── ANSI colour support ────────────────────────────────────────────────────
class _C:
    RESET       = '\033[0m'
    BOLD        = '\033[1m'
    DIM         = '\033[2m'
    GREEN       = '\033[32m'
    LIGHT_GREEN = '\033[92m'
    YELLOW      = '\033[33m'
    RED         = '\033[31m'
    CYAN        = '\033[36m'
    GREY        = '\033[90m'


def _enable_windows_ansi() -> bool:
    """Enable VT escape-sequence processing on the Windows console.

    Returns True when colours can be used; False when they must be disabled.
    """
    if os.name != 'nt':
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(handle_id)
            if not handle or handle == -1:
                continue
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        return False
    return True


try:
    _COLORS_ENABLED = bool(sys.stdout.isatty()) and _enable_windows_ansi()
except Exception:
    _COLORS_ENABLED = False


def _paint(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes; returns text unchanged when colour is off."""
    if not _COLORS_ENABLED:
        return text
    active = [c for c in codes if c]
    if not active:
        return text
    return ''.join(active) + text + _C.RESET


def _verdict_paint(name: str) -> str:
    """Return ANSI codes for a verdict name ('' when disabled or unknown)."""
    if not _COLORS_ENABLED:
        return ''
    return {
        'IMPLEMENTED':           _C.BOLD + _C.LIGHT_GREEN,
        'PARTIALLY_IMPLEMENTED': _C.YELLOW,
        'NOT_IMPLEMENTED':       _C.RED,
        'PENDING':               _C.GREY,
        'VIA_WINDOWS_EVENTLOG':  _C.CYAN,
        'ERROR_SAMPLE':          _C.RED,
        'ERROR_LOG_INPUT':       _C.RED,
        'AMBIGUOUS':             _C.YELLOW,
    }.get(name, '')


def _highlight_results(text: str) -> str:
    """Colour [RESULT] PASS / FAIL lines inside sample stdout."""
    def _sub(m) -> str:
        line = m.group(0)
        if 'PASS' in line and 'FAIL' not in line:
            return _paint(line, _C.BOLD, _C.LIGHT_GREEN)
        if 'FAIL' in line:
            return _paint(line, _C.BOLD, _C.RED)
        return line
    return re.sub(r'^\[RESULT\].*$', _sub, text, flags=re.MULTILINE)


class _ColoredFormatter(logging.Formatter):
    _LEVEL_COLOURS = {
        logging.DEBUG:    _C.GREY,
        logging.INFO:     _C.GREEN,
        logging.WARNING:  _C.YELLOW,
        logging.ERROR:    _C.RED,
        logging.CRITICAL: _C.RED + _C.BOLD,
    }

    def format(self, record):
        msg = super().format(record)
        colour = self._LEVEL_COLOURS.get(record.levelno)
        if _COLORS_ENABLED and colour:
            return colour + msg + _C.RESET
        return msg


_HERE    = Path(__file__).resolve().parent
_ROOT    = _HERE.parent
_CORE    = _ROOT / 'core'
_CONFIG  = _ROOT / 'config'
_RESULTS = _ROOT.parent / 'results' / 'match_history'

for _p in (_CORE, _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from stdout_parser import parse_stdout_file, parse_stdout, parse_stdout_phases, RunMetadata
from normalizer    import load_events
from matcher       import match as do_match
from verdict       import decide, aggregate_verdicts

_handler = logging.StreamHandler()
_handler.setFormatter(_ColoredFormatter('%(levelname)s  %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_test_cases() -> dict[str, dict]:
    p = _CONFIG / 'test_cases.json'
    with p.open('r', encoding='utf-8') as fh:
        data = json.load(fh)
    return {c['id']: c for c in data.get('cases', [])}


def _load_behavior_fields(test_case: dict) -> dict:
    """Load behavior_fields from config/mappings/<module>/<CASE-ID>.json.

    Each mapping file stores stdout TARGET field name → IOA log dot-path,
    discovered by value scanning (see tools/discover_mapping.py).
    Returns {} when no mapping file exists for the case.
    """
    module = (test_case.get('module') or '').lower()
    case_id = test_case['id']
    p = _CONFIG / 'mappings' / module / f'{case_id}.json'
    if not p.exists():
        return {}
    try:
        with p.open('r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data.get('behavior_fields') or {}
    except (OSError, json.JSONDecodeError) as exc:
        log.warning('Failed to load behavior mapping %s: %s', p, exc)
        return {}


def _load_observed_fields(test_case: dict) -> list[str]:
    """Load observed_fields (IOA 采集到的业务字段清单) from the mapping file."""
    module = (test_case.get('module') or '').lower()
    case_id = test_case['id']
    p = _CONFIG / 'mappings' / module / f'{case_id}.json'
    if not p.exists():
        return []
    try:
        with p.open('r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data.get('observed_fields') or []
    except (OSError, json.JSONDecodeError) as exc:
        log.warning('Failed to load observed_fields mapping %s: %s', p, exc)
        return []


def _write_json(path: Path, obj) -> None:
    with path.open('w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    log.info('Written: %s', path)


def _write_match_result(verdict_doc: dict, case_id: str, out_dir: Path) -> None:
    """Write match result twice: an archived, timestamped copy under
    results/match_history/ (never overwritten), and a latest pointer for the frontend.
    """
    _write_json(out_dir / 'match_result.json', verdict_doc)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    _RESULTS.mkdir(parents=True, exist_ok=True)
    archive = _RESULTS / f'{case_id}_{ts}_match_result.json'
    _write_json(archive, verdict_doc)


def _resolve_vm_config(args) -> Path:
    """vm_config.json path from CLI arg, or the repo default."""
    if getattr(args, 'vm_config', None):
        return Path(args.vm_config)
    return _CONFIG / 'vm_config.json'


def _load_vm_config(vm_config_path: Path) -> dict:
    with vm_config_path.open('r', encoding='utf-8') as fh:
        return json.load(fh)


def _md5_file(path: Path) -> str:
    import hashlib
    h = hashlib.md5()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest().upper()


def _locate_sample_exe(test_case: dict, vm_config: dict):
    """Locate the host sample EXE for a case, or (None, reason)."""
    program = test_case.get('program') or test_case.get('sample_file', '')
    module  = test_case.get('module', '')
    if not program:
        return None, 'test_case missing program'
    root_cfg = (vm_config.get('samples_root')
                or vm_config.get('vm', {}).get('samples_root', ''))
    root = Path(root_cfg) if root_cfg else (_ROOT.parent / 'samples')
    # Primary: <samples_root>/<module>/<program>
    if module:
        candidate = root / module / program
        if candidate.is_file():
            return candidate, None
    # Fallback: recursive discovery
    for p in sorted(root.rglob(program)):
        if p.is_file():
            return p, None
    return None, f'sample {program!r} not found under {root}'


def _check_sample_hash(test_case: dict, vm_config: dict, args) -> int:
    """Built-in pre-run self-check: verify the sample EXE MD5 matches
    test_cases.json, auto-syncing it when stale.

    A mismatch means the sample was rebuilt/patched without updating
    test_cases.json — running would capture telemetry under a stale MD5 anchor
    and every match would silently zero out. So we auto-sync (full auto,
    built-in rule): compute the real MD5, write it back, then proceed.

    Returns 0 on pass (or after auto-sync). Only fails when the sample cannot
    be located; use --skip-hash-check to bypass the check entirely.
    """
    if getattr(args, 'skip_hash_check', False):
        log.info('--skip-hash-check: sample hash self-check skipped')
        return 0

    exe, reason = _locate_sample_exe(test_case, vm_config)
    if exe is None:
        log.error('[%s] Cannot locate sample: %s', test_case['id'], reason)
        return 1

    actual_md5 = _md5_file(exe)
    declared_md5 = (test_case.get('sample_md5') or '').strip().upper()
    actor_md5    = ((test_case.get('match') or {}).get('actor_md5') or '').strip().upper()

    if actual_md5 == declared_md5 == actor_md5:
        log.info('[%s] Sample MD5 OK: %s (%s)',
                 test_case['id'], actual_md5, exe.name)
        return 0

    # ── Built-in rule: auto-sync stale hashes, then proceed ──────────────
    if declared_md5 and actual_md5 != declared_md5:
        log.warning('[%s] Sample MD5 stale: declared=%s actual=%s (%s)',
                    test_case['id'], declared_md5, actual_md5, exe.name)
    if actor_md5 and actual_md5 != actor_md5:
        log.warning('[%s] Sample actor_md5 stale: declared=%s actual=%s (%s)',
                    test_case['id'], actor_md5, actual_md5, exe.name)
    if not declared_md5:
        log.warning('[%s] No sample_md5 declared for sample (%s)',
                    test_case['id'], exe.name)

    log.info('[%s] Auto-syncing sample MD5 %s into test_cases.json',
             test_case['id'], actual_md5)
    p = _CONFIG / 'test_cases.json'
    with p.open('r', encoding='utf-8') as fh:
        data = json.load(fh)
    for c in data.get('cases', []):
        if c['id'] == test_case['id']:
            c['sample_md5'] = actual_md5
            m = c.setdefault('match', {})
            # actor_md5 anchors the matcher; keep it in sync unless the case
            # skips process anchoring (skip_process_anchor / kernel_mode).
            if not (m.get('skip_process_anchor') or m.get('kernel_mode')):
                m['actor_md5'] = actual_md5
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                 encoding='utf-8')
    log.info('[%s] test_cases.json auto-synced (md5=%s)', test_case['id'], actual_md5)
    return 0


def _resolve_snapshot(test_case: dict, args, vm_config: dict) -> str:
    """Snapshot to restore before a run, or '' when not requested.

    Snapshot restore policy is a three-state value resolved in order:
      case-level   test_case['snapshot_policy']
      module-level vm.snapshot_policy_map[module]
      global       vm.snapshot_policy  (default 'auto')

    Policy values:
      'required' -> always restore, even with --no-restore-snapshot
      'never'    -> never restore (self-cleaning, or depends on prior run state)
      'auto'     -> restore unless --no-restore-snapshot is passed

    Which snapshot to restore (when restoring) is resolved in order:
      --snapshot CLI override  ->  test_case['snapshot']  ->
      vm.snapshot_map[module]  ->  vm.snapshot
    """
    vm = vm_config.get('vm') or {}
    module = test_case.get('module') or ''

    policy = (
        test_case.get('snapshot_policy')
        or (vm.get('snapshot_policy_map') or {}).get(module)
        or vm.get('snapshot_policy')
        or 'auto'
    )

    def _snapshot_name() -> str:
        if getattr(args, 'snapshot', None):
            return args.snapshot
        if test_case.get('snapshot'):
            return test_case['snapshot']
        snap_map = vm.get('snapshot_map') or {}
        if module in snap_map:
            return snap_map[module]
        return vm.get('snapshot') or ''

    # 1. explicit --snapshot always wins (user asked for a specific snapshot)
    if getattr(args, 'snapshot', None):
        return args.snapshot
    # 2. never -> no restore (case depends on prior in-guest state)
    if policy == 'never':
        return ''
    # 3. --no-restore-snapshot: honoured unless the case requires a clean state
    if getattr(args, 'no_restore_snapshot', False):
        if policy == 'required':
            log.warning(
                'Case %s (module %s) policy=required; ignoring --no-restore-snapshot.',
                test_case.get('id'), module,
            )
        else:
            return ''
    # 4. restore the default snapshot
    return _snapshot_name()


def _raw_logs_roots() -> list:
    """Candidate log roots, from the automation repo up to E:/EDR."""
    return [
        _ROOT.parent / 'logs',
    ]


def _collect_log_candidates(test_case: dict) -> list:
    """Collect candidate IOA JSON exports for a case, newest mtime first.

    Searches three layouts under each log root:
      (a) log/<Module>/json/*.json   (per-module exports)
      (b) log/<Module>/*.json        (flat per-module exports)
      (c) log/*.json                 (flat full-log exports)
    Files whose name contains the case id rank above others; within each
    group the most recently modified file wins. Duplicate paths (reachable
    via multiple roots) are collapsed.
    """
    module = test_case.get('module') or 'Unknown'
    case_id = test_case['id']
    mod_dir = Path(module)
    named, others = [], []
    for root in _raw_logs_roots():
        for sub in (Path(),):
            d = root / sub
            if not d.is_dir():
                continue
            for p in d.glob('*.json'):
                try:
                    mt = p.stat().st_mtime
                except OSError:
                    continue
                (named if case_id.lower() in p.name.lower() else others).append((mt, p))
    pool = named or others
    # De-duplicate by resolved path; keep the newest mtime per path.
    best: dict = {}
    for mt, p in pool:
        key = str(p)
        if key not in best or mt > best[key][0]:
            best[key] = (mt, p)
    uniq = list(best.values())
    uniq.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in uniq]


def _auto_detect_events_path(test_case: dict):
    """Auto-locate the newest IOA JSON export for a case (or None)."""
    candidates = _collect_log_candidates(test_case)
    return candidates[0] if candidates else None


def _human_size(num_bytes: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num_bytes < 1024 or unit == 'GB':
            return f'{num_bytes:.0f}{unit}' if unit == 'B' else f'{num_bytes:.1f}{unit}'
        num_bytes /= 1024.0
    return f'{num_bytes:.1f}GB'


def _human_mtime(p: Path) -> str:
    from datetime import datetime
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
    except OSError:
        return '?'


def _interactive_select_log(candidates: list, module: str):
    """Prompt the user to pick a log export from a numbered list.

    Enter  -> newest; number -> that entry; filename/path -> exact or partial
    match. Falls back to the newest on any unparseable input or EOF.
    """
    print(f'\n发现 {len(candidates)} 份 IOA 日志（log/{module}/）：')
    for i, p in enumerate(candidates, 1):
        try:
            size = _human_size(p.stat().st_size)
        except OSError:
            size = '?'
        tag = '  ← 最新' if i == 1 else ''
        print(f'  [{i}] {p.name:<58}  {_human_mtime(p)}  {size}{tag}')
    print('请输入编号 [回车=1（最新）]，或直接输入文件名/路径：')
    try:
        raw = input('> ').strip()
    except EOFError:
        raw = ''
    if not raw:
        return candidates[0]
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(candidates):
            return candidates[idx - 1]
        print(f'编号 {raw} 超出范围，使用最新。')
        return candidates[0]
    for p in candidates:
        if raw == p.name or raw == str(p):
            return p
    for p in candidates:
        if raw.lower() in p.name.lower():
            return p
    print(f'未匹配到 {raw!r}，使用最新。')
    return candidates[0]


def _resolve_events_path(test_case: dict, args):
    """Resolve the IOA events file for match.

    Explicit --json/--csv win outright. Otherwise:
      - --non-interactive -> silently pick the newest export
      - not an interactive TTY (pasted commands / script / front-end) ->
        silently pick the newest export (avoids input() swallowing the next
        pasted command)
      - a single candidate -> use it directly
      - multiple candidates on a real terminal -> interactive numbered prompt
    """
    if getattr(args, 'json', None):
        return Path(args.json)
    if getattr(args, 'csv', None):
        return Path(args.csv)
    candidates = _collect_log_candidates(test_case)
    if not candidates:
        return None
    module = test_case.get('module') or 'Unknown'
    if getattr(args, 'non_interactive', False):
        p = candidates[0]
        log.info('--non-interactive: auto-selected newest log: %s', p)
        return p
    if len(candidates) == 1:
        p = candidates[0]
        log.info('Auto-detected events file (only one): %s', p)
        return p
    if not sys.stdin.isatty():
        p = candidates[0]
        log.info('stdin is not a TTY (pasted/scripted input): auto-selected newest log: %s', p)
        return p
    return _interactive_select_log(candidates, module)


def _deliver_sample(test_case: dict, vm_config: dict, restore_snapshot: str,
                    strict_fingerprint: bool = False):
    """Discover -> deliver -> run -> capture stdout.

    Returns (RunMetadata, stdout_text); both None on failure.
    """
    # Lazy import so offline `match` usage doesn't need vmrun.
    from deliverer import Deliverer

    deliverer = Deliverer(vm_config)

    if not deliverer.ensure_vm_ready(restore_snapshot):
        log.error('Guest VM is not ready. Check that the VM is running.')
        return None, None

    stdout_text = deliverer.deliver_and_run(
        test_case, strict_fingerprint=strict_fingerprint,
    )
    if stdout_text is None:
        log.error('Sample delivery or execution failed.')
        return None, None

    runs = parse_stdout_phases(stdout_text)
    if not runs:
        runs = [parse_stdout(stdout_text)]
    log.info('stdout parsed: %d phase(s)', len(runs))
    for r in runs:
        if r.missing_fields:
            log.warning('Phase %s missing fields: %s', r.test_case_id, r.missing_fields)
    return runs, stdout_text


def _shutdown_after_if_requested(args, vm_config) -> None:
    """Soft power-off the VM when --shutdown-after is set.

    Called in a finally block so it runs even when the sample/matching
    step fails — a failed run can still leave persistent behavior behind.
    """
    if not getattr(args, 'shutdown_after', False):
        return
    from deliverer import Deliverer
    Deliverer(vm_config).shutdown_after()


def _save_stdout(stdout_text: str, out_dir: Path, case_id: str,
                run_id: str = '') -> Path:
    """Save stdout versioned by RunID, plus a latest pointer.

    - <case>_<RunID>_stdout.txt  -> immutable history, one per run
    - <case>_stdout.txt          -> latest pointer (overwritten each run)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if run_id:
        safe = re.sub(r'[^A-Za-z0-9._-]+', '_', run_id)
        hist = out_dir / f'{case_id}_{safe}_stdout.txt'
        hist.write_text(stdout_text, encoding='utf-8')
        log.info('stdout history saved: %s', hist)
    p = out_dir / f'{case_id}_stdout.txt'
    p.write_text(stdout_text, encoding='utf-8')
    log.info('stdout saved (latest): %s', p)
    return p


def _export_sysmon_log(vm_config: dict, out_dir: Path, case_id: str):
    """Export guest Sysmon events to out_dir/sysmon_<case>.evtx.

    L2 baseline evidence. Must run before the next snapshot revert (which
    happens at the start of the next run). Non-fatal: any failure logs a
    warning and continues.
    """
    try:
        from deliverer import Deliverer
        d = Deliverer(vm_config)
        return d.export_sysmon_log(out_dir, case_id)
    except Exception as exc:
        log.warning('Sysmon export failed (non-fatal): %s', exc)
        return None


def _extract_target_window(stdout_text: str) -> dict:
    """Extract the TARGET time window from stdout (multiple formats).

    The frozen samples emit one of several timestamp layouts; be lenient:
      * `[TARGET-BEGIN] TimeUTC=2026-08-24T04:45:54.298Z`  (current frozen)
      * `[TARGET-BEGIN] 2026-08-24 12:40:07`               (legacy local)
      * `[TARGET-START_TIME] 2026-08-24T04:45:54Z`          (older UTC)
    """
    txt = stdout_text or ''

    def _one(patterns):
        for pat in patterns:
            m = re.search(pat, txt, re.MULTILINE)
            if m:
                return m.group(1).strip()
        return None

    ts = r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:]+(?:\.?[0-9]*)?Z?[+-][0-9:]*|' \
         r'[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:]+'
    begin = _one([r'\[TARGET-BEGIN\]\s*TimeUTC=(\S+)',
                  r'\[TARGET-START_TIME\]\s*(\S+)',
                  r'\[TARGET-BEGIN\]\s*(' + ts + r')'])
    end = _one([r'\[TARGET-END\]\s*TimeUTC=(\S+)',
                r'\[TARGET-END_TIME\]\s*(\S+)',
                r'\[TARGET-END\]\s*(' + ts + r')'])
    m = re.search(r'Hostname=(\S+)', txt)
    return {'begin': begin, 'end': end,
            'hostname': m.group(1) if m else None}


def _write_target_window(stdout_text: str, out_dir: Path, case_id: str) -> None:
    """Persist the TARGET time window + print it for the operator.

    Lets the operator copy the exact time range when exporting the IOA cloud
    log. Non-fatal: a missing window is silently skipped.
    """
    w = _extract_target_window(stdout_text)
    if not w.get('begin'):
        return
    try:
        _write_json(out_dir / 'target_window.json', {
            'case_id': case_id,
            'hostname': w['hostname'],
            'begin': w['begin'],
            'end': w['end'],
        })
    except Exception as exc:
        log.warning('target_window.json write failed: %s', exc)
    print('\n===== 导出日志时间窗 =====')
    print('UTC  %s ~ %s' % (w['begin'], w['end']))
    print('主机 %s' % (w['hostname'] or '?'))
    print('===========================')


def _bj(dt) -> str:
    """UTC-aware datetime → Beijing time string (UTC+8), for human display."""
    if dt is None:
        return '?'
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        local = dt.astimezone(timezone(timedelta(hours=8)))
        return local.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(dt)


_TIMEUTC_RE = re.compile(r'TimeUTC=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z')


def _annotate_local_times(text: str) -> str:
    """Render every `TimeUTC=...Z` as Beijing local time, for humans.

    The stdout file and matcher keep using UTC; this only affects display.
    """
    def _sub(m):
        ts = m.group(0)[len('TimeUTC='):]
        if ts.endswith('Z'):
            ts = ts[:-1]
        try:
            dt = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            try:
                dt = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                return m.group(0)
        dt = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return _TIMEUTC_RE.sub(_sub, text)


def _print_stdout(stdout_text: str, runs, test_case: dict) -> None:
    print()
    print('=' * 62)
    print(f' Case   : {test_case["id"]} '
          f'({test_case.get("module", "?")} / {test_case.get("action", "?")})')
    if runs:
        r0 = runs[0]
        print(f' Phases : {len(runs)}')
        print(f' Sample : {getattr(r0, "sample_result", None) or "(not parsed)"} '
              f'ExitCode={getattr(r0, "exit_code", None)} '
              f'PID={getattr(r0, "pid", None)} '
              f'Host={getattr(r0, "hostname", None) or "?"}')
        for i, r in enumerate(runs, 1):
            bj = _bj(r.target_begin_utc) if r.target_begin_utc else '?'
            be = _bj(r.target_end_utc) if r.target_end_utc else '?'
            print(f'   [{i}] {r.test_case_id or "?"} {bj} → {be}')
    print('=' * 62)
    print('---- stdout (begin) ----')
    print(_highlight_results(_annotate_local_times(stdout_text.rstrip())))
    print('---- stdout (end) ----')
    print()


def _print_summary(test_case, run, match_result, verdict_result, out_dir):
    v = verdict_result
    print()
    print(f'  Case        : {test_case["id"]}')
    print(f'  Module      : {test_case.get("module", "")}')
    print(f'  Parser mode : {run.parser_mode}')
    print(f'  Sample      : {run.sample_result or "(not parsed)"}')
    print(f'  Coverage    : {match_result.coverage_status}')
    print(f'  Candidates  : {match_result.match_count}')
    _vc = _verdict_paint(v.verdict.name)
    print(f'  {v.verdict.icon}  {_paint(v.verdict.name, _vc)}', end='')
    if v.verdict.capability_state:
        print(f'  →  {v.verdict.capability_state}', end='')
    print()
    print(f'  Reason      : {v.message}')
    if v.field_coverage:
        print('  Field coverage:')
        for fc in v.field_coverage:
            icon = '✅' if fc.status == 'PASS' else ('⚠️' if fc.status == 'FAIL' else '❌')
            req  = ' [required]' if fc.required else ''
            print(f'    {icon} {fc.field}{req}  actual={fc.actual_value!r}')
    if run.degraded_match:
        print(f'  ⚠  Degraded match (missing: {run.missing_fields})')
    print()
    print(f'  Outputs: {out_dir}')
    print()


def _pick_run(runs: list[RunMetadata], case_id: str):
    """从多 phase stdout 里精确取当前 case 对应的 phase。

    行业规范 fullcycle 样本一次运行多个行为，每个 [PHASE-BEGIN] 带 TestCaseID。
    单 phase case 匹配时，必须按 TestCaseID 精确取对应 phase 的时间窗，
    而不是盲目取第一个（否则 5 个 phase 的样本会错取到别人的时间窗）。

    退化顺序：精确匹配 test_case_id → 单 run 直接返回 → 首个 run。
    """
    if not runs:
        return None
    for r in runs:
        if r.test_case_id == case_id:
            return r
    if len(runs) == 1:
        return runs[0]
    return runs[0]


def _run_match_pipeline(
    test_case: dict,
    runs: list[RunMetadata],
    events_path: Path,
    out_dir: Path,
) -> int:
    """Shared normalise → match → verdict → write pipeline.

    Supports both single-phase cases (one run, top-level match/expected_fields)
    and fullcycle cases (multiple phases, each with its own match/expected_fields).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_json(out_dir / 'run_metadata.json', [r.to_dict() for r in runs])

    # Load events
    events, stats = load_events(events_path, config_dir=_CONFIG)
    log.info(
        'Events loaded: %d total, %d parsed, source=%s',
        stats['total_rows'], stats['parsed_rows'], stats['source'],
    )
    _write_json(out_dir / 'normalized_events.json', [e.to_dict() for e in events])

    # ── Inject behavior_fields from per-case mapping file ────────────────
    bf = _load_behavior_fields(test_case)
    if bf:
        test_case['behavior_fields'] = bf
        log.info('Loaded behavior_fields from mappings/%s/%s.json: %s',
                 (test_case.get('module') or '').lower(), test_case['id'], list(bf))

    # ── observed_fields: IOA 采到的业务字段清单（采集能力佐证）──────────
    observed_fields = _load_observed_fields(test_case)

    phases = test_case.get('phases')

    # ── Single-phase path ────────────────────────────────────────────────
    if not phases:
        run = _pick_run(runs, test_case['id'])
        if run is None:
            log.error('No parsed run available')
            return 1
        match_result = do_match(run, test_case, events)
        verdict_result = decide(run, match_result, test_case, stats)
        verdict_doc = verdict_result.to_dict()
        verdict_doc.update({
            'test_case_id':   test_case['id'],
            'module':         test_case.get('module', ''),
            'action':         test_case.get('action', ''),
            'sample_result':  run.sample_result,
            'match_stats':    match_result.to_dict(),
            'parser_mode':    run.parser_mode,
            'degraded_match': run.degraded_match,
        })
        # observed_fields coverage: which business fields IOA actually filled
        # on the matched event (采集能力完整性佐证，不影响 verdict).
        if observed_fields:
            evt = verdict_result.matched_event
            obs_cov = {}
            for f in observed_fields:
                if evt is not None:
                    v = evt.raw.get(f) if evt.raw else None
                    obs_cov[f] = None if v in (None, '') else str(v)
                else:
                    obs_cov[f] = None
            verdict_doc['observed_fields'] = {
                'declared': observed_fields,
                'matched_event_coverage': obs_cov,
                'filled': sum(1 for v in obs_cov.values() if v is not None),
                'total': len(observed_fields),
            }
        _write_match_result(verdict_doc, test_case['id'], out_dir)
        _print_summary(test_case, run, match_result, verdict_result, out_dir)
        return 0

    # ── Fullcycle (multi-phase) path ─────────────────────────────────────
    # NOTE: phases run back-to-back (5-7s apart) with the SAME actor+pid.
    # The default 30s post-slack would make one phase's time window swallow
    # the next phase's events (create and modify are both RegSetValue), so
    # fullcycle phases use a tight slack window by default. Override via
    # per-phase "pre_slack_s"/"post_slack_s" in test_cases.json if needed.
    phase_results = []
    for phase in phases:
        pid = phase.get('phase_id', '')
        run = _pick_run(runs, pid) if pid else (runs[0] if runs else None)
        if run is None:
            log.warning('No matching phase stdout for %r, skipped', pid)
            continue
        phase_case = {
            'id':              phase.get('phase_id', test_case['id']),
            'module':          test_case.get('module', ''),
            'action':          phase.get('action', run.action),
            'match':           phase.get('match', {}),
            'expected_fields': phase.get('expected_fields', {}),
            'expected_result': phase.get('expected_result'),
        }
        pre_slack  = int(phase.get('pre_slack_s', 3))
        post_slack = int(phase.get('post_slack_s', 3))
        match_result = do_match(
            run, phase_case, events,
            pre_slack_s=pre_slack, post_slack_s=post_slack,
        )
        verdict_result = decide(run, match_result, phase_case, stats)
        phase_results.append({
            'phase_id':        phase.get('phase_id', ''),
            'action':          phase.get('action', ''),
            'verdict':         verdict_result.verdict.name,
            'verdict_icon':    verdict_result.verdict.icon,
            'capability_state': verdict_result.verdict.capability_state,
            'message':         verdict_result.message,
            'sample_result':   run.sample_result,
            'expected_result': verdict_result.expected,
            'as_expected':     verdict_result.as_expected,
            'field_coverage':  [fc.to_dict() for fc in verdict_result.field_coverage],
            'match_stats':     match_result.to_dict(),
        })

    overall = aggregate_verdicts(phase_results)

    verdict_doc = {
        'test_case_id':   test_case['id'],
        'module':         test_case.get('module', ''),
        'action':         test_case.get('action', ''),
        'overall_verdict':       overall['overall_verdict'],
        'overall_icon':          overall['icon'],
        'overall_capability_state': overall['capability_state'],
        'phase_count':    len(phase_results),
        'phases':         phase_results,
    }
    _write_match_result(verdict_doc, test_case['id'], out_dir)

    # Console summary
    print()
    print(f'  Case   : {test_case["id"]} (fullcycle, {len(phase_results)} phases)')
    for pr in phase_results:
        icon = pr['verdict_icon']
        _vc = _verdict_paint(pr['verdict'])
        print(f'    {icon} {pr["phase_id"]} → {_paint(pr["verdict"], _vc)}  {pr["message"]}')
    _ovc = _verdict_paint(overall['overall_verdict'])
    print(f'  {overall["icon"]}  OVERALL  {_paint(overall["overall_verdict"], _ovc)}'
          f'  →  {overall["capability_state"]}')
    print(f'  Outputs: {out_dir}')
    print()
    return 0


# ── Sub-command: run ───────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> int:
    """Deliver sample to VM, capture stdout, then optionally match an IOA log."""
    cases = _load_test_cases()
    if args.case not in cases:
        log.error('Unknown case %r. Available: %s', args.case, list(cases))
        return 1
    test_case = cases[args.case]

    vm_config_path = _resolve_vm_config(args)
    if not vm_config_path.exists():
        log.error('VM config not found: %s', vm_config_path)
        return 1
    vm_config = _load_vm_config(vm_config_path)

    out_dir = Path(args.out_dir) if args.out_dir else (
        _ROOT.parent / 'results' / 'runs' / test_case.get('module', 'Unknown') / test_case['id']
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    restore_snapshot = _resolve_snapshot(test_case, args, vm_config)

    # Hard pre-run gate: sample MD5 must match test_cases.json before delivery.
    if _check_sample_hash(test_case, vm_config, args) != 0:
        return 1

    runs, stdout_text = _deliver_sample(
        test_case, vm_config, restore_snapshot,
        strict_fingerprint=args.strict_fingerprint,
    )
    try:
        if runs is None or stdout_text is None:
            return 1

        stdout_file = _save_stdout(stdout_text, out_dir, test_case['id'],
                                    runs[0].run_id if runs else '')
        _write_json(out_dir / 'run_metadata.json', [r.to_dict() for r in runs])
        _print_stdout(stdout_text, runs, test_case)

        # L2 baseline: export guest Sysmon events before the next snapshot
        # revert (which happens at the start of the next run) wipes them.
        _export_sysmon_log(vm_config, out_dir, test_case['id'])
        _write_target_window(stdout_text, out_dir, test_case['id'])

        # Events
        if not args.json and not args.csv:
            log.info(
                'No --json/--csv provided. stdout + run_metadata saved to %s. '
                'After exporting the IOA log, run: '
                'python telemetry_runner.py match --case %s --stdout %s'
                '  (--json optional; auto-detects the latest export)',
                out_dir, test_case['id'], stdout_file,
            )
            return 0

        events_path = Path(args.json) if args.json else Path(args.csv)
        if not events_path.exists():
            log.error('Events file not found: %s', events_path)
            return 1

        return _run_match_pipeline(test_case, runs, events_path, out_dir)
    finally:
        _shutdown_after_if_requested(args, vm_config)


# ── Sub-command: deliver ───────────────────────────────────────────────────

def cmd_deliver(args: argparse.Namespace) -> int:
    """Deliver sample to VM, run it, capture and print stdout (no log match)."""
    cases = _load_test_cases()
    if args.case not in cases:
        log.error('Unknown case %r. Available: %s', args.case, list(cases))
        return 1
    test_case = cases[args.case]

    vm_config_path = _resolve_vm_config(args)
    if not vm_config_path.exists():
        log.error('VM config not found: %s', vm_config_path)
        return 1
    vm_config = _load_vm_config(vm_config_path)

    out_dir = Path(args.out_dir) if args.out_dir else (
        _ROOT.parent / 'results' / 'runs' / test_case.get('module', 'Unknown') / test_case['id']
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    restore_snapshot = _resolve_snapshot(test_case, args, vm_config)

    # Hard pre-run gate: sample MD5 must match test_cases.json before delivery.
    if _check_sample_hash(test_case, vm_config, args) != 0:
        return 1

    runs, stdout_text = _deliver_sample(
        test_case, vm_config, restore_snapshot,
        strict_fingerprint=args.strict_fingerprint,
    )
    try:
        if runs is None or stdout_text is None:
            return 1

        stdout_file = _save_stdout(stdout_text, out_dir, test_case['id'],
                                    runs[0].run_id if runs else '')
        _write_json(out_dir / 'run_metadata.json', [r.to_dict() for r in runs])
        _print_stdout(stdout_text, runs, test_case)

        # L2 baseline: export guest Sysmon events before the next snapshot
        # revert (which happens at the start of the next run) wipes them.
        _export_sysmon_log(vm_config, out_dir, test_case['id'])
        _write_target_window(stdout_text, out_dir, test_case['id'])

        log.info(
            'Delivered. After exporting the IOA log, run: '
            'python telemetry_runner.py match --case %s --stdout %s'
            '  (--json optional; auto-detects the latest export)',
            test_case['id'], stdout_file,
        )
        return 0
    finally:
        _shutdown_after_if_requested(args, vm_config)


# ── Sub-command: match ─────────────────────────────────────────────────────

def cmd_match(args: argparse.Namespace) -> int:
    """Match a pre-captured stdout against an IOA log (no VM needed)."""
    cases = _load_test_cases()
    if args.case not in cases:
        log.error('Unknown case %r. Available: %s', args.case, list(cases))
        return 1
    test_case = cases[args.case]

    stdout_path = Path(args.stdout)
    if not stdout_path.exists():
        log.error('stdout file not found: %s', stdout_path)
        return 1

    stdout_text = stdout_path.read_text(encoding='utf-8', errors='replace')
    runs = parse_stdout_phases(stdout_text)
    if not runs:
        runs = [parse_stdout(stdout_text)]
    log.info('stdout parsed: %d phase(s)', len(runs))
    for r in runs:
        if r.missing_fields:
            log.warning('Phase %s missing fields: %s', r.test_case_id, r.missing_fields)

    events_path = _resolve_events_path(test_case, args)
    if events_path is None:
        log.error(
            'No --json/--csv provided and no IOA export found under log/%s/.',
            test_case.get('module', 'Unknown'),
        )
        return 1
    if not events_path.exists():
        log.error('Events file not found: %s', events_path)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else Path.cwd()
    return _run_match_pipeline(test_case, runs, events_path, out_dir)


# ── Sub-command: inspect-csv ───────────────────────────────────────────────

def cmd_inspect_csv(args: argparse.Namespace) -> int:
    import csv as _csv
    p = Path(args.csv)
    if not p.exists():
        log.error('File not found: %s', p)
        return 1
    with p.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = _csv.DictReader(fh)
        headers = reader.fieldnames or []
        rows = list(reader)
    print(f'\nFile   : {p.name}')
    print(f'Rows   : {len(rows)}')
    print(f'Columns: {len(headers)}')
    for i, h in enumerate(headers, 1):
        print(f'  {i:3d}. {h}')
    print()
    return 0


# ── CLI ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='telemetry_runner',
        description='EDR Telemetry Validation Runner',
    )
    sub = p.add_subparsers(dest='command', required=True)

    # run
    r = sub.add_parser('run', help='Deliver sample to VM + match IOA log')
    r.add_argument('--case',      required=True, help='Test case ID, e.g. REG-MODIFY-001')
    r.add_argument('--json',      default=None,  help='Path to IOA JSON export')
    r.add_argument('--csv',       default=None,  help='Path to IOA CSV export')
    r.add_argument('--vm-config', default=None,  help='Path to vm_config.json (default: config/vm_config.json)')
    r.add_argument('--out-dir',   default=None,  help='Output directory')
    r.add_argument('--snapshot',  default=None,  help='Snapshot to restore (default: config vm.snapshot)')
    r.add_argument('--no-restore-snapshot', action='store_true',
                   help='Skip automatic snapshot restore')
    r.add_argument('--strict-fingerprint', action='store_true',
                   help='Abort delivery on sample fingerprint mismatch (default: warn only)')
    r.add_argument('--skip-hash-check', action='store_true',
                   help='Skip the pre-run sample MD5 self-check (not recommended)')
    r.add_argument('--shutdown-after', action='store_true',
                   help='Soft power-off the VM after the run (clear persistent behavior)')

    # deliver
    d = sub.add_parser('deliver', help='Deliver sample to VM, run it, print stdout (no log match)')
    d.add_argument('--case',      required=True, help='Test case ID, e.g. REG-MODIFY-001')
    d.add_argument('--vm-config', default=None,  help='Path to vm_config.json (default: config/vm_config.json)')
    d.add_argument('--out-dir',   default=None,  help='Output directory')
    d.add_argument('--snapshot',  default=None,  help='Snapshot to restore (default: config vm.snapshot)')
    d.add_argument('--no-restore-snapshot', action='store_true',
                   help='Skip automatic snapshot restore')
    d.add_argument('--strict-fingerprint', action='store_true',
                   help='Abort delivery on sample fingerprint mismatch (default: warn only)')
    d.add_argument('--skip-hash-check', action='store_true',
                   help='Skip the pre-run sample MD5 self-check (not recommended)')
    d.add_argument('--shutdown-after', action='store_true',
                   help='Soft power-off the VM after delivery (clear persistent behavior)')

    # match
    m = sub.add_parser('match', help='Match pre-captured stdout against IOA log')
    m.add_argument('--case',    required=True, help='Test case ID')
    m.add_argument('--stdout',  required=True, help='Path to sample stdout .txt')
    m.add_argument('--json',    default=None,  help='Path to IOA JSON export')
    m.add_argument('--csv',     default=None,  help='Path to IOA CSV export')
    m.add_argument('--non-interactive', action='store_true',
                   help='Silently auto-select the newest log export (no prompt)')
    m.add_argument('--out-dir', default=None,  help='Output directory (default: cwd)')

    # inspect-csv
    ic = sub.add_parser('inspect-csv', help='Inspect CSV column headers')
    ic.add_argument('--csv', required=True)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == 'run':
        sys.exit(cmd_run(args))
    elif args.command == 'deliver':
        sys.exit(cmd_deliver(args))
    elif args.command == 'match':
        sys.exit(cmd_match(args))
    elif args.command == 'inspect-csv':
        sys.exit(cmd_inspect_csv(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
