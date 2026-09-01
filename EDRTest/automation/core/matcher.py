"""
matcher.py

Deterministic event matcher for IOA telemetry validation.

Match pipeline:
  1. Hostname
  2. TARGET time window (±slack)
  3. Actor name
  4. PID (strict when source carries PID data)
  5. Operation
  6. Extra key fields from test_case['match']

Field-level validation (expected_fields) is handled by verdict.py after a
unique candidate is found here.

PID policy:
  - stdout PID present AND ≥1 candidate carries actor_pid → strict match
  - stdout PID present but source carries no actor_pid at all → skip filter
  - stdout PID absent → skip filter
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from normalizer import CanonicalEvent
from stdout_parser import RunMetadata

log = logging.getLogger(__name__)

_DEFAULT_PRE_SLACK_S  = 5
_DEFAULT_POST_SLACK_S = 30


@dataclass
class MatchResult:
    candidates: list[CanonicalEvent] = field(default_factory=list)
    filter_log: list[str] = field(default_factory=list)

    total_events:    int = 0
    after_hostname:  int = 0
    after_time:      int = 0
    after_actor:     int = 0
    after_pid:       int = 0
    after_operation: int = 0
    after_extra:     int = 0

    target_window_available: bool = False
    pid_filter_applied:      bool = False
    pid_skipped_no_data:     bool = False

    log_time_min: Optional[str] = None
    log_time_max: Optional[str] = None
    target_begin: Optional[str] = None
    target_end:   Optional[str] = None
    run_begin:    Optional[str] = None
    run_end:      Optional[str] = None
    coverage_status: str = 'UNKNOWN'   # COVERED | PARTIAL | NOT_COVERED | UNKNOWN

    # ── Capability detection (能力存在性，不锚定进程) ────────────────────
    # 判定 IOA 是否具备采集该行为类型的能力：日志里只要存在符合
    # operation（+可选 capability_probe 精确字段）的事件即能力存在，
    # 不论事件是哪个进程触发的。这是 baseline 的主结论。
    #   capability_base_detected = 仅 operation 命中（基础能力，判断「有没有该事件类型」）
    #   capability_detected      = operation + probe 精确字段都命中（精确能力，判断「对/疑问」）
    capability_detected: bool = False
    capability_base_detected: bool = False
    capability_evidence: list = field(default_factory=list)

    # ── 值扫描（stdout 字段值 → 日志里是否存在）──────────────────────
    # 对 stdout 的每个 [TARGET] 字段值，在日志归一化事件里做全字段扫描，
    # 记录该值是否被 IOA 采到（不预设 dot-path）。用于前端「存在才标」。
    value_scan: dict = field(default_factory=dict)
    capability_count: int = 0   # 精确能力命中的真实事件数（evidence 是截断的，别用它计数）
    capability_base_count: int = 0   # 基础能力（仅 operation）命中的真实事件数

    # ── 分能力采集判断 v2（capability_rules_v2.json 驱动）───────────────
    capability_v2: Optional[str] = None   # '有' | '无' | None(无规则)
    collected_v2:   Optional[str] = None  # '采到' | '未采到' | '待测' | None(无规则)
    capability_v2_rule: Optional[dict] = None  # v2 规则摘要（锚定/表/operation），前端监测终端展示

    # ── 样本特征值命中（behavior_fields 映射的 stdout 值 → 日志字段）────
    # 在 hostname + 时间窗过滤后的池上独立匹配，不受进程锚定影响。
    # True  = 样本的关键值（文件名/账户名/路径）在日志里被采到
    # False = 样本值未被采到（但能力可能仍存在 → verdict 判「疑问」）
    # None  = 无 behavior_fields 映射，不参与值命中判定
    sample_value_found: Optional[bool] = None
    sample_value_hits: dict = field(default_factory=dict)  # stdout_field -> bool

    @property
    def unique_match(self) -> Optional[CanonicalEvent]:
        return self.candidates[0] if len(self.candidates) == 1 else None

    @property
    def match_count(self) -> int:
        return len(self.candidates)

    def to_dict(self) -> dict:
        return {
            'total_events':            self.total_events,
            'after_hostname':          self.after_hostname,
            'after_time':              self.after_time,
            'after_actor':             self.after_actor,
            'after_pid':               self.after_pid,
            'after_operation':         self.after_operation,
            'after_extra':             self.after_extra,
            'target_window_available': self.target_window_available,
            'pid_filter_applied':      self.pid_filter_applied,
            'pid_skipped_no_data':     self.pid_skipped_no_data,
            'log_time_min':            self.log_time_min,
            'log_time_max':            self.log_time_max,
            'target_begin':            self.target_begin,
            'target_end':              self.target_end,
            'run_begin':               self.run_begin,
            'run_end':                 self.run_end,
            'coverage_status':         self.coverage_status,
            'candidate_count':         self.match_count,
            'capability_detected':     self.capability_detected,
            'capability_base_detected': self.capability_base_detected,
            'capability_evidence':     self.capability_evidence,
            'value_scan':              self.value_scan,
            'capability_count':        self.capability_count,
            'capability_base_count':   self.capability_base_count,
            'capability_v2':           self.capability_v2,
            'collected_v2':            self.collected_v2,
            'capability_v2_rule':      self.capability_v2_rule,
            'sample_value_found':      self.sample_value_found,
            'sample_value_hits':       self.sample_value_hits,
            'filter_log':              self.filter_log,
        }


# ── Helpers ────────────────────────────────────────────────────────────────

def _norm(value) -> str:
    return str(value).strip().lower() if value is not None else ''


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _get(event: CanonicalEvent, field_name: str) -> Optional[str]:
    """
    Read a field from CanonicalEvent by canonical attribute name.
    Falls back to raw dict for non-canonical dot-path names.
    """
    val = getattr(event, field_name, None)
    if val is None and event.raw:
        val = event.raw.get(field_name)
    return str(val).strip() if val is not None else None


# ── 分能力采集判断 v2 ─────────────────────────────────────────────────────
# 由 config/capability_rules_v2.json 驱动：
#   capability_v2: 有/无 —— 全局能力存在性（operation(+表)在日志里是否存在）
#   collected_v2:  采到/未采到/待测 —— 时间窗 + 锚定进程(Parent) + 表类别
# 锚定方式：
#   direct   样本进程自己就是 Parent（按 Parent.FileMd5 精确匹配样本 MD5）
#   indirect 样本拉起子进程，子进程才是 Parent（按 Parent.FileName，如 msiexec/powershell）
#   system   kernel/系统进程执行（跳过进程锚定，只看时间窗 + operation）
#   field    无 operation，按字段存在性判断能力（如哈希=Child.FileMd5 字段）
_CAP_RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', 'config', 'capability_rules_v2.json')
_cap_rules_cache: Optional[dict] = None


def _load_capability_rules() -> dict:
    global _cap_rules_cache
    if _cap_rules_cache is None:
        try:
            with open(_CAP_RULES_PATH, encoding='utf-8') as f:
                _cap_rules_cache = json.load(f)
        except Exception as exc:  # 规则文件缺失时优雅降级
            log.warning('capability_rules_v2.json 加载失败: %s', exc)
            _cap_rules_cache = {'capabilities': []}
    return _cap_rules_cache


def _capability_v2(test_case: dict, events: list, window_pool: list):
    """分能力采集判断 v2。返回 (capability_v2, collected_v2)。"""
    rules = _load_capability_rules()
    case_id = test_case.get('id')
    cap = next((c for c in rules.get('capabilities', [])
                if case_id in c.get('cases', [])), None)
    if cap is None:
        return None, None, None
    ops_norm = {_norm(o) for o in (cap.get('operations') or [])}
    table_norm = {_norm(t) for t in (cap.get('tables') or [])}

    def _op_ok(e):
        return (not ops_norm) or (_norm(e.operation) in ops_norm)

    def _table_ok(e):
        if not table_norm:
            return True
        return _norm(_get(e, '@table')) in table_norm

    # 能力（全局）：operation(+表) 是否存在。
    # 不依赖任何 Child.* 字段——判定只基于样本 stdout 已知信息：
    # 行为 operation（case 配置）+ 时间窗 + 进程锚定。
    capability = '有' if any(_op_ok(e) and _table_ok(e) for e in events) else '无'

    # 采集（时间窗 + 锚定）
    anchor = cap.get('anchor') or {}
    atype = anchor.get('type')
    if atype == 'direct':
        md5 = _norm(anchor.get('md5'))
        hits = [
            e for e in window_pool
            if _op_ok(e) and _table_ok(e) and md5
            and _norm(_get(e, 'Parent.FileMd5')) == md5
        ]
        collected = '采到' if hits else '未采到'
    elif atype == 'indirect':
        proc = _norm(anchor.get('process'))
        hits = [
            e for e in window_pool
            if _op_ok(e) and _table_ok(e) and proc
            and _norm(_get(e, 'Parent.FileName')) == proc
        ]
        collected = '采到' if hits else '未采到'
    elif atype == 'system':
        hits = [e for e in window_pool if _op_ok(e) and _table_ok(e)]
        collected = '采到' if hits else '未采到'
    elif atype == 'field':
        collected = '待测'  # 字段类能力不适用窗内锚定
    else:
        collected = '待测'

    anchor = cap.get('anchor') or {}
    rule = {
        'anchor_type':    anchor.get('type'),
        'anchor_process': anchor.get('process'),
        'anchor_md5':     anchor.get('md5'),
        'tables':         cap.get('tables') or [],
        'operations':     cap.get('operations') or [],
        'probe':          cap.get('probe'),
    }
    return capability, collected, rule



# ── Main matcher ───────────────────────────────────────────────────────────

def match(
    run: RunMetadata,
    test_case: dict,
    events: list[CanonicalEvent],
    pre_slack_s:  int = _DEFAULT_PRE_SLACK_S,
    post_slack_s: int = _DEFAULT_POST_SLACK_S,
) -> MatchResult:
    result = MatchResult(total_events=len(events))
    match_cfg: dict = test_case.get('match', {})

    # Case-level slack override: allow test_cases.json to tighten the TARGET
    # window via match.pre_slack_s / match.post_slack_s. Useful when the same
    # Action.Name recurs every ~20s across cases (e.g. AccountCreate from each
    # case's SETUP) and the default 30s post-slack would swallow neighbours.
    if 'pre_slack_s' in match_cfg:
        pre_slack_s = int(match_cfg['pre_slack_s'])
    if 'post_slack_s' in match_cfg:
        post_slack_s = int(match_cfg['post_slack_s'])

    # ── Log time range (before any filter) ───────────────────────────────
    all_times = [e.event_time_utc for e in events if e.event_time_utc is not None]
    if all_times:
        result.log_time_min = _iso(min(all_times))
        result.log_time_max = _iso(max(all_times))

    # ── Stage 0: Hostname ─────────────────────────────────────────────────
    expected_host = _norm(run.hostname)
    if not expected_host:
        result.filter_log.append('WARN: stdout hostname empty; hostname filter skipped')
        pool = list(events)
    else:
        pool = [e for e in events if _norm(e.hostname) == expected_host]
        result.filter_log.append(
            f'Hostname ({run.hostname!r}): {len(pool)}/{result.total_events}'
        )
    result.after_hostname = len(pool)

    # ── Stage 1: 样本运行时间区间（RUN-BEGIN..RUN-END）────────────────────
    # 时间过滤优先用「样本运行区间」，覆盖 SETUP + TARGET + 验证整段：
    # 行为事件（如账户操作）常发生在 SETUP 阶段，不在 TARGET 瞬间。
    # 只有 RUN 区间缺失时才回退到 TARGET 窗口。
    run_begin_dt = _utc(run.run_start_utc)
    run_end_dt   = _utc(run.run_end_utc)
    t_begin = run_begin_dt or _utc(run.target_begin_utc)
    t_end   = run_end_dt   or _utc(run.target_end_utc)
    result.run_begin    = _iso(run_begin_dt)
    result.run_end      = _iso(run_end_dt)
    result.target_begin = _iso(_utc(run.target_begin_utc))
    result.target_end   = _iso(_utc(run.target_end_utc))

    if t_begin is None or t_end is None:
        result.filter_log.append('WARN: RUN window absent; time filter skipped')
        result.coverage_status = 'UNKNOWN'
    else:
        result.target_window_available = True
        window_start = t_begin - timedelta(seconds=pre_slack_s)
        window_end   = t_end   + timedelta(seconds=post_slack_s)

        if all_times:
            log_min, log_max = min(all_times), max(all_times)
            if log_min <= t_begin and log_max >= t_end:
                result.coverage_status = 'COVERED'
            elif log_max < t_begin or log_min > t_end:
                result.coverage_status = 'NOT_COVERED'
            else:
                result.coverage_status = 'PARTIAL'
        else:
            result.coverage_status = 'NOT_COVERED'

        pool = [
            e for e in pool
            if e.event_time_utc is not None
            and window_start <= e.event_time_utc <= window_end
        ]
        result.filter_log.append(
            f'Time window [{window_start.isoformat()} – {window_end.isoformat()}]: '
            f'{len(pool)} events (coverage={result.coverage_status})'
        )
    result.after_time = len(pool)
    # 时间窗内候选快照：供 behavior_fields 值匹配独立使用。
    # 进程锚定链(actor/PID/MD5)只影响 candidates，不影响能力与值命中判定。
    window_pool = list(pool)

    # ── Process-anchor-skipped behaviours ───────────────────────────────
    # 两类行为的 IOA 事件 Parent 不是样本进程，样本 MD5/PID/进程名全部不适用：
    #   1. 内核态动作（LoadDriver）→ Parent=SystemIdle（PID=0, MD5=AAAA…）
    #   2. WinEventLog 代执行动作（账户管理/登录）→ Parent=lsass.exe
    # 此时跳过进程级锚点，仅靠时间窗 + operation + 行为字段值锚定。
    # 兼容旧写法 kernel_mode 与通用写法 skip_process_anchor。
    skip_process_anchor = bool(
        match_cfg.get('kernel_mode', False) or
        match_cfg.get('skip_process_anchor', False)
    )

    # ── Stage 2: Actor name ───────────────────────────────────────────────
    expected_actor = _norm(match_cfg.get('actor_exe', ''))
    if expected_actor and not skip_process_anchor:
        pool = [e for e in pool if _norm(e.actor_name) == expected_actor]
        result.filter_log.append(
            f'Actor ({match_cfg["actor_exe"]!r}): {len(pool)} events'
        )
    elif skip_process_anchor:
        result.filter_log.append('Actor filter skipped (skip_process_anchor)')
    result.after_actor = len(pool)

    # ── Stage 3: PID ──────────────────────────────────────────────────────
    if run.pid is not None and not skip_process_anchor:
        candidates_with_pid = [e for e in pool if e.actor_pid is not None]
        if not candidates_with_pid:
            result.pid_skipped_no_data = True
            result.filter_log.append(
                f'PID ({run.pid}): source carries no actor_pid — filter omitted'
            )
        else:
            matched_by_pid = [e for e in pool if e.actor_pid == run.pid]
            result.pid_filter_applied = True
            if matched_by_pid:
                pool = matched_by_pid
                result.filter_log.append(
                    f'PID ({run.pid}): strict → {len(pool)} events'
                )
            else:
                result.filter_log.append(
                    f'PID ({run.pid}): strict → 0 events (no match in source)'
                )
                pool = []
    if skip_process_anchor:
        result.filter_log.append('PID filter skipped (skip_process_anchor)')
    result.after_pid = len(pool)

    # ── Stage 3.5: Sample MD5 exact match (anchor) ────────────────────────
    # 核心锚点：Parent.FileMd5 小写精确相等（非 contains）。
    # 来源：match_cfg['actor_md5']（或 test_case['sample_md5'] 兜底）。
    md5_cfg = match_cfg.get('actor_md5') or test_case.get('sample_md5')
    if md5_cfg and not skip_process_anchor:
        md5_norm = _norm(md5_cfg)
        before = len(pool)
        pool = [e for e in pool if _norm(e.actor_md5) == md5_norm]
        result.filter_log.append(
            f'MD5 exact ({md5_cfg!r}): {before} → {len(pool)} events'
        )

    # ── Stage 4: Operation ────────────────────────────────────────────────
    # operation may be a single string or a list (match ANY of them).
    # A multi-value operation (e.g. tamper → VirtualAllocEx OR WriteProcessMemory)
    # can legitimately hit several events that all describe the *same* actor→target
    # action. When those extra hits share the same (actor, actor_pid, target),
    # we dedupe to a single representative candidate instead of flagging AMBIGUOUS.
    op_cfg = match_cfg.get('operation', '')
    if op_cfg:
        ops = op_cfg if isinstance(op_cfg, list) else [op_cfg]
        ops_norm = [_norm(o) for o in ops if o]
        if ops_norm:
            pool = [e for e in pool if _norm(e.operation) in ops_norm]
            result.filter_log.append(
                f'Operation ({op_cfg!r}): {len(pool)} events'
            )
            if isinstance(op_cfg, list) and len(pool) > 1:
                seen: dict = {}
                deduped: list = []
                for e in pool:
                    key = (_norm(e.actor_name), _norm(e.actor_pid), _norm(e.target_name))
                    if key not in seen:
                        seen[key] = e
                        deduped.append(e)
                if len(deduped) < len(pool):
                    result.filter_log.append(
                        f'Operation dedup (same actor+target): {len(pool)} → {len(deduped)} events'
                    )
                    pool = deduped
    result.after_operation = len(pool)

    # ── Stage 5: Extra match fields from match_cfg ────────────────────────
    # These are coarse identity filters (registry_path, registry_value_name, etc.)
    # Fine-grained value checks (OldValue, NewValue, contains/equals rules)
    # are in expected_fields and evaluated by verdict.py after a unique match.
    skip_keys = {'actor_exe', 'operation', 'actor_md5', 'kernel_mode',
                 'skip_process_anchor', 'pre_slack_s', 'post_slack_s',
                 'capability_probe'}
    for field_name, expected_value in match_cfg.items():
        if field_name in skip_keys:
            continue
        # Numeric values (e.g. Child.FileTotalWrite=0) must match exactly,
        # otherwise a substring match would wrongly hit 10/100/200 etc.
        expected_norm = _norm(str(expected_value))
        exact = str(expected_value).strip().isdigit()
        before = len(pool)
        if exact:
            pool = [
                e for e in pool
                if _norm(_get(e, field_name)) == expected_norm
            ]
        else:
            pool = [
                e for e in pool
                if expected_norm in _norm(_get(e, field_name) or '')
            ]
        result.filter_log.append(
            f'match[{field_name}]={expected_value!r} ({"==" if exact else "contains"}): '
            f'{before} → {len(pool)} events'
        )

    result.after_extra = len(pool)

    # ── Stage 6: behavior_fields (stdout TARGET value → log dot-path) ─────
    # Data-driven behavior verification: config/mappings/<module>/<CASE-ID>.json
    # maps each stdout TARGET field name to the log dot-path where IOA actually
    # recorded that value (discovered by value scanning, not pre-set).
    # The value may be a single dot-path or a list (one stdout value lands on
    # several fields, e.g. a file path → Child.FilePath + Child.FileName).
    behavior_fields = test_case.get('behavior_fields') or {}
    for stdout_field, log_path in behavior_fields.items():
        expected = (run.target_fields or {}).get(stdout_field)
        if not expected:
            result.filter_log.append(
                f'behavior_fields[{stdout_field}]→{log_path}: '
                f'no stdout TARGET value, skipped'
            )
            continue
        expected_norm = _norm(expected)
        paths = log_path if isinstance(log_path, list) else [log_path]
        # 值匹配在【时间窗池】上独立进行，不依赖进程锚定链。
        # 命中与否记录到 sample_value_hits，供 verdict 判定「对/疑问」。
        hits = [
            e for e in window_pool
            if expected_norm and any(
                expected_norm in _norm(_get(e, p) or '') for p in paths
            )
        ]
        result.sample_value_hits[stdout_field] = bool(hits)
        result.filter_log.append(
            f'behavior_fields[{stdout_field}]→{paths}={expected!r}: '
            f'{len(hits)} hits in window pool'
        )
    if behavior_fields:
        result.sample_value_found = any(result.sample_value_hits.values())

    result.candidates  = pool

    # ── Capability detection ─────────────────────────────────────────────
    # 与进程锚定正交的第二条判定线：IOA 有没有采集「该行为类型」的能力。
    # 只看事件类型（operation）+ 可选的精确字段（capability_probe），
    # 不看 actor/PID/MD5/时间窗——因为能力是全局的，样本进程是否被采是另一回事。
    #
    # 例：FILE-CREATE 的能力探测 = FileWriteClose + Child.FileCreateOpName 含「新建文件」；
    #     而 FileWriteClose 一个事件类型覆盖了新建/覆盖写/打开三个行为，
    #      必须靠 FileCreateOpName 精确区分，否则会误判。
    probe = match_cfg.get('capability_probe') or {}
    probe_op = probe.get('operation') or match_cfg.get('operation', '')
    if probe_op:
        probe_ops = probe_op if isinstance(probe_op, list) else [probe_op]
        probe_ops_norm = [_norm(o) for o in probe_ops]
        probe_field = probe.get('field')
        probe_contains = probe.get('contains')
        probe_equals = probe.get('equals')
        capability_hits: list = []
        base_hits: list = []
        for e in events:
            if _norm(e.operation) not in probe_ops_norm:
                continue
            base_hits.append(e)  # 基础能力：仅 operation 命中
            if probe_field:
                val = _get(e, probe_field) or ''
                if probe_contains and probe_contains not in _norm(val):
                    continue
                if probe_equals and _norm(val) != _norm(probe_equals):
                    continue
            capability_hits.append(e)  # 精确能力：operation + probe 字段
        result.capability_detected = bool(capability_hits)
        result.capability_base_detected = bool(base_hits)
        result.capability_count = len(capability_hits)
        result.capability_base_count = len(base_hits)
        result.capability_evidence = [
            {'operation': e.operation, 'actor': e.actor_name, 'target': e.target_name}
            for e in capability_hits[:5]
        ]
        result.filter_log.append(
            f'Capability ({probe_op!r}): {len(capability_hits)} events '
            f'(能力{"存在" if capability_hits else "不存在"})'
        )

    # ── 值扫描：stdout 的每个 [TARGET] 字段值，在日志里全字段扫描是否存在 ──
    # 回答「SizeBefore=83 / ContentMd5=xxx 这些具体值日志里有没有」，
    # 前端据此「存在才标、不存在不标」。
    if run and run.target_fields:
        for _k, _v in run.target_fields.items():
            if not _v:
                continue
            _sv = str(_v).strip()
            if len(_sv) < 2:
                continue
            # 短值（动作名/数字 Size=59/83/66）用等值匹配避免子串误报；
            # 长值（路径/文件名/MD5）用子串匹配。
            _is_short = len(_sv) <= 6
            _found = False
            _where: list = []
            for e in events:
                _fvals = [str(x) for x in (e.actor_name, e.target_name, e.operation, e.actor_commandline) if x]
                if e.raw:
                    _fvals += [str(x) for x in e.raw.values() if x is not None]
                _hit = (any(_sv == fv for fv in _fvals) if _is_short
                        else any(_sv in fv for fv in _fvals))
                if _hit:
                    _found = True
                    _where.append(e.operation)
                    break
            result.value_scan[_k] = {'value': _sv, 'found': _found, 'where': _where[:3]}

    # ── 分能力采集判断 v2 ──────────────────────────────────────────────
    result.capability_v2, result.collected_v2, result.capability_v2_rule = _capability_v2(
        test_case, events, window_pool)

    log.info(
        'Match complete for %s: %d candidate(s), capability_detected=%s, '
        'capability_v2=%s, collected_v2=%s',
        test_case.get('id', '?'), len(pool), result.capability_detected,
        result.capability_v2, result.collected_v2,
    )
    return result
