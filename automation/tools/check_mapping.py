#!/usr/bin/env python3
"""
映射自检工具：校验 ioa_field_mapping.json 的 json_fields 映射是否与真实 IOA 日志一致。

用法：
    python tools/check_mapping.py <日志json路径> [映射json路径]

输出：
    1. 映射里"路径在日志中不存在"的字段（字段名写错了）
    2. 映射里"路径存在但日志中全空"的字段（可能该日志没触发，或字段名错）
    3. 日志里存在、但映射里没有的字段（遗漏，可考虑补充）
"""
import io
import json
import sys
from pathlib import Path

# 修复 Windows GBK 控制台的 Unicode 输出（emoji 会报 UnicodeEncodeError）
if sys.stdout.encoding and sys.stdout.encoding.lower() in ('gbk', 'cp936', 'cp950'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 让脚本能 import 同目录上级的 core 包（可选）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _flatten_mapping(d: dict, out: dict = None) -> dict:
    """把嵌套分组映射拍平成 {逻辑名: 点号路径}。"""
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


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    log_path = Path(sys.argv[1])
    map_path = Path(sys.argv[2]) if len(sys.argv) > 2 else (
        Path(__file__).resolve().parent.parent / 'config' / 'ioa_field_mapping.json'
    )

    # 1. 读映射
    mapping = json.loads(map_path.read_text(encoding='utf-8'))
    jf = mapping.get('json_fields', {})
    flat = _flatten_mapping(jf)

    # 2. 读日志，收集字段名全集 + 各字段非空计数
    data = json.loads(log_path.read_text(encoding='utf-8'))
    records = data if isinstance(data, list) else data.get('records', data)

    path_nonempty = {}   # 字段路径 -> 非空条数
    path_count = {}      # 字段路径 -> 出现条数
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for k, v in rec.items():
            path_count[k] = path_count.get(k, 0) + 1
            if v not in (None, ''):
                path_nonempty[k] = path_nonempty.get(k, 0) + 1

    # 3. 分类
    wrong = []      # 路径不存在（写错）
    empty = []      # 路径存在但全空（可能没触发）
    ok = []
    for logical, dotpath in flat.items():
        if dotpath not in path_count:
            wrong.append((logical, dotpath))
        elif path_nonempty.get(dotpath, 0) == 0:
            empty.append((logical, dotpath))
        else:
            ok.append((logical, dotpath, path_nonempty[dotpath]))

    # 4. 遗漏：日志里有、映射没有的 Child.*/Parent.*/Common.*/Action.*/Environment.* 字段
    mapped_paths = set(flat.values())
    unmapped = [
        k for k in path_nonempty
        if k not in mapped_paths
        and k.split('.')[0] in ('Child', 'Parent', 'Common', 'Action', 'Environment')
    ]

    print(f"日志记录数: {len(records)}")
    print(f"映射字段总数: {len(flat)}")
    print(f"✅ 路径存在且有值: {len(ok)}")
    print(f"❌ 路径不存在(写错): {len(wrong)}")
    print(f"⚠️  路径存在但全空(可能未触发): {len(empty)}")
    print(f"🔎 日志有而映射没有(遗漏候选): {len(unmapped)}")

    if wrong:
        print("\n--- 路径不存在的字段（需修正）---")
        for logical, dotpath in wrong:
            print(f"  {logical} -> {dotpath}")
    if empty:
        print("\n--- 路径存在但全空（需确认是否未触发）---")
        for logical, dotpath in empty:
            print(f"  {logical} -> {dotpath}")
    if unmapped:
        print("\n--- 遗漏候选字段（日志有、映射无）---")
        for k in sorted(unmapped):
            print(f"  {k}  ({path_nonempty[k]} 条非空)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
