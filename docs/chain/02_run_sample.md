# 行为链 ② 跑样本（chain/02_run_sample.md）

> 版本：v1.0.0 ｜ 更新：2026-08-24 ｜ 上游：① 样本构建 ｜ 下游：③ 找映射
> 一句话：跑样本 → 更新 stdout → 返回时间段 → 提示导出日志 → 手动导出 → 提交指定区。

## 一、自动化实现（现状）

- 投递执行：`runner/telemetry_runner.py` 的 `run` / `run_all.py` 的 `deliver`（投递到 VM → 执行 → 捕获 stdout）；
- stdout 落盘：`runs/<module>/<case>/<case>_stdout.txt`（含 [RUN-BEGIN] 时间窗 + [TARGET] 块）；
- Sysmon 参照：`deliverer.export_sysmon_log()` 自动导出 `sysmon_<case>.evtx` 回传 host（L2 平行对照）；
- 环境管理：快照三态（required/never/auto）+ 含 Sysmon 的快照（实例名见 vm_config）+ 测后软关机 `--shutdown-after`。

## 二、目前规则

- 跑完 → 返回**时间段**（stdout 的 [RUN-BEGIN]~[RUN-END]）；
- 提示"**导出增长时间范围后的日志**"（覆盖时间段 + 前后 slack）；
- **手动导出**（自动化导出未完成），提交到指定区（前端「+ → 导入日志」上传到 `log/<module>/`）：
  - **首选路径**：`log/<module>/json/*.json`（最规范，探测第一优先）；
  - `<module>` = `test_cases.json` 的 `module` 字段，**首字母大写**（File / Registry / Account / Network / Driver / Process / Hash / ScheduledTask / Service，**非**小写 file/registry——注意与 `config/mappings/` 的小写目录不同）；
  - 探测范围（`server.py _list_log_candidates`）：`log/<module>/json` → `log/<module>` → `log` 根，且三个 log 根目录都会扫（`automation/log`、`EDRTest/log`、`EDR/log`）；
  - 命中排序：mtime 最新优先 + 文件名含 case_id 优先。
- MD5 跑前自检，不匹配自动写回 `test_cases.json`（`audit_hashes.py`）。

## 三、问题记录（编号）

### 已解决
| 编号 | 问题 | 结论 |
|---|---|---|
| RUN-01 | revert 错快照（旧 IOA 无 Sysmon）| case 级 `snapshot` 优先级 > vm_config，33 case 迁 `IOA_Sysmon` |
| RUN-02 | 测后残留污染 | `--shutdown-after` 软关机 |
| RUN-03 | 样本 MD5 不同步 | `audit_hashes.py --update` 全自动 |

### 未解决
| 编号 | 问题 | 状态 |
|---|---|---|
| RUN-11 | **自动化导出日志未完成**（手动导出；注意目标产品控制台**筛查条件**要选对，否则误以为无日志）| 手动导出兜底 |
| RUN-12 | runs 目录杂乱（历史 UUID stdout、20MB normalized_events）| 待整理（方案已定，见 AI_CHAIN_LOG）|

## 四、编号与版本规则

- 问题编号：`RUN-<序号>`（01~10 已解决，11 起未解决）。
- 规则版本：本文件版本号 vX.Y.Z；changelog 见 `AI_CHAIN_LOG.md`。
