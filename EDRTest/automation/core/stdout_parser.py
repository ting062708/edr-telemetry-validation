"""
stdout_parser.py

Parses structured stdout from Lifecycle test executables.

Supports two formats:

CURRENT (frozen protocol):
    [RUN-BEGIN] RunID=<id> TimeUTC=<iso>
    [META] TestCaseID=<id> Module=<name> Action=<action>
    [META] Process=<exe> PID=<pid> Hostname=<host>
    [SETUP-BEGIN] TimeUTC=<iso>
    [SETUP] Key=Value
    [SETUP-END] TimeUTC=<iso>
    [TARGET-BEGIN] TimeUTC=<iso>
    [TARGET] Key=Value
    [TARGET-END] TimeUTC=<iso>
    [RESULT] PASS|FAIL ExitCode=<n>
    [RUN-END] RunID=<id> TimeUTC=<iso>

LEGACY (backward compat, read-only):
    [PHASE-BEGIN] <phase-name>
    [TELEMETRY] ...
    [TIME] <timestamp>
    [INFO] ...
    [PHASE-END] <phase-name>
    RESULT PASS / FAIL / [RESULT] PASS|FAIL

Legacy stdout will be parsed on a best-effort basis.
Missing fields are set to None and recorded in missing_fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_KV_RE = re.compile(r'(\w+)=((?:[^\s=]+(?:\s+[^\s=]+)*?)(?=\s+\w+=|$))')


def _parse_kv(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in _KV_RE.finditer(text)}


def _parse_utc(value: str) -> Optional[datetime]:
    """Parse a UTC ISO-8601 string into an aware UTC datetime.

    Handles both 'fffZ' (e.g. 2026-08-22T03:44:47.899Z) and
    round-trip 'o' format (e.g. 2026-08-22T03:44:47.8996781+00:00).
    """
    if not value:
        return None
    v = value.strip()
    # Strip trailing 'Z'
    if v.endswith('Z'):
        v = v[:-1]
    # Strip trailing numeric offset like '+00:00' / '-05:30'
    m = re.search(r'[+-]\d{2}:\d{2}$', v)
    if m:
        v = v[:m.start()]
    # Truncate fractional seconds to 6 digits (strptime %f max)
    if '.' in v:
        head, frac = v.split('.', 1)
        v = head + '.' + frac[:6]
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_local_plus8(value: str) -> Optional[datetime]:
    """
    Parse a +08:00 local timestamp string (legacy format) and convert to UTC.
    Handles: '2026-08-20 10:54:24.796 +08:00'
    """
    if not value:
        return None
    v = value.strip()
    # Drop trailing timezone token and parse
    patterns = [
        ('%Y-%m-%d %H:%M:%S.%f +08:00', timedelta(hours=8)),
        ('%Y-%m-%d %H:%M:%S +08:00',     timedelta(hours=8)),
        ('%Y-%m-%dT%H:%M:%S.%f+08:00',   timedelta(hours=8)),
        ('%Y-%m-%dT%H:%M:%S+08:00',       timedelta(hours=8)),
    ]
    for fmt, offset in patterns:
        try:
            naive = datetime.strptime(v, fmt)
            tz = timezone(offset)
            local = naive.replace(tzinfo=tz)
            return local.astimezone(timezone.utc)
        except ValueError:
            continue
    # Last attempt: strip tz suffix and treat as naive UTC
    v2 = re.sub(r'\s*[+-]\d{2}:\d{2}$', '', v).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(v2, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RunMetadata:
    run_id: str = ''
    test_case_id: str = ''
    module: str = ''
    action: str = ''
    process_name: str = ''
    pid: Optional[int] = None
    hostname: str = ''

    run_start_utc: Optional[datetime] = None
    setup_begin_utc: Optional[datetime] = None
    setup_end_utc: Optional[datetime] = None
    target_begin_utc: Optional[datetime] = None
    target_end_utc: Optional[datetime] = None
    run_end_utc: Optional[datetime] = None

    setup_lines: list[str] = field(default_factory=list)
    target_fields: dict[str, str] = field(default_factory=dict)

    sample_result: str = ''      # PASS | FAIL | (empty)
    exit_code: Optional[int] = None
    error_lines: list[str] = field(default_factory=list)

    # Parser diagnostics
    parser_mode: str = 'current'           # 'current' | 'legacy_phase'
    missing_fields: list[str] = field(default_factory=list)
    degraded_match: bool = False           # True when key match fields absent

    raw_meta: dict[str, str] = field(default_factory=dict)

    @property
    def sample_ok(self) -> bool:
        return self.sample_result == 'PASS'

    @property
    def target_window(self) -> tuple[Optional[datetime], Optional[datetime]]:
        return self.target_begin_utc, self.target_end_utc

    def to_dict(self) -> dict:
        def _fmt(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None
        return {
            'test_case_id':      self.test_case_id,
            'run_id':            self.run_id or None,
            'module':            self.module or None,
            'action':            self.action or None,
            'process_name':      self.process_name or None,
            'pid':               self.pid,
            'hostname':          self.hostname or None,
            'run_start_utc':     _fmt(self.run_start_utc),
            'setup_begin_utc':   _fmt(self.setup_begin_utc),
            'setup_end_utc':     _fmt(self.setup_end_utc),
            'target_begin_utc':  _fmt(self.target_begin_utc),
            'target_end_utc':    _fmt(self.target_end_utc),
            'run_end_utc':       _fmt(self.run_end_utc),
            'sample_result':     self.sample_result or None,
            'exit_code':         self.exit_code,
            'parser_mode':       self.parser_mode,
            'missing_fields':    self.missing_fields,
            'degraded_match':    self.degraded_match,
            'target_fields':     self.target_fields,
            'error_lines':       self.error_lines,
        }


# ---------------------------------------------------------------------------
# Current-protocol parser
# ---------------------------------------------------------------------------

def _parse_current(lines: list[str]) -> RunMetadata:
    md = RunMetadata(parser_mode='current')
    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if line.startswith('[RUN-BEGIN]'):
            kv = _parse_kv(line[len('[RUN-BEGIN]'):].strip())
            md.run_id = kv.get('RunID', '')
            md.run_start_utc = _parse_utc(kv.get('TimeUTC', ''))

        elif line.startswith('[META]'):
            kv = _parse_kv(line[len('[META]'):].strip())
            md.raw_meta.update(kv)
            if 'TestCaseID' in kv:  md.test_case_id = kv['TestCaseID']
            if 'Module'     in kv:  md.module       = kv['Module']
            if 'Action'     in kv:  md.action       = kv['Action']
            if 'Process'    in kv:  md.process_name = kv['Process']
            if 'Hostname'   in kv:  md.hostname     = kv['Hostname']
            if 'PID'        in kv:
                try: md.pid = int(kv['PID'])
                except ValueError: pass
            if 'RunStartUTC' in kv:
                md.run_start_utc = _parse_utc(kv['RunStartUTC'])
            if 'StartTimeUTC' in kv:
                md.run_start_utc = _parse_utc(kv['StartTimeUTC'])
            if 'RunID' in kv:
                md.run_id = kv['RunID']

        elif line.startswith('[PHASE-BEGIN]'):
            kv = _parse_kv(line[len('[PHASE-BEGIN]'):].strip())
            if 'TestCaseID' in kv and not md.test_case_id:
                md.test_case_id = kv['TestCaseID']

        elif line.startswith('[PHASE-END]'):
            kv = _parse_kv(line[len('[PHASE-END]'):].strip())
            status = kv.get('Status', '')
            if status and not md.sample_result:
                md.sample_result = status.upper()

        elif line.startswith('[SETUP-BEGIN]'):
            kv = _parse_kv(line[len('[SETUP-BEGIN]'):].strip())
            md.setup_begin_utc = _parse_utc(kv.get('TimeUTC', ''))

        elif line.startswith('[SETUP]'):
            md.setup_lines.append(line[len('[SETUP]'):].strip())

        elif line.startswith('[SETUP-END]'):
            kv = _parse_kv(line[len('[SETUP-END]'):].strip())
            md.setup_end_utc = _parse_utc(kv.get('TimeUTC', ''))

        elif line.startswith('[TARGET-BEGIN]'):
            kv = _parse_kv(line[len('[TARGET-BEGIN]'):].strip())
            md.target_begin_utc = _parse_utc(kv.get('TimeUTC', ''))

        elif line.startswith('[TARGET]'):
            body = line[len('[TARGET]'):].strip()
            eq = body.find('=')
            if eq != -1:
                md.target_fields[body[:eq].strip()] = body[eq+1:].strip()

        elif line.startswith('[TARGET-END]'):
            kv = _parse_kv(line[len('[TARGET-END]'):].strip())
            md.target_end_utc = _parse_utc(kv.get('TimeUTC', ''))

        elif line.startswith('[RESULT]'):
            body = line[len('[RESULT]'):].strip()
            parts = body.split()
            if parts:
                md.sample_result = parts[0]
            kv = _parse_kv(body)
            if 'ExitCode' in kv:
                try: md.exit_code = int(kv['ExitCode'])
                except ValueError: pass

        elif line.startswith('[ERROR]'):
            md.error_lines.append(line[len('[ERROR]'):].strip())

        elif line.startswith('[RUN-END]'):
            kv = _parse_kv(line[len('[RUN-END]'):].strip())
            md.run_end_utc = _parse_utc(kv.get('TimeUTC', ''))

    # Sanity check: TARGET window must be forward in time.
    # A TARGET-END earlier than TARGET-BEGIN means the stdout file is
    # corrupted / hand-merged or the VM clock jumped backwards; using such
    # a window for matching would silently produce wrong results.
    if (md.target_begin_utc and md.target_end_utc
            and md.target_end_utc < md.target_begin_utc):
        md.error_lines.append(
            'target window invalid: end before begin '
            f'({md.target_begin_utc.isoformat()} -> {md.target_end_utc.isoformat()})'
        )
        md.target_end_utc = None

    # Record missing key fields
    missing = []
    if not md.pid:           missing.append('pid')
    if not md.hostname:      missing.append('hostname')
    if not md.run_id:        missing.append('run_id')
    if not md.target_begin_utc: missing.append('target_begin_utc')
    if not md.target_end_utc:   missing.append('target_end_utc')
    md.missing_fields = missing
    if missing:
        md.degraded_match = True
    return md


# ---------------------------------------------------------------------------
# Legacy [PHASE-BEGIN] parser
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\s*[+-]\d{2}:\d{2})?)'
)

_HEADER_KV_RE = re.compile(r'^([A-Za-z][\w ]*?)\s*:\s*(.+)$')


def _parse_legacy(lines: list[str]) -> RunMetadata:
    """
    Best-effort parse of the legacy [PHASE-BEGIN]/[TIME]/[INFO] format.

    Also parses the plain header block that precedes the phases, e.g.:
        Module    : Registry
        Process   : RegistryLifecycleTest.exe
        PID       : 14024
        Start     : 2026-08-20 10:54:24.785 +08:00
        Target    : HKCU\\Software\\EDRTelemetryTest

    Hostname and RunID are still not available in legacy stdout — set to None.
    If no [RESULT]/RESULT line and no [ERROR] appears, sample_result is left
    empty (never fabricated) and 'sample_result' is added to missing_fields.
    """
    md = RunMetadata(parser_mode='legacy_phase')

    all_times: list[datetime] = []
    current_phase: str = ''
    phase_times: dict[str, list[datetime]] = {}
    result_str = ''
    result_seen = False
    in_header = True  # header block ends at the first bracket tag

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # Skip decorative separator lines
        if set(line) <= {'=', '-'}:
            continue

        # ── Header key:value block (before any bracket tag) ───────────
        if in_header and not line.startswith('['):
            m = _HEADER_KV_RE.match(line)
            if m:
                key = m.group(1).strip().lower()
                val = m.group(2).strip()
                if key == 'module':
                    md.module = val
                elif key == 'process':
                    md.process_name = val
                elif key == 'pid':
                    try:
                        md.pid = int(val)
                    except ValueError:
                        pass
                elif key == 'start':
                    dt = _parse_local_plus8(val)
                    if dt:
                        md.run_start_utc = dt
                        all_times.append(dt)
                elif key in ('hostname', 'host', 'computer', 'computername'):
                    md.hostname = val
                # 'target' is informational only; not used for matching
                continue

        if line.startswith('['):
            in_header = False

        # [PHASE-BEGIN] REG-CREATE-001
        if line.startswith('[PHASE-BEGIN]'):
            current_phase = line[len('[PHASE-BEGIN]'):].strip()
            phase_times[current_phase] = []

        elif line.startswith('[PHASE-END]'):
            current_phase = ''

        elif line.startswith('[TIME]'):
            ts_raw = line[len('[TIME]'):].strip()
            dt = _parse_local_plus8(ts_raw)
            if dt:
                all_times.append(dt)
                if current_phase:
                    phase_times.setdefault(current_phase, []).append(dt)

        elif line.startswith('[TELEMETRY]'):
            body = line[len('[TELEMETRY]'):].strip()
            # Try to extract module/action hint
            low = body.lower()
            if 'registry' in low:
                md.module = 'Registry'
            if 'create' in low:
                md.action = 'create'
            elif 'modif' in low:
                md.action = 'modify'
            elif 'delet' in low:
                md.action = 'delete'

        elif line.startswith('[INFO]'):
            md.setup_lines.append(line[len('[INFO]'):].strip())

        elif line.startswith('[RESULT]') or line.startswith('RESULT'):
            body = re.sub(r'^\[RESULT\]\s*', '', line)
            body = re.sub(r'^RESULT\s*', '', body).strip()
            parts = body.split()
            if parts:
                result_str = parts[0]

        elif line.startswith('[ERROR]'):
            md.error_lines.append(line[len('[ERROR]'):].strip())
            if not result_str:
                result_str = 'FAIL'

        elif line.startswith('[END]'):
            ts_raw = line[len('[END]'):].strip()
            dt = _parse_local_plus8(ts_raw)
            if dt:
                all_times.append(dt)
                md.run_end_utc = dt

        # Also catch inline RESULT on own line
        elif re.match(r'^(PASS|FAIL)\s*$', line, re.IGNORECASE):
            if not result_str:
                result_str = line.strip().upper()

    md.sample_result = result_str if result_str else ''

    # Approximate run start
    if all_times:
        md.run_start_utc = min(all_times)

    # Try to set TARGET window from the phase that looks like the main action
    # Legacy format has only one phase per run (REG-CREATE-001 etc.)
    # Use all phase times as the TARGET window
    if phase_times:
        # Pick the first (and usually only) phase
        first_phase_key = next(iter(phase_times))
        pts = phase_times[first_phase_key]
        md.test_case_id = first_phase_key
        if pts:
            md.target_begin_utc = min(pts)
            md.target_end_utc   = max(pts)
        # If only one timestamp, use it as both begin and end
        if md.target_begin_utc and not md.target_end_utc:
            md.target_end_utc = md.target_begin_utc
    elif all_times:
        # Fallback: use full run range
        md.target_begin_utc = min(all_times)
        md.target_end_utc   = max(all_times)

    # Record missing fields
    missing = ['pid', 'hostname', 'run_id']
    if not md.target_begin_utc: missing.append('target_begin_utc')
    if not md.target_end_utc:   missing.append('target_end_utc')
    md.missing_fields = missing
    md.degraded_match = True  # legacy always degraded
    return md


# ---------------------------------------------------------------------------
# Auto-detect and dispatch
# ---------------------------------------------------------------------------

def _is_current_protocol(lines: list[str]) -> bool:
    for line in lines:
        if line.strip().startswith('[RUN-BEGIN]') or line.strip().startswith('[META]'):
            return True
    return False


def parse_stdout(text: str) -> RunMetadata:
    lines = text.splitlines()
    if _is_current_protocol(lines):
        return _parse_current(lines)
    else:
        return _parse_legacy(lines)


def parse_stdout_phases(text: str) -> list[RunMetadata]:
    """Parse stdout into one or more RunMetadata objects.

    A fullcycle stdout contains multiple [RUN-BEGIN]...[RUN-END] blocks
    (one per phase); a single-action stdout contains exactly one. Split on
    RUN-BEGIN/RUN-END boundaries and return one RunMetadata per block.

    Newer "single-RUN multi-PHASE" format (e.g. RegistryLifecycleTest
    fullcycle) has ONE [RUN-BEGIN]...[RUN-END] block that internally
    contains [PHASE-BEGIN]...[PHASE-END] sections. When detected, each
    PHASE section is parsed as its own run, inheriting the global
    RUN/META header lines.

    Legacy-format stdout yields a single element.
    """
    lines = text.splitlines()
    if not _is_current_protocol(lines):
        return [parse_stdout(text)]

    # New format: single RUN block with internal PHASE sections.
    if any(s.startswith('[PHASE-BEGIN]') for s in lines):
        return _parse_single_run_phases(lines)

    # Legacy current-format: multiple RUN blocks.
    blocks: list[list[str]] = []
    current: list[str] = []
    depth = 0
    for line in lines:
        s = line.strip()
        if s.startswith('[RUN-BEGIN]'):
            current = [line]
            depth = 1
        elif s.startswith('[RUN-END]'):
            if current:
                current.append(line)
                blocks.append(current)
                current = []
            depth = 0
        elif depth:
            current.append(line)

    if not blocks:
        return [parse_stdout(text)]
    return [_parse_current(b) for b in blocks]


def _parse_single_run_phases(lines: list[str]) -> list[RunMetadata]:
    """Split a single-RUN multi-PHASE stdout into per-phase runs.

    Global header lines ([RUN-BEGIN] / [META] / [RESULT] / [RUN-END])
    are attached to every phase; phase-local lines are grouped by
    [PHASE-BEGIN]...[PHASE-END] boundaries.
    """
    header: list[str] = []
    phases: list[list[str]] = []
    current: list[str] = []
    in_phase = False

    for line in lines:
        s = line.strip()
        if s.startswith('[PHASE-BEGIN]'):
            if in_phase and current:
                phases.append(current)
            current = [line]
            in_phase = True
        elif s.startswith('[PHASE-END]'):
            if in_phase:
                current.append(line)
                phases.append(current)
                current = []
                in_phase = False
        elif in_phase:
            current.append(line)
        else:
            header.append(line)

    if in_phase and current:
        phases.append(current)

    if not phases:
        return [parse_stdout('\n'.join(lines))]

    runs = []
    for ph in phases:
        runs.append(_parse_current(header + ph))
    return runs


def parse_stdout_file(path) -> RunMetadata:
    p = Path(path)
    text = p.read_text(encoding='utf-8', errors='replace')
    return parse_stdout(text)
