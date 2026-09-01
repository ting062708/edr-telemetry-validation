"""
normalizer.py

Loads IOA event exports (JSON or CSV) and converts each row into a
canonical CanonicalEvent with UTC-aware timestamps.

JSON format (IOA native export):
    Common.EventTime  = Unix milliseconds (UTC) — no timezone conversion needed
    All field names use dot notation: Parent.FileName, Child.RegKeyPath, etc.

CSV format (IOA CSV export):
    Timestamps are in Asia/Shanghai (UTC+8) string format.
    Field names are Chinese column headers mapped via ioa_field_mapping.json.

Both formats produce the same CanonicalEvent dataclass.
Matcher receives only CanonicalEvent objects and never cares about the source.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Timezone helper ────────────────────────────────────────────────────────

try:
    from zoneinfo import ZoneInfo
    def _get_tz(name: str):
        return ZoneInfo(name)
except ImportError:
    class _FixedOffset(timezone):
        pass
    _FALLBACKS = {'Asia/Shanghai': timezone(timedelta(hours=8)), 'UTC': timezone.utc}
    def _get_tz(name: str):
        return _FALLBACKS.get(name, timezone(timedelta(hours=8)))


# ── Data model ─────────────────────────────────────────────────────────────

@dataclass
class CanonicalEvent:
    """One IOA event in a timezone-normalised, source-agnostic form."""
    event_id: str = ''
    hostname: str = ''

    event_time_utc: Optional[datetime] = None
    ingest_time_utc: Optional[datetime] = None

    event_category: str = ''   # e.g. "Reg"
    operation: str = ''        # e.g. "RegSetValue"

    actor_name: str = ''
    actor_path: str = ''
    actor_pid: Optional[int] = None
    actor_commandline: str = ''
    actor_process_uid: str = ''
    actor_md5: str = ''

    target_name: str = ''
    target_path: str = ''
    target_md5: str = ''
    target_user: str = ''
    logon_type: str = ''

    registry_path: str = ''
    registry_value_name: str = ''
    registry_value_type: str = ''
    registry_value_data: str = ''
    registry_old_value_type: str = ''
    registry_old_value_data: str = ''

    raw: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        def _fmt(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None
        return {
            'event_id':               self.event_id,
            'hostname':               self.hostname,
            'event_time_utc':         _fmt(self.event_time_utc),
            'ingest_time_utc':        _fmt(self.ingest_time_utc),
            'event_category':         self.event_category,
            'operation':              self.operation,
            'actor_name':             self.actor_name,
            'actor_path':             self.actor_path,
            'actor_pid':              self.actor_pid,
            'actor_commandline':      self.actor_commandline,
            'actor_process_uid':      self.actor_process_uid,
            'actor_md5':              self.actor_md5,
            'target_name':            self.target_name,
            'target_path':            self.target_path,
            'target_md5':             self.target_md5,
            'target_user':            self.target_user,
            'logon_type':             self.logon_type,
            'registry_path':          self.registry_path,
            'registry_value_name':    self.registry_value_name,
            'registry_value_type':    self.registry_value_type,
            'registry_value_data':    self.registry_value_data,
            'registry_old_value_type': self.registry_old_value_type,
            'registry_old_value_data': self.registry_old_value_data,
        }


# ── Helpers ────────────────────────────────────────────────────────────────

def _flatten_mapping(d: dict, out: Optional[dict] = None) -> dict:
    """Recursively flatten a nested mapping into logical-name → dot-path.

    Nested dicts are purely organisational (per-module grouping); leaf keys
    are the logical names. Keys starting with '_' are comments and skipped.
    """
    if out is None:
        out = {}
    for k, v in d.items():
        if k.startswith('_'):
            continue
        if isinstance(v, dict):
            _flatten_mapping(v, out)
        else:
            out[k] = v
    return out


def _safe_int(v) -> Optional[int]:
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def _ms_to_utc(ms) -> Optional[datetime]:
    """Convert Unix milliseconds (int or str) to UTC-aware datetime."""
    try:
        return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _parse_ioa_csv_time(raw: str, ioa_tz) -> Optional[datetime]:
    if not raw or not raw.strip():
        return None
    v = raw.strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
        try:
            naive = datetime.strptime(v, fmt)
            local = naive.replace(tzinfo=ioa_tz)
            return local.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


# ── JSON loader ────────────────────────────────────────────────────────────

def _load_json(path: Path, config_dir: Optional[Path] = None) -> tuple[list[CanonicalEvent], dict]:
    """Load IOA native JSON export. Common.EventTime is Unix ms UTC.

    config_dir (optional) supplies ioa_field_mapping.json's ``json_fields``
    (logical-name → raw dot-path). Extended fields are copied onto the event's
    ``raw`` dict under their logical name so match/expected_fields can reference
    them by name without code changes.
    """
    ext_map: dict[str, str] = {}
    if config_dir is not None:
        try:
            with (Path(config_dir) / 'ioa_field_mapping.json').open('r', encoding='utf-8') as fh:
                cfg = json.load(fh)
            jf = cfg.get('json_fields', {})
            if isinstance(jf, dict):
                ext_map = _flatten_mapping(jf)
        except Exception as exc:
            log.warning('json_fields mapping unavailable: %s', exc)

    with path.open('r', encoding='utf-8', errors='replace') as fh:
        records = json.load(fh)

    if not isinstance(records, list):
        records = [records]

    events: list[CanonicalEvent] = []
    skipped = 0

    for rec in records:
        try:
            # Merge extended fields into raw under their logical names.
            raw = dict(rec)
            for logical, dotpath in ext_map.items():
                if dotpath in rec and rec.get(dotpath) not in (None, ''):
                    raw[logical] = rec.get(dotpath)

            # Actor extraction: for ProcEvents (process creation) the acting
            # entity is the NEW process (Child.*); for everything else
            # (file/registry/network ops) it is the process that performed
            # the operation (Parent.*).
            _table = str(rec.get('@table', ''))
            if _table == 'ProcEvents':
                actor_name        = str(rec.get('Child.FileName', ''))
                actor_path        = str(rec.get('Child.FilePath', ''))
                actor_pid         = _safe_int(rec.get('Child.ProcPid'))
                actor_commandline = str(rec.get('Child.ProcCmdline', ''))
                actor_process_uid = str(rec.get('Child.ProcGuid', ''))
                actor_md5         = str(rec.get('Child.FileMd5', ''))
            else:
                actor_name        = str(rec.get('Parent.FileName', ''))
                actor_path        = str(rec.get('Parent.FilePath', ''))
                actor_pid         = _safe_int(rec.get('Parent.ProcPid'))
                actor_commandline = str(rec.get('Parent.ProcCmdline', ''))
                actor_process_uid = str(rec.get('Parent.ProcGuid', ''))
                actor_md5         = str(rec.get('Parent.FileMd5', ''))

            evt = CanonicalEvent(
                event_id          = str(rec.get('Common.EventUUId') or rec.get('Common.EventId') or ''),
                hostname          = str(rec.get('Environment.HostName', '')),
                event_time_utc    = _ms_to_utc(rec.get('Common.EventTime')),
                event_category    = str(rec.get('Action.Type', '')),
                operation         = str(rec.get('Action.Name', '')),
                actor_name        = actor_name,
                actor_path        = actor_path,
                actor_pid         = actor_pid,
                actor_commandline = actor_commandline,
                actor_process_uid = actor_process_uid,
                actor_md5         = actor_md5,
                # Target (generic) = Child.File*; LoginEvents falls back to Child.TargetUserName
                target_name       = str(rec.get('Child.FileName', '')) or str(rec.get('Child.TargetUserName', '')),
                target_path       = str(rec.get('Child.FilePath', '')),
                target_md5        = str(rec.get('Child.FileMd5', '')),
                # Account login specific
                target_user       = str(rec.get('Child.TargetUserName', '')),
                logon_type        = str(rec.get('Child.LogonType', '')),
                # Registry = Child.Reg*
                registry_path          = str(rec.get('Child.RegKeyPath', '')),
                registry_value_name    = str(rec.get('Child.RegValName', '')),
                registry_value_type    = str(rec.get('Child.RegValType', '')),
                registry_value_data    = str(rec.get('Child.RegValData', '')),
                registry_old_value_type= str(rec.get('Child.RegOldValType', '')),
                registry_old_value_data= str(rec.get('Child.RegOldValData', '')),
                raw=raw,
            )
            events.append(evt)
        except Exception as exc:
            skipped += 1
            log.warning('JSON record skipped: %s', exc)

    stats = {
        'source': 'json',
        'total_rows': len(records),
        'parsed_rows': len(events),
        'skipped_rows': skipped,
        'missing_fields': {},
    }
    log.info('JSON: loaded %d/%d events (%d skipped) from %s',
             len(events), len(records), skipped, path.name)
    return events, stats


# ── CSV loader ─────────────────────────────────────────────────────────────

def _load_mapping(config_dir: Path) -> dict:
    mapping_path = config_dir / 'ioa_field_mapping.json'
    with mapping_path.open('r', encoding='utf-8') as fh:
        return json.load(fh)


def _load_csv(path: Path, config_dir: Path) -> tuple[list[CanonicalEvent], dict]:
    """Load IOA CSV export. Timestamps are Asia/Shanghai strings."""
    mapping = _load_mapping(config_dir)
    fields   = mapping['fields']
    encoding = mapping.get('encoding', 'utf-8-sig')
    delimiter= mapping.get('delimiter', ',')
    tz_cfg   = mapping.get('timezones', {})
    ioa_tz   = _get_tz(tz_cfg.get('ioa_tz', 'Asia/Shanghai'))

    events: list[CanonicalEvent] = []
    skipped = 0
    total = 0

    def col(row: dict, key: str) -> str:
        cn = fields.get(key, '')
        return row.get(cn, '').strip() if cn else ''

    with path.open('r', encoding=encoding, newline='') as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        for row in reader:
            total += 1
            try:
                evt = CanonicalEvent(
                    event_id               = col(row, 'event_id'),
                    hostname               = col(row, 'hostname'),
                    event_time_utc         = _parse_ioa_csv_time(col(row, 'event_time'), ioa_tz),
                    ingest_time_utc        = _parse_ioa_csv_time(col(row, 'ingest_time'), ioa_tz),
                    event_category         = col(row, 'event_category'),
                    operation              = col(row, 'operation'),
                    actor_name             = col(row, 'actor_name'),
                    actor_path             = col(row, 'actor_path'),
                    actor_pid              = _safe_int(col(row, 'actor_pid')),
                    actor_commandline      = col(row, 'actor_commandline'),
                    actor_process_uid      = col(row, 'actor_process_uid'),
                    actor_md5              = col(row, 'actor_md5'),
                    target_name            = col(row, 'target_name'),
                    target_path            = col(row, 'target_path'),
                    target_md5             = col(row, 'target_md5'),
                    registry_path          = col(row, 'registry_path'),
                    registry_value_name    = col(row, 'registry_value_name'),
                    registry_value_type    = col(row, 'registry_value_type'),
                    registry_value_data    = col(row, 'registry_value_data'),
                    registry_old_value_type= col(row, 'registry_old_value_type'),
                    registry_old_value_data= col(row, 'registry_old_value_data'),
                    raw=dict(row),
                )
                events.append(evt)
            except Exception as exc:
                skipped += 1
                log.warning('CSV row %d skipped: %s', total, exc)

    # Report mapped columns absent from header
    missing = {}
    if events:
        sample_raw = events[0].raw
        for logical, chinese in fields.items():
            if chinese not in sample_raw:
                missing[logical] = chinese

    stats = {
        'source': 'csv',
        'total_rows': total,
        'parsed_rows': len(events),
        'skipped_rows': skipped,
        'missing_fields': missing,
    }
    log.info('CSV: loaded %d/%d events (%d skipped) from %s',
             len(events), total, skipped, path.name)
    return events, stats


# ── Public API ─────────────────────────────────────────────────────────────

def load_events(
    path: Path | str,
    config_dir: Optional[Path | str] = None,
) -> tuple[list[CanonicalEvent], dict]:
    """
    Auto-detect format (JSON or CSV) and return (events, stats).

    config_dir is only required for CSV; ignored for JSON.
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == '.json':
        return _load_json(p, config_dir)
    elif suffix == '.csv':
        if config_dir is None:
            raise ValueError('config_dir is required for CSV loading')
        return _load_csv(p, Path(config_dir))
    else:
        # Try JSON first, fall back to CSV
        try:
            return _load_json(p)
        except (json.JSONDecodeError, ValueError):
            if config_dir is None:
                raise ValueError('Cannot determine format and config_dir not provided')
            return _load_csv(p, Path(config_dir))
