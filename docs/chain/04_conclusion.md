# 行为链 ④ 结论分析（chain/04_conclusion.md）

> 版本：v1.0.0 ｜ 更新：2026-08-24 ｜ 上游：③ 找映射 ｜ 下游：可反哺 ① 样本构建
> 一句话：三态判定 + 行业对比 + AI 行为结果分析（可循环反哺样本构建）。

## 一、自动化实现（现状）

- 三态判定：`config/case_result_map.json`（对 / 疑问 / 错）+ `status.py` 的 `_verdict_to_binary` 前端四色；
- 行业对比：`config/industry_baseline.json`（53 category × Sysmon/MDE/CrowdStrike/SentinelOne）+ summary 行业对比列；
- AI 行为结果分析：`result_analysis` 字段（预留，规范见 `AI_SUMMARY_SPEC.md`）——采到/漏采/根因/行业/建议；
- 前端展示：summary.html（表格：行为 / 判定 / 结论 / 行业对比 / AI 分析占位）。

## 二、目前规则

- 三态：对（完整采集）/ 疑问（部分采集）/ 错（无采集），导师标准"部分=通过"；
- 行业对比 4 标签：🟢行业对齐 / 🔴能力缺口 / ⚪行业常态缺口 / ⭐领先行业；
- **反哺**：结论分析发现样本问题（如触发方式不对）→ 回行为链 ① 重构样本（循环，不是单向）。

## 三、问题记录（编号）

### 已解决
| 编号 | 问题 | 结论 |
|---|---|---|
| VERDICT-01 | 三态 verdict | case_result_map v3.0.0（对 12 / 疑问 3 / 错 6）|
| VERDICT-02 | 行业对比 | industry_baseline.json + summary 列 |
| VERDICT-03 | 总结规范 | AI_SUMMARY_SPEC.md |

### 未解决
| 编号 | 问题 | 状态 |
|---|---|---|
| VERDICT-11 | `result_analysis` 未填（预留，AI 待按规范生成）| 待生成 |
| VERDICT-12 | 15 待定稿 case（Process/Hash/ScheduledTask/Service）| 待跑 match |
| VERDICT-13 | 行业对比"行业分歧"边界（2 有 2 无时怎么算）| 待定义 |

## 四、编号与版本规则

- 问题编号：`VERDICT-<序号>`（01~10 已解决，11 起未解决）。
- 规则版本：本文件版本号 vX.Y.Z；changelog 见 `AI_CHAIN_LOG.md`。
