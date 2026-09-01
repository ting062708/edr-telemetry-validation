# IOA 实例层（ioa/）

> 本目录存放**当前实例 = 腾讯 IOA** 的专属内容：模块采集结论、样本清单、行业基准等。
> 上层通用文档（`AI_ENGINE.md` / `chain/` / `STDOUT_SPEC.md` / `MAPPING_GUIDE.md`）**不含** IOA 专属细节，换目标 EDR 产品时本目录整体替换。

## 本目录内容

| 文件 | 作用 |
|---|---|
| `MODULES.md` | 各模块（Registry/File/Account/Driver/Network…）的 IOA 采集结论 + 关键认知 |
| `SAMPLE_INVENTORY.md` | 样本清单 + Migration gate |
| `BEHAVIOR_LEDGER.md` | 行为编号台账 |
| `FILE_SAMPLE_AUDIT.md` | File 样本审计 |

## 相关实例数据（在 `config/`，不在本目录）

| 文件 | 作用 |
|---|---|
| `config/test_cases.json` | 46 个 case 定义（match 规则 + expected_result） |
| `config/case_result_map.json` | 三态 baseline（对 / 疑问 / 错） |
| `config/ioa_field_mapping.json` | IOA 日志字段登记（json_fields） |
| `config/mappings/<module>/<case>.json` | 每 case 的 behavior_fields + observed_fields |
| `config/industry_baseline.json` | 行业基准（53 category × Sysmon/MDE/CS/S1） |

## 换目标产品时

1. 替换 `config/ioa_field_mapping.json` → 新产品字段映射；
2. 重造样本（`E:\EDR\EDRTelemetry\`）→ 新产品的行为触发方式；
3. 重跑 `chain/` 四步，产出新的 `MODULES.md` + `case_result_map.json`。
