#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sysmon evtx 解析工具（L2 参照佐证用）。

把 Sysmon 导出的 evtx 文件读成可分析的事件列表，用于佐证"样本确实执行了某个行为"。
后端用 PowerShell 的 Get-WinEvent（Windows 原生，无需第三方库），Python 负责组装/过滤/输出。

用法：
    python tools/parse_evtx.py <evtx路径>                       # 统计 EventID 分布
    python tools/parse_evtx.py <evtx路径> --event-id 11         # 只看某 EventID（如 11=FileCreate, 1=ProcessCreate）
    python tools/parse_evtx.py <evtx路径> --search "关键词"      # 搜字段值含关键词的事件
    python tools/parse_evtx.py <evtx路径> --field Image --top 20 # 统计某字段值分布 Top N
    python tools/parse_evtx.py <evtx路径> --out result.json      # 输出完整 JSON

Sysmon 常用 EventID：
    1  ProcessCreate（进程创建）   11 FileCreate（文件创建）
    12 RegistryEvent(创建/删除)    13 RegistryValue(写值)
    23 FileDelete（文件删除，新版）  22 DnsQuery   5 ProcessTerminate
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

_PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$path = '__EVTX_PATH__'
$evts = @(Get-WinEvent -Path $path -ErrorAction SilentlyContinue)
$result = @()
foreach ($e in $evts) {
    $xml = [xml]$e.ToXml()
    $data = @{}
    foreach ($d in @($xml.Event.EventData.Data)) {
        if ($d.Name) { $data[$d.Name] = [string]$d.'#text' }
    }
    $result += [pscustomobject]@{
        EventID   = [int]$e.Id
        Time      = $e.TimeCreated.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        Computer  = [string]$xml.Event.System.Computer
        Data      = $data
    }
}
$result | ConvertTo-Json -Depth 6 -Compress
"""


def read_evtx(evtx_path: str) -> list:
    """读 evtx，返回事件列表 [{EventID, Time, Computer, Data:{Name:value}}]."""
    escaped = str(evtx_path).replace("'", "''")
    ps = _PS_SCRIPT.replace('__EVTX_PATH__', escaped)
    proc = subprocess.run(
        ['powershell', '-NoProfile', '-Command', ps],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    raw = (proc.stdout or '').strip()
    if not raw:
        raise RuntimeError(
            'PowerShell 读取失败，stderr: ' + (proc.stderr or '')[:500]
        )
    parsed = json.loads(raw)
    # ConvertTo-Json 对单元素会输出对象而非数组
    if isinstance(parsed, dict):
        parsed = [parsed]
    return parsed


def _field_values(events: list, field: str) -> list:
    out = []
    for e in events:
        v = (e.get('Data') or {}).get(field)
        if v:
            out.append(v)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='Sysmon evtx 解析（L2 佐证）')
    ap.add_argument('evtx', help='evtx 文件路径')
    ap.add_argument('--event-id', type=int, help='只保留该 EventID')
    ap.add_argument('--search', help='搜任意字段值含关键词的事件')
    ap.add_argument('--field', help='统计某字段值分布（配合 --top）')
    ap.add_argument('--top', type=int, default=20, help='分布 Top N')
    ap.add_argument('--out', help='输出完整事件到 JSON 文件')
    args = ap.parse_args(argv)

    events = read_evtx(args.evtx)

    if args.event_id is not None:
        events = [e for e in events if e['EventID'] == args.event_id]

    if args.search:
        kw = args.search
        events = [e for e in events
                  if any(kw in str(v) for v in (e.get('Data') or {}).values())]

    # 1) 分布统计
    if args.field:
        vals = _field_values(events, args.field)
        from collections import Counter
        print(f'== {args.field} 值分布（Top {args.top}，总 {len(vals)} 条）==')
        for v, c in Counter(vals).most_common(args.top):
            print(f'{c:6d}  {v}')
        return 0

    # 2) EventID 分布（默认）
    from collections import Counter
    dist = Counter(e['EventID'] for e in events)
    print(f'== EventID 分布（总 {len(events)} 条）==')
    for eid, c in sorted(dist.items()):
        print(f'  EventID {eid}: {c}')

    # 3) 输出完整 JSON
    if args.out:
        Path(args.out).write_text(
            json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(f'已写出 {len(events)} 条到 {args.out}')

    # 4) 简要列出（前 10 条）
    print('\n== 前 10 条（EventID / Time / 关键字段）==')
    for e in events[:10]:
        data = e.get('Data') or {}
        keys = ['Image', 'TargetFilename', 'CommandLine', 'ParentImage', 'TargetObject', 'QueryName']
        kv = ' '.join(f'{k}={data[k]}' for k in keys if k in data)
        print(f'  [{e["EventID"]}] {e["Time"]}  {kv[:160]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
