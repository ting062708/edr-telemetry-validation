# results/ 目录规范

本目录存放「IOA 采集能力验证」的**结果存档**（结论表），分模块组织、版本留痕。

## 目录结构
- `00_overview/`            当前全部 case 的汇总结果（xls/csv/txt）
- `by_module/<模块>/`       当前分模块结果，模块 = File / Account / Registry / Driver / Network
- `archive/<日期>_v<版本>/`  历史版本归档（每次改动前整体留档）
- `match_history/`          每次匹配的原始 match_result.json 归档（代码自动写入，勿手动改）

## 命名与版本规则
- 结果文件名固定为 `case_result_map.{xls,csv,txt}`
- 归档目录名 = `<YYYYMMDD>_v<X.Y.Z>`（日期 + 语义化版本号）
- **改动前**：把当前 `00_overview` + `by_module` 整体复制到 `archive/<日期>_<新版本>/`
- verdict 调整、判定标准变更，均在 `config/case_result_map.json` 的 `_meta.changelog` 留痕

## 与其他目录的关系
- 权威数据源：`config/case_result_map.json`（代码/前端读它，本目录是它的"人类可读副本"）
- 模块分析文档：`docs/*_MODULE.md`（IOA 记录逻辑剖析、特殊情况原因——不删，永久留档）
- 匹配过程留档：`runs/<module>/<case>/match_result.json`（最新）+ `results/match_history/`（历史归档）

## 判定标准（v2.0.0 起）
部分情况有记录即判定为通过（导师 2026-08-23）
- 通过 = 完整采集
- 通过(部分)? = 有记录但对样本变体不采，待确认（问号）
- 未通过 = 完全无记录

## 当前版本
v2.0.0（2026-08-23）。历史：v1.0.0 二元版见 `config/archive/case_result_map_v1_20260823.json`。
