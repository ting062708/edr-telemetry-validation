#!/usr/bin/env python3
"""
discover_mapping.py — 值扫描工具（行为字段发现）

用样本 stdout 的 TARGET 字段值，在 IOA 日志事件集里做【值扫描】，
发现每个业务值实际落在日志的哪个字段，据此生成
    config/mappings/<module>/<CASE-ID>.json

思路（已定稿）：
    锚点统一（Parent.FileMd5 + Common.EventTime 时间窗），框架负责；
    行为字段按 case 数据驱动发现——不预设字段名，
    拿 stdout TARGET 的实际值去日志里搜，值落在哪个字段就用哪个字段。

用法：
    python tools/discover_mapping.py \
        --stdout runs/Driver/DRIVER-LOAD-001/DRIVER-LOAD-001_stdout.txt \
        --json   log/Driver/json/export.json \
        [--sample-md5 E569892B7EEFAA9284720D8311AF5BA7] \
        [--slack 5] [--write]

流程：
    1. 解析 stdout → TARGET 字段值 + 时间窗
    2. 加载日志 → CanonicalEvent 列表
    3. 时间窗(±slack)过滤 → 锁定事件集
    4. 每个 TARGET 字段值 → 扫描所有 raw 字段 → 命中统计
    5. 打印候选映射；--write 时写 config/mappings/<module>/<CASE-ID>.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

# 修复 Windows GBK 控制台的 Unicode 输出
if sys.stdout.encoding and sys.stdout.encoding.lower() in ('gbk', 'cp936', 'cp950'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_ROOT = Path(__file__).resolve().parent.parent
_CORE = _ROOT / 'core'
_CONFIG = _ROOT / 'config'

for _p in (_CORE, str(_ROOT)):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from stdout_parser import parse_stdout, RunMetadata  # noqa: E402
from normalizer import load_events, CanonicalEvent   # noqa: E402


# 噪声字段：这些是进程元数据/调用栈，字符串拼接，不属业务对象字段
_NOISE_SUBSTR = (
    'Cmdline', 'CallStack', 'ProcChain', 'ProcGuid', 'ThreadId',
    'FileCompany', 'FileCopyright', 'FileDesc', 'FileIssuer', 'FileLegalMark',
    'FileOriginalName', 'FileProductName', 'FileProductVer', 'FileVersion',
    'FileTags', 'FileSourceUrl', 'CloudAttr', 'FileSign', 'FileSignWhite',
    'FileSignStatus', 'ProcTrust', 'ProcIntegrity', 'ProcUserName',
    'ProcDomainName', 'ProcElevationType', 'ProcCreateTime', 'ProcArch',
    'FileAccessTime', 'FileCreateTime', 'FileModifyTime', 'FileDriverType',
    'FileFormat', 'FileContentType', 'FileEncrypted', 'FileMd5Type',
    'FileTotalRead', 'FileTotalWrite',
)

# 业务对象字段优先级（值命中多个字段时，选优先级最高的）
_PRIORITY = (
    'Child.FilePath',
    'Child.NodeName',
    'Child.FileName',
    'Child.RegKeyPath',
    'Child.RegValName',
    'Child.RegValData',
    'Child.DstIp',
    'Child.SrcIp',
    'Child.DstPort',
    'Child.SrcPort',
    'Child.Url',
    'Child.HostName',
    'Child.Domain',
    'Child.TargetUserName',
    'Child.LogonType',
)


def _is_noise(dot_path: str) -> bool:
    if dot_path.startswith('PParent.'):
        return True
    return any(s in dot_path for s in _NOISE_SUBSTR)


def _is_business_field(dot_path: str) -> bool:
    """业务字段：Child.* 目标对象字段，且非进程/文件元数据噪声。

    observed_fields 收录这些字段——它们是 IOA 在行为事件里实际采到的
    目标对象业务维度（大小/类型/创建操作名/MD5/账户属性等），
    用于佐证采集能力的完整性，与 behavior_fields（值锚定）区分。
    """
    if not dot_path.startswith('Child.'):
        return False
    if _is_noise(dot_path):
        return False
    return True


def _enumerate_observed_fields(pool: list[CanonicalEvent]) -> list[str]:
    """枚举锁定事件集里 IOA 实际采集到的业务字段（非噪声 Child.*）。

    按出现频率降序返回字段名列表。用于生成映射文件的 observed_fields。
    """
    counts: dict[str, int] = {}
    for evt in pool:
        for k, v in (evt.raw or {}).items():
            if not _is_business_field(k):
                continue
            if v in (None, ''):
                continue
            counts[k] = counts.get(k, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def _priority(dot_path: str) -> int:
    try:
        return _PRIORITY.index(dot_path)
    except ValueError:
        return len(_PRIORITY)


def _scan_value(events: list[CanonicalEvent], value: str) -> dict[str, list[dict]]:
    """Return {dot_path: [ {table, action, time, value}, ... ]} for a single value."""
    v = str(value)
    if not v:
        return {}
    hits: dict[str, list[dict]] = {}
    for evt in events:
        for k, raw_val in (evt.raw or {}).items():
            match = False
            if isinstance(raw_val, str) and v.lower() in raw_val.lower():
                match = True
            elif isinstance(raw_val, (int, float)) and str(raw_val) == v:
                match = True
            if match:
                hits.setdefault(k, []).append({
                    'table':  evt.raw.get('@table', ''),
                    'action': evt.operation,
                    'time':   evt.event_time_utc.isoformat() if evt.event_time_utc else '',
                    'value':  raw_val,
                })
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description='Discover behavior_fields mapping by value scanning')
    ap.add_argument('--stdout', required=True, help='样本 stdout .txt')
    ap.add_argument('--json', required=True, help='IOA JSON 导出')
    ap.add_argument('--sample-md5', default=None, help='样本 MD5（锚点，可选）')
    ap.add_argument('--slack', type=int, default=None, help='对称宽松秒数（旧参数；不传则从 test_cases.json 读 pre/post slack，与 matcher 对齐）')
    ap.add_argument('--write', action='store_true', help='写 config/mappings/<module>/<CASE-ID>.json')
    ap.add_argument('--out-dir', default=None, help='映射输出目录（默认 config/mappings）')
    args = ap.parse_args()

    stdout_path = Path(args.stdout)
    json_path = Path(args.json)
    if not stdout_path.exists():
        print(f'stdout not found: {stdout_path}')
        return 1
    if not json_path.exists():
        print(f'json not found: {json_path}')
        return 1

    # 1. 解析 stdout
    run: RunMetadata = parse_stdout(stdout_path.read_text(encoding='utf-8', errors='replace'))
    case_id = run.test_case_id or stdout_path.stem.replace('_stdout', '')
    module = run.module or ''
    target_fields = dict(run.target_fields)

    print(f'Case      : {case_id}')
    print(f'Module    : {module}')
    print(f'Hostname  : {run.hostname or "(none)"}')
    print(f'TARGET窗  : {run.target_begin_utc} -> {run.target_end_utc}')
    print(f'TARGET字段: {len(target_fields)} 个')
    for k, val in target_fields.items():
        print(f'    {k} = {val}')

    # 2. 加载日志
    events, stats = load_events(json_path, config_dir=_CONFIG)
    print(f'\n日志事件  : {stats["total_rows"]} 行 / {stats["parsed_rows"]} 已解析 ({stats["source"]})')

    # 3. 时间窗过滤（与 matcher 对齐：pre_slack 前置 / post_slack 后置，
    #    默认 5 / 30，并优先读 test_cases.json 里该 case 的 match.pre_slack_s
    #    / match.post_slack_s，保证值扫描锁定的事件集与 match 时一致。）
    from datetime import timedelta
    pre_slack = 5
    post_slack = 30
    if args.slack is not None:
        pre_slack = post_slack = args.slack
    else:
        try:
            with (_CONFIG / 'test_cases.json').open('r', encoding='utf-8') as fh:
                tcases = json.load(fh).get('cases', [])
            tcase = next((c for c in tcases if c.get('id') == case_id), None)
            if tcase:
                m = tcase.get('match', {})
                pre_slack = int(m.get('pre_slack_s', pre_slack))
                post_slack = int(m.get('post_slack_s', post_slack))
        except Exception as exc:
            print(f'WARN: 读取 test_cases.json 的 slack 失败，用默认 5/30: {exc}')

    if run.target_begin_utc and run.target_end_utc:
        w0 = run.target_begin_utc - timedelta(seconds=pre_slack)
        w1 = run.target_end_utc + timedelta(seconds=post_slack)
        pool = [e for e in events
                if e.event_time_utc and w0 <= e.event_time_utc <= w1]
        print(f'时间窗过滤: [{w0.isoformat()} – {w1.isoformat()}] '
              f'(pre={pre_slack}s, post={post_slack}s) → {len(pool)}/{len(events)} 事件')
    else:
        pool = events
        print('WARN: TARGET 时间窗缺失，扫描全部事件')

    # 4. 值扫描
    print('\n' + '=' * 70)
    print('值扫描结果（stdout TARGET 字段值 → 日志命中字段）')
    print('=' * 70)

    discovered: dict[str, list[str]] = {}
    for fname, fval in target_fields.items():
        hits = _scan_value(pool, fval)
        print(f'\n[{fname}] = "{fval}"')
        if not hits:
            print('    → 0 命中（IOA 未采集此值）')
            continue
        # 去噪 + 排序（优先业务字段，其次命中数）
        clean = {k: v for k, v in hits.items() if not _is_noise(k)}
        ordered = sorted(clean.items(), key=lambda kv: (_priority(kv[0]), -len(kv[1])))
        if not ordered:
            print('    → 仅命中噪声字段（Cmdline/元数据等），忽略')
            continue
        # 一个值命中多个业务字段时，全部保留为映射（FilePath + FileName 等）。
        # 首选字段（优先级最高）排在第一位，其余作为补充映射。
        discovered[fname] = [p for p, _ in ordered]
        print(f'    ✅ 映射 {len(ordered)} 个字段（按优先级）:')
        for path, hh in ordered:
            print(f'       {fname} -> {path}  ({len(hh)} 条, {hh[0]["table"]}/{hh[0]["action"]})')

    # 5. 输出 / 写文件
    print('\n' + '=' * 70)
    if not discovered:
        print('未发现任何可映射的行为字段（该行为可能未被 IOA 采集）。')
        mapping = {
            'case_id': case_id,
            'module': module.lower(),
            'behavior_fields': {},
        }
    else:
        print('最终映射:')
        print(json.dumps(discovered, ensure_ascii=False, indent=2))
        mapping = {
            'case_id': case_id,
            'module': module.lower(),
            'behavior_fields': discovered,
        }

    # 5.5 observed_fields：锁定事件集里 IOA 采到的业务字段（采集能力佐证）
    observed = _enumerate_observed_fields(pool)
    if observed:
        mapping['observed_fields'] = observed
        print(f'\nobserved_fields（IOA 采到的业务字段 {len(observed)} 个）:')
        for f in observed:
            print(f'    {f}')
    else:
        print('\nobserved_fields: 无（锁定事件集内没有非噪声业务字段）')

    if args.write:
        out_dir = Path(args.out_dir) if args.out_dir else _CONFIG / 'mappings'
        out_path = out_dir / module.lower() / f'{case_id}.json'
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'\n已写入: {out_path}')
    else:
        print('\n（未加 --write，仅预览。确认后加 --write 落盘）')

    return 0


if __name__ == '__main__':
    sys.exit(main())
