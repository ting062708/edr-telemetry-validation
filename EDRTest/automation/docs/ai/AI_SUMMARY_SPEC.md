# AI 总结 baseline 规范（AI_SUMMARY_SPEC）

> 定位：定义「AI 如何对一个模块 / 整个 baseline 的采集结果做总结」，使结果总结**可复用、可自动生成**。
> 后续每个模块测完后，AI 按本规范直接产出「结论 + 行为结果分析」，无需每次人工重写。

---

## 一、总结的三个层级

| 层级 | 对象 | 产出 |
|---|---|---|
| 行为级 | 单个 case | verdict + 结论 + 行为结果分析 |
| 模块级 | 一个模块 | 模块结论 + 关键认知 + 映射完整性 |
| 总览级 | 整个 baseline | 三态统计 + 待定稿清单 |

---

## 二、行为级总结（核心）

每个行为（case），AI 输出以下字段：

| 字段 | 含义 | 示例 |
|---|---|---|
| `verdict` | 三态：对 / 疑问 / 错 | 疑问 |
| `conclusion` | 一句话结论 | "读 .cab 有 FileRead，读 .txt/.exe 无" |
| `result_analysis` | AI 深度分析（结构见下）| — |

### result_analysis 结构（行为结果分析，预留字段）

```json
{
  "collected":   ["采到了什么字段 / 值"],
  "missed":      ["漏了什么字段 / 值"],
  "root_cause":  "根因（采集机制 / 触发方式 / 路径筛选）",
  "industry":    "行业对比（读 config/industry_baseline.json，列 Sysmon/MDE/CrowdStrike/SentinelOne 判定）",
  "suggestion":  "建议（是否重测 / 怎么改样本 / 改触发方式）"
}
```

### 三态判定规则（对齐导师标准）

- **对**：完整采集（IOA 采到了该行为的核心字段）
- **疑问**：部分采集（部分情况下有记录）——导师标准下"部分=通过"，但标"疑问"以保留 AI 自扩展工程继续研究
- **错**：完全无采集

---

## 三、模块级总结

| 字段 | 含义 |
|---|---|
| 模块结论 | 一句话（如"IOA 对文件操作采集基本完整，读文件除外"）|
| 关键认知 | IOA 记录逻辑剖析（如"RegSetValue 只对值从无到有触发"）|
| 映射完整性 | behavior_fields（值锚点）+ observed_fields（采集完整性清单）|
| 样本改动 | 样本为触发采集做的调整记录 |

---

## 四、总览级总结（baseline）

| 字段 | 含义 |
|---|---|
| 三态统计 | 对 X / 疑问 X / 错 X / 待判定 X |
| 待定稿清单 | 没跑 match / 没定稿的 case |
| 差异记录 | 与同学 baseline 的差异（如 ScheduledTask 零采集 vs 同学 ✅）|
| 行业对比矩阵 | IOA 三态 × Sysmon/MDE/CrowdStrike/SentinelOne，标注「能力缺口 vs 行业常态缺口」|

---

## 五、与现有资产的对应

| 规范字段 | 落在哪 |
|---|---|
| verdict / conclusion | `case_result_map.json` 的 `verdict` / `note` |
| situations | `case_result_map.json` 的 `situations` |
| result_analysis | **预留**：`case_result_map.json` 新增 `result_analysis` 字段（后续 AI 生成填入）|
| 模块级总结 | `docs/<MODULE>_MODULE.md` |
| 总览级 | 前端 summary 页 / capability_matrix |

---

## 六、自动生成流程（测完即生成）

1. 跑样本 → 导出日志 → match → 得到 verdict（五态技术判定）；
2. AI 按本规范：五态 → 三态（对/疑问/错）+ conclusion + result_analysis；
3. 写入 `case_result_map.json` + 模块文档；
4. 前端 summary 页自动展示。

---

## 七、行业对比规范（每次总结必生成）

> 目的：把 IOA 的能力放进行业坐标系，判断它是「能力缺口」还是「行业常态」。

### 数据源

`config/industry_baseline.json`（53 category × Sysmon / MDE / CrowdStrike / SentinelOne），来源 EDR-Telemetry。

### 生成步骤

1. 每个 case 通过 `case_map`（case_id → 行业 category 英文名）找到行业 category；
2. 读出该 category 的 4 个参照产品判定（Yes / No / Partially / Via EventLogs / Via EnablingTelemetry）；
3. 与 IOA 三态对比，产出：

| 场景 | 结论 | 标签 |
|---|---|---|
| IOA 对 + 行业多数对 | 正常能力 | 🟢 行业对齐 |
| IOA 错/疑问 + 行业多数对 | IOA 的能力缺口 | 🔴 能力缺口 |
| IOA 错/疑问 + 行业多数错 | 行业常态缺口（不止 IOA 不采）| ⚪ 行业常态缺口 |
| IOA 对 + 行业多数错 | IOA 超行业能力（亮点）| ⭐ 领先行业 |

### 归一化规则

行业判定值归一化：`Yes`=有，`No`=无，其余（Partially / Via EventLogs / Via EnablingTelemetry / Pending Response）=部分。
「行业多数」= 4 参照产品中 ≥3 个「有」算「行业能采」，≥3 个「无」算「行业不采」，否则算「行业分歧」。

### 产出

- 行为级：写入 `result_analysis.industry`（如「行业 Sysmon=No/MDE=Yes/CS=Yes/S1=Yes，IOA 落后于 MDE/CS/S1」）；
- 总览级：summary 页「行业对比」列，一键看出 IOA 的 🔴能力缺口 与 ⚪行业常态缺口。
