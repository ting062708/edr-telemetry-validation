"""
verdict.py

Five-state verdict system aligned with EDR capability matrix:

    ✅ IMPLEMENTED            – event found, all required + expected fields match
    ⚠️  PARTIALLY_IMPLEMENTED – event found, but ≥1 required field missing/empty
    ❌ NOT_IMPLEMENTED        – log covers window, zero matching events
    ❓ PENDING                – no run data (no stdout / no log)
    🪵 VIA_WINDOWS_EVENTLOG   – not in IOA; found in Windows evtx (external signal)

Internal error states (not capability states):
    ERROR_SAMPLE             – sample did not execute successfully
    ERROR_LOG_INPUT          – log empty, unreadable, or does not cover TARGET window
    AMBIGUOUS                – multiple candidates, cannot uniquely identify
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from matcher import MatchResult
from normalizer import CanonicalEvent
from stdout_parser import RunMetadata


class Verdict(Enum):
    # ── Capability states (appear in final report) ─────────────────────────
    IMPLEMENTED             = auto()   # ✅
    PARTIALLY_IMPLEMENTED   = auto()   # ⚠️
    NOT_IMPLEMENTED         = auto()   # ❌
    PENDING                 = auto()   # ❓
    VIA_WINDOWS_EVENTLOG    = auto()   # 🪵

    # ── Operational error states ───────────────────────────────────────────
    ERROR_SAMPLE            = auto()
    ERROR_LOG_INPUT         = auto()
    AMBIGUOUS               = auto()

    @property
    def icon(self) -> str:
        _icons = {
            'IMPLEMENTED':           '✅',
            'PARTIALLY_IMPLEMENTED': '⚠️',
            'NOT_IMPLEMENTED':       '❌',
            'PENDING':               '❓',
            'VIA_WINDOWS_EVENTLOG':  '🪵',
            'ERROR_SAMPLE':          '🔴',
            'ERROR_LOG_INPUT':       '🔴',
            'AMBIGUOUS':             '🟡',
        }
        return _icons.get(self.name, '?')

    @property
    def capability_state(self) -> Optional[str]:
        """Return the human-readable capability matrix label, or None for error states."""
        _labels = {
            'IMPLEMENTED':           'Implemented',
            'PARTIALLY_IMPLEMENTED': 'Partially Implemented',
            'NOT_IMPLEMENTED':       'Not Implemented',
            'PENDING':               'Pending Response',
            'VIA_WINDOWS_EVENTLOG':  'Via Windows EventLogs',
        }
        return _labels.get(self.name)


@dataclass
class FieldCoverageResult:
    """Per-field match result for a single event."""
    field: str
    required: bool
    rule: dict                    # the rule from expected_fields
    actual_value: Optional[str]   # value from the matched event
    status: str                   # PASS | FAIL | MISSING_IN_EVENT | MISSING_IN_CONFIG

    def to_dict(self) -> dict:
        return {
            'field':         self.field,
            'required':      self.required,
            'rule':          self.rule,
            'actual_value':  self.actual_value,
            'status':        self.status,
        }


@dataclass
class VerdictResult:
    verdict: Verdict
    message: str
    matched_event: Optional[CanonicalEvent] = None
    field_coverage: list[FieldCoverageResult] = field(default_factory=list)
    # Expected-result annotation (from test_cases.json "expected_result").
    # e.g. "not_implemented" means the case documents an IOA capability gap.
    expected: Optional[str] = None

    # ── 能力维度（主结论） ────────────────────────────────────────────
    # capability_detected: 日志里是否存在该行为类型的事件（不看进程锚定）。
    #   True  → IOA 具备采集该行为的能力
    #   False → IOA 不具备该行为类型的采集能力
    # anchor_detected: 是否锚定到了样本进程（辅助证据，非主结论）。
    # anomaly: capability_detected=True 但 anchor_detected=False 时，
    #          记录「异常采集现象」（进程信任过滤 / 路径排除 / 待验证）。
    capability_detected: Optional[bool] = None
    anchor_detected: Optional[bool] = None
    anomaly: Optional[str] = None
    value_scan: dict = field(default_factory=dict)

    @property
    def as_expected(self) -> bool:
        """True when the actual verdict matches the declared expected_result."""
        if not self.expected:
            return False
        return self.expected.strip().lower() == self.verdict.name.lower()

    @property
    def missing_required_fields(self) -> list[str]:
        return [
            fc.field for fc in self.field_coverage
            if fc.required and fc.status != 'PASS'
        ]

    @property
    def partial_fields(self) -> list[str]:
        """Fields that exist in event but failed the value check."""
        return [
            fc.field for fc in self.field_coverage
            if fc.status == 'FAIL'
        ]

    def to_dict(self) -> dict:
        return {
            'verdict':                  self.verdict.name,
            'verdict_icon':             self.verdict.icon,
            'capability_state':         self.verdict.capability_state,
            'message':                  self.message,
            'matched_event_id':         self.matched_event.event_id if self.matched_event else None,
            'missing_required_fields':  self.missing_required_fields,
            'partial_fields':           self.partial_fields,
            'field_coverage':           [fc.to_dict() for fc in self.field_coverage],
            'expected_result':          self.expected,
            'as_expected':              self.as_expected,
            'capability_detected':      self.capability_detected,
            'anchor_detected':          self.anchor_detected,
            'anomaly':                  self.anomaly,
            'value_scan':               self.value_scan,
        }


# ── Field-level validator ──────────────────────────────────────────────────

def _check_field(
    field_name: str,
    rule: dict,
    event: CanonicalEvent,
) -> FieldCoverageResult:
    """
    Evaluate one expected_fields rule against a CanonicalEvent.

    Rule keys (all optional, combined with AND):
        equals    – case-insensitive exact match
        contains  – case-insensitive substring match
        nonempty  – value must be non-None and non-empty string
        startswith – case-insensitive prefix
    """
    required = rule.get('required', False)

    # Resolve value from canonical event
    raw = getattr(event, field_name, None)
    # Also try raw JSON via field_name if not on canonical model
    if raw is None and event.raw:
        raw = event.raw.get(field_name)

    actual = str(raw).strip() if raw is not None else None

    if actual is None or actual == '' or actual == 'None':
        status = 'MISSING_IN_EVENT'
        return FieldCoverageResult(field_name, required, rule, actual, status)

    # Evaluate rules
    val = actual.lower()
    passed = True

    if 'equals' in rule:
        passed = passed and (val == str(rule['equals']).lower().strip())
    if 'contains' in rule:
        passed = passed and (str(rule['contains']).lower().strip() in val)
    if 'startswith' in rule:
        passed = passed and val.startswith(str(rule['startswith']).lower().strip())
    if 'nonempty' in rule:
        passed = passed and (actual != '')

    status = 'PASS' if passed else 'FAIL'
    return FieldCoverageResult(field_name, required, rule, actual, status)


def evaluate_field_coverage(
    event: CanonicalEvent,
    test_case: dict,
) -> list[FieldCoverageResult]:
    """Run all expected_fields rules against a matched event."""
    expected: dict = test_case.get('expected_fields', {})
    results = []
    for field_name, rule in expected.items():
        results.append(_check_field(field_name, rule, event))
    return results


# ── Main verdict logic ─────────────────────────────────────────────────────

def decide(
    run: RunMetadata,
    match_result: MatchResult,
    test_case: dict,
    load_stats: dict,
) -> VerdictResult:

    # ── PENDING: no run data at all ───────────────────────────────────────
    expected = test_case.get('expected_result') if isinstance(test_case, dict) else None

    if run is None or (not run.sample_result and not run.run_id):
        return VerdictResult(
            Verdict.PENDING,
            'No run data available. Sample has not been executed against this case.',
            expected=expected,
        )

    # ── ERROR_SAMPLE: sample execution failed ─────────────────────────────
    if not run.sample_ok:
        return VerdictResult(
            Verdict.ERROR_SAMPLE,
            f'Sample did not execute successfully: result={run.sample_result!r}, '
            f'exit_code={run.exit_code}. Errors: {run.error_lines}',
            expected=expected,
        )

    # ── ERROR_LOG_INPUT: empty or unloadable log ──────────────────────────
    if load_stats.get('total_rows', 0) == 0:
        return VerdictResult(
            Verdict.ERROR_LOG_INPUT,
            'Event log is empty or could not be loaded.',
            expected=expected,
        )

    # ── ERROR_LOG_INPUT: TARGET window not available ──────────────────────
    if not match_result.target_window_available:
        return VerdictResult(
            Verdict.ERROR_LOG_INPUT,
            'TARGET time window not available from stdout; cannot filter by time.',
            expected=expected,
        )

    # ── ERROR_LOG_INPUT: log does not cover TARGET window ─────────────────
    if match_result.coverage_status == 'NOT_COVERED':
        return VerdictResult(
            Verdict.ERROR_LOG_INPUT,
            f'Event log time range does not cover the TARGET window. '
            f'Log: [{match_result.log_time_min} – {match_result.log_time_max}], '
            f'Target: [{match_result.target_begin} – {match_result.target_end}]. '
            f'Re-export the log with a wider time range.',
            value_scan=match_result.value_scan,
            expected=expected,
        )

    coverage_note = ''
    if match_result.coverage_status == 'PARTIAL':
        coverage_note = (
            f' NOTE: log only partially covers TARGET window '
            f'({match_result.log_time_min} – {match_result.log_time_max}).'
        )

    count = match_result.match_count

    # ── 主结论（三态）：能力判定（base / full 两层）─────────────────────
    # 判定依据 = 云端日志 operation 匹配（能力存在性），
    # capability_probe 精确字段区分「对 / 疑问」。进程锚定只作辅助。
    match_cfg = test_case.get('match') or {}
    probe_op = ((match_cfg.get('capability_probe') or {}).get('operation')
                or match_cfg.get('operation', ''))

    # 1) 无能力 → 错（未采集）：连基础 operation 事件都没有
    if not match_result.capability_base_detected:
        return VerdictResult(
            Verdict.NOT_IMPLEMENTED,
            f'未采集：云端日志中无 {probe_op!r} 行为事件（能力不存在）。{coverage_note} '
            f'Log covered TARGET window (coverage={match_result.coverage_status}).',
            capability_detected=False,
            anchor_detected=count > 0,
            value_scan=match_result.value_scan,
            expected=expected,
        )

    # 2) 基础能力有、但精确变体（probe 字段）未采到 → 疑问
    if not match_result.capability_detected:
        return VerdictResult(
            Verdict.PARTIALLY_IMPLEMENTED,
            f'疑问：云端日志存在 {match_result.capability_base_count} 条 {probe_op!r} 基础事件，'
            f'但 capability_probe 精确字段未命中——该行为变体可能未采集。{coverage_note}',
            capability_detected=False,
            anchor_detected=count > 0,
            value_scan=match_result.value_scan,
            expected=expected,
        )

    # 样本特征值命中辅助说明（不作为判定依据，仅用于 message 如实展示）
    svf_note = ''
    if match_result.sample_value_found is True:
        svf_note = '样本特征值已命中。'
    elif match_result.sample_value_found is False:
        svf_note = '（样本具体对象值未命中，但能力存在，不影响判定。）'

    # 3) 精确能力命中 → 对（采集到）
    #    若锚定到唯一候选，跑 expected_fields 校验作佐证；required 字段失败仍标「疑问」。
    if count == 1:
        evt = match_result.unique_match
        coverage = evaluate_field_coverage(evt, test_case)
        failed_required = [fc for fc in coverage if fc.required and fc.status != 'PASS']
        if failed_required:
            field_summary = ', '.join(
                f'{fc.field}({fc.status})' for fc in failed_required
            )
            return VerdictResult(
                Verdict.PARTIALLY_IMPLEMENTED,
                f'Event matched (ID={evt.event_id})，但 required 字段校验失败: '
                f'{field_summary}.{coverage_note}',
                matched_event=evt,
                field_coverage=coverage,
                capability_detected=True,
                anchor_detected=True,
                value_scan=match_result.value_scan,
                expected=expected,
            )
        return VerdictResult(
            Verdict.IMPLEMENTED,
            f'采集到：{probe_op!r} 事件命中，字段校验通过 (ID={evt.event_id})。{svf_note}{coverage_note}',
            matched_event=evt,
            field_coverage=coverage,
            capability_detected=True,
            anchor_detected=True,
            value_scan=match_result.value_scan,
            expected=expected,
        )

    # count==0 或 count>1：锚定非唯一，但能力 + 值命中已足够判「对」
    return VerdictResult(
        Verdict.IMPLEMENTED,
        f'采集到：云端日志存在 {match_result.capability_count} 条 {probe_op!r} 事件（能力存在）。'
        f'{svf_note}{coverage_note}'
        f'Log covered TARGET window (coverage={match_result.coverage_status}).',
        capability_detected=True,
        anchor_detected=count > 0,
        value_scan=match_result.value_scan,
        expected=expected,
    )


# ── Multi-phase (fullcycle) aggregation ────────────────────────────────────

_VERDICT_SEVERITY = {
    'ERROR_SAMPLE':          0,
    'ERROR_LOG_INPUT':       0,
    'AMBIGUOUS':             1,
    'NOT_IMPLEMENTED':       2,
    'PARTIALLY_IMPLEMENTED': 3,
    'IMPLEMENTED':           4,
    'VIA_WINDOWS_EVENTLOG':  8,
    'PENDING':               9,
}


def aggregate_verdicts(phase_results: list[dict]) -> dict:
    """Aggregate per-phase verdict dicts into an overall verdict.

    phase_results: list of dicts, each containing a 'verdict' name string.
    Returns a dict with overall_verdict / capability_state / icon.
    The overall verdict is the *worst* (lowest severity) phase verdict.
    """
    if not phase_results:
        return {
            'overall_verdict':   'PENDING',
            'capability_state':  'Pending Response',
            'icon':              '❓',
        }
    names = [r.get('verdict', 'PENDING') for r in phase_results]
    worst = min(names, key=lambda n: _VERDICT_SEVERITY.get(n, 99))
    try:
        v = Verdict[worst]
    except KeyError:
        v = Verdict.PENDING
    return {
        'overall_verdict':   worst,
        'capability_state':  v.capability_state,
        'icon':              v.icon,
    }
