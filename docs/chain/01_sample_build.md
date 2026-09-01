# 行为链 ① 样本构建（chain/01_sample_build.md）

> 版本：v1.0.0 ｜ 更新：2026-08-24 ｜ 上游：无 ｜ 下游：② 跑样本
> 一句话：按行业规范造样本，Sysmon↔IOA 交替验证收紧（3 次失败记样本失败）。

## 一、自动化实现（现状）

- 参照行业规范：EDR-Telemetry category 定义 + Atomic Red Team / MITRE 评估惯例（文件操作测**攻击者真实会动的类型**，如 .exe/.ps1/.js/.dll，而非空文件或 .txt）；
- 冻结协议 stdout：`STDOUT_SPEC.md`（统一 `TimeUTC=...Z`、[TARGET] 块确定性值）；
- 接入门槛：`SAMPLE_INVENTORY.md` Migration gate 7 条（非交互命令行 / SETUP 只建前置 / TARGET 单行为 / UTC+ PID / 退出码 0/1/2 / 幂等清理 / .NET Framework 4.7.2 Release x64）；
- 样本编号：`BEHAVIOR_LEDGER.md`（S-001~S-017）。

## 二、目前规则

- **Sysmon ↔ IOA 交替验证制作收紧样本**：先用样本触发 → 用 Sysmon（L2）确认"行为确实发生"→ 用 IOA 看"采没采到"→ 采不到就调**触发方式**（不是调锚点值）；
- **交替上限 3 次**（全局提示词 #2）：3 次迭代仍未收敛 → 记「样本失败 / 待拍板」，不无限循环。

## 三、问题记录（编号）

### 已解决
| 编号 | 问题 | 结论 |
|---|---|---|
| SAMPLE-01 | 冻结协议 stdout 定稿 | STDOUT_SPEC.md，禁 DateTime.Now / ToString("o") |
| SAMPLE-02 | 计划任务触发方式 | COM API → `schtasks + XML`（IOA 才采）|
| SAMPLE-03 | File 样本版本链 | 空文件 .exe → 有内容 .txt 全周期（间隔 10s 避开建删去重）|

### 未解决
| 编号 | 问题 | 状态 |
|---|---|---|
| SAMPLE-11 | **目标文件类型拍板**（方案 A 有内容 .exe vs B 维持 .txt）| 待用户拍板 |
| SAMPLE-12 | Sysmon 配置不含 .txt（FileCreate/Delete 盲区）| 待补规则 + 重打快照 |
| SAMPLE-13 | stdout_parser 全周期适配（5 phase 只取 1）| 待改 parser |

## 四、编号与版本规则

- 问题编号：`SAMPLE-<序号>`（01~10 已解决，11 起未解决）；解决后不改号，新增递增。
- 规则版本：本文件版本号 vX.Y.Z；规则变更 → 次版本 +1，结构变更 → 主版本 +1；changelog 见 `AI_CHAIN_LOG.md`。
