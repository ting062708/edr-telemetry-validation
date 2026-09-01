# 行为链 ③ 找映射（chain/03_find_mapping.md）

> 版本：v1.0.0 ｜ 更新：2026-08-24 ｜ 上游：② 跑样本 ｜ 下游：④ 结论分析
> 一句话：正向值扫描 + 反向剖析 → 生成 behavior_fields + observed_fields（已实践）。

## 一、自动化实现（现状）

- 正向值扫描：`tools/discover_mapping.py` —— stdout 的 TARGET 值 → 扫日志找 dot-path 落点；
- 反向剖析：日志有值字段 → 反推样本该补什么 stdout 值（方法论见 STDOUT_SPEC，工具待完善）；
- 产物：`config/mappings/<module>/<CASE>.json`（`behavior_fields` 值锚点 + `observed_fields` 采集完整性清单 + `known_gap`）；
- 格式规范：`docs/MAPPING_GUIDE.md`（dot-path 规则、数组候选落点）。

## 二、目前规则

- **已实践**，交替迭代：反向先行定"补什么"，正向验证"对上了没"；
- 交替上限 3 次（全局提示词 #2）；
- 锚点：`Parent.FileMd5` + `Common.EventTime` ±slack；进程用 MD5，内核态用对象值/`skip_process_anchor`。

## 三、问题记录（编号）

### 已解决
| 编号 | 问题 | 结论 |
|---|---|---|
| MAPPING-01 | 正向值扫描工具 | `discover_mapping.py` 可用 |
| MAPPING-02 | 5 模块 21 case 映射 | file/account/registry/driver/network 已定稿 |
| MAPPING-03 | 映射格式 | behavior_fields + observed_fields + known_gap |

### 未解决
| 编号 | 问题 | 状态 |
|---|---|---|
| MAPPING-11 | 反向剖析工具未完善（方法论已定）| 待写工具 |
| MAPPING-12 | 字段歧义消解（Network 同事件多行为靠 Child.Host 区分）| 待沉淀通用规则 |
| MAPPING-13 | 内核态事件锚点（对象值锚定）| 部分已做，待系统化 |

## 四、编号与版本规则

- 问题编号：`MAPPING-<序号>`（01~10 已解决，11 起未解决）。
- 规则版本：本文件版本号 vX.Y.Z；changelog 见 `AI_CHAIN_LOG.md`。
