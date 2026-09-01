# 项目目录与文件说明（PROJECT LAYOUT）

> 定位：整个 `automation/` 项目的「地图」——每个目录、每个关键文件是干什么用的。
> 更新：2026-08-24

---

## 一、顶层目录一览

| 目录 | 作用 | 谁读写 |
|---|---|---|
| `config/` | 配置中心：case 定义、verdict、映射、VM、行业基准 | 代码读，人改 |
| `core/` | 核心逻辑：匹配、规范化、stdout 解析、verdict、状态、投递 | 代码 |
| `runner/` | 命令行入口 | 代码 |
| `tools/` | 工具脚本：值扫描、映射校验、哈希审计 | 代码/人 |
| `docs/` | 文档中心：AI 工程 + 原项目方法 + 台账 + 模块分析 | 人 |
| `runs/` | 运行产物：每 case 的 stdout / match_result / evtx | 代码写，人看 |
| `log/` | 导出的 IOA 日志（json） | 人导，代码读 |
| `results/` | 结果归档：总览 / 分模块 / 历史 | 代码/人 |

---

## 二、各目录关键文件

### `config/`（配置中心）

| 文件 | 作用 |
|---|---|
| `test_cases.json` | 36 个 case 定义（id/module/behavior/sample/md5/match/expected_result）|
| `case_result_map.json` | **三态 verdict 权威表**（v3.0.0：对/疑问/错 + note/situations）|
| `case_result_map.{csv,txt,xls}` | 结果表的人类可读导出副本 |
| `mappings/<module>/<case>.json` | 字段映射（behavior_fields + observed_fields），module 小写 |
| `vm_config.json` | VM 配置（vmrun/vmx/凭据/快照/样本路径）|
| `ioa_field_mapping.json` | IOA 日志字段登记（json_fields）|
| `baseline.json` | baseline 快照（rule_fingerprint + verdicts）|
| `industry_baseline.json` | 行业基准（53 category × Sysmon/MDE/CS/S1）|
| `archive/` | case_result_map 历史版本归档 |

### `core/`（核心逻辑）

| 文件 | 作用 |
|---|---|
| `matcher.py` | 匹配引擎：主机 + 时间窗 + 进程 + PID + MD5 锚点 + 字段验证 |
| `normalizer.py` | 日志规范化：IOA JSON/CSV → 扁平事件（EventTime/Parent/Child）|
| `stdout_parser.py` | 冻结协议 stdout 解析（TARGET 字段 → target_fields）|
| `verdict.py` | verdict 判定（五态 + 三错误态）|
| `status.py` | 状态聚合 collect_status（前端数据源，binary 四态 + result 三态）|
| `deliverer.py` | 投递执行：VM 投递、快照恢复、Sysmon evtx 导出 |

### `runner/`

| 文件 | 作用 |
|---|---|
| `telemetry_runner.py` | CLI：run / deliver / match / inspect-csv 等 |

### `tools/`（工具脚本）

| 文件 | 作用 |
|---|---|
| `discover_mapping.py` | 正向值扫描：stdout 值 → 日志字段落点 |
| `check_mapping.py` | 映射校验 |
| `audit_hashes.py` | 样本 MD5/SHA256 审计（--update 同步）|

### `docs/`（文档中心，分组导航）

| 组 | 文档 | 作用 |
|---|---|---|
| **端到端方法** | `E2E_VALIDATION_METHOD.md` | 原项目主流程：样本→Sysmon 验证→跑测试→对比收敛→判定 |
| **AI 工程** | `AI_ENGINE.md` + `chain/` 4 文件 | 全局总纲（目标/规范/提示词）+ 4 行为链 |
| 目标方法论 | `AI_MAPPING_METHODOLOGY.md` | 目标、内核/适配层、收紧方式边界 |
| 总结规范 | `AI_SUMMARY_SPEC.md` | AI 总结 baseline 规范 + 行业对比 |
| 链路台账 | `AI_CHAIN_LOG.md` | 链路拆解 + 完成状态 + 搁置待办 + changelog |
| stdout 规范 | `STDOUT_SPEC.md` | 冻结协议 + 补值三原则 + 正反向剖析 |
| 映射指南 | `MAPPING_GUIDE.md` | 映射文件格式 + 工作流 + verdict 表 |
| 样本清单 | `SAMPLE_INVENTORY.md` | 样本清单 + Migration gate 7 条 |
| 行为台账 | `BEHAVIOR_LEDGER.md` | 53 行为编号 + 样本编号 |
| 重测清单 | `RETEST_BACKLOG.md` | P0/P1/P2 待办 |
| 行业基准 | `EDR_TELEMETRY_BASELINE.md` | 行业 EDR 采集能力矩阵 |
| 模块分析 | `*_MODULE.md`、`FILE_SAMPLE_AUDIT.md` | 各模块结论 + 样本审计 |
| 交接 | `BASELINE_HANDOFF_V2.md`、`FRONTEND_HANDOFF.md`、`AI_MAPPING_HANDOFF.md` | 子系统交接 |
| 关于 | `ABOUT.md` | 前端「关于」页 |

### `runs/`（运行产物）

- 每个模块每个 case 一个目录：`runs/<Module>/<CASE-ID>/`
- 目录内：`<case>_stdout.txt`（最新）、`sysmon_<case>.evtx`（L2 参照）、`match_result.json`、`run_metadata.json`、历史 UUID stdout
- 顶层：`progress.json`（断点续跑）、`regression_diff.json`（回归对比）

### `results/`（结果归档）

| 子目录 | 作用 |
|---|---|
| `00_overview/` | 全部 case 汇总（xls/csv/txt）|
| `by_module/<Module>/` | 分模块结果 |
| `archive/<日期>_v<版本>/` | 历史版本留档 |
| `match_history/` | 历史 match_result.json 归档 |

### `log/`（导出的 IOA 日志）

- `log/<模块大写>/json/*.json` —— 首选路径（探测 `json/` → `<module>/` → `log` 根）

---

## 三、一次完整验证走哪些文件（数据流）

```
改样本(源码 E:\EDR\EDRTelemetry\<Module>\) → 编译 → samples\<Module>\
   ↓ runner\telemetry_runner.py run --case <CASE-ID>
   ↓ core\deliverer.py 投递 VM 执行 → 捕获 stdout → runs\<Module>\<CASE>\<case>_stdout.txt
   ↓ 导出 Sysmon evtx → runs\<Module>\<CASE>\sysmon_<case>.evtx
   ↓ 人导 IOA 日志 → log\<模块大写>\json\*.json
   ↓ runner match → core\matcher.py + core\normalizer.py + core\stdout_parser.py
   ↓ core\verdict.py 判定 → runs\<Module>\<CASE>\match_result.json
   ↓ 人定稿 → config\case_result_map.json（三态）
   ↓ 前端 / summary.html / 结果表导出（results\）
```

---

## 四、待清理 / 待优化（见回复中的优化方案）

- 根目录散落临时日志（`*.log`/`*.out.log`/`*.err.log`）
- `core/stdout_parser.py.bak`、`tools/_fix_file_cases.py`
- `config/` 与 `results/00_overview/` 的结果表副本重复
- `README.md` 内容过时（旧协议）
