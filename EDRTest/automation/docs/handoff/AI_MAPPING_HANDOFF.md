# AI 辅助映射自扩展——交接文档（新目标）

> **项目目标已更新（2026-08-24）**：不再追求"日志自动导出 + baseline 回归"的完整自动化；**重点放在「单模块的 AI 辅助映射自扩展」**——对每个行为模块，用「正向值扫描 + 反向剖析」自动发现/生成/扩展字段映射，判定 IOA 采集能力。
> 日志导出改为**手动导出**（不走自动化）。

---

## 一、核心流程（单模块，照这个走）

```
样本(触发行为, Migration gate 7 条)
  → 冻结协议 stdout（只补确定性字符串值）
  → 手动导出 IOA 日志(json)
  → ① 正向值扫描：stdout 值 → 扫日志找落点（tools/discover_mapping.py）
  → ② 反向剖析：日志有值字段 → 反推样本该补什么 stdout 值
  → ③ 生成映射：behavior_fields（值锚点）+ observed_fields（采集完整性）
  → ④ verdict 判定（三态：通过 / 通过(部分)? / 未通过）
```

①②交替迭代，**反向先行定"补什么"，正向验证"对上了没"**。

---

## 二、已有资产（直接复用，别重造）

| 资产 | 位置 | 作用 |
|---|---|---|
| 正向值扫描工具 | `tools/discover_mapping.py` | stdout 值 → 日志字段落点 |
| 映射校验 | `tools/check_mapping.py` | 校验映射文件 |
| 哈希审计 | `tools/audit_hashes.py` | 样本 MD5 审计 |
| 已定稿映射 | `config/mappings/<module>/<case>.json` | 5 模块 21 case |
| IOA 字段登记 | `config/ioa_field_mapping.json` | 日志字段名 → 语义 |
| 映射指南 | `docs/MAPPING_GUIDE.md` | 映射格式 + 工作流 + verdict 表 |
| stdout 规范 | `docs/STDOUT_SPEC.md` | 补值三原则 + 正反向剖析方法论 |
| 行为台账 | `docs/BEHAVIOR_LEDGER.md` | 53 行为编号 + 10 样本编号 |
| 重测清单 | `docs/RETEST_BACKLOG.md` | P0/P1/P2 分级待办 |
| 定稿结论 | `config/case_result_map.json` | 三态 verdict（v2.0.0）|

> 旧目标的 `docs/BASELINE_HANDOFF_V2.md`（baseline/diff 回归）**现在不用管**，除非以后要回归对比。

---

## 三、关键认知（别踩坑）

1. **三层 ground truth**：L0 样本声明 → L1 样本 API 回读事实 → L2 独立参照（Sysmon/ETW）。验证基准建在"事实"上，不是"样本自说自话"。
2. **导师标准（2026-08-23）**：部分情况有记录 = 通过。
3. **stdout 补值三原则**：只补「样本确定知道 + IOA 原样记录」的字符串值（账户名/文件名/路径/主机名）；避开枚举状态值（IOA 中文加工）、系统加工值（UAC、空文件 MD5）、不稳定值（SID）。
4. **锚点**：核心锚点 `Parent.FileMd5`（小写精确）+ `Common.EventTime`（±slack）；进程事件用 MD5，内核态/系统进程事件用对象值锚定（如账户名）或 `skip_process_anchor`。
5. **时间**：stdout 用 UTC（`TimeUTC=...Z`），匹配逻辑用 UTC，控制台才显示北京。
6. **采集延迟差异**：实时钩子类（文件/进程/注册表）毫秒级；异步/轮询/去重类（账户 lsass、文件建删、服务/计划任务）秒级到几十秒——所以 slack 设 pre5s/post30s，别按毫秒设。

---

## 四、未完成 / 下一步（按优先级）

1. **P0 重测**（7 条，见 RETEST_BACKLOG.md）：FILE-DELETE、REG-MODIFY、FILE-OPEN、NET-UDP、DRIVER-MODIFY、NET-URL、TASK×3；
2. **15 个待定稿 case**：Process6 / Hash3 / ScheduledTask3 / Service3（同学 baseline 已给结论，可占位标"待复测"）；
3. **P1 映射核对**（5 条）+ **P2 原理研究**（6 条，自扩展核心）；
4. **预留模块**（17 行为，编号已占位，样本未建）。

---

## 五、与 baseline 的分工（重要，避免撞车）

- **本项目主线（映射自扩展）**：按 File → Account → Network 逐模块深化，定稿映射 + verdict（三态）。
- **baseline（另一位 AI 全权）**：等映射定稿后，重打 `baseline` + `matrix --diff` 回归。它只消费定稿后的 verdict，不碰映射。
- **依赖关系**：baseline 数据源是 `match_result.json`，而它现在是旧数据（FILE 全 NOT_IMPLEMENTED）。**必须等映射重测/定稿后，baseline AI 才能重打 baseline——顺序不能反。**
- **给 baseline AI 的交代（详见 BASELINE_HANDOFF_V2.md）**：
  1. baseline/diff 已实现（`run_all.py` 的 `baseline` 子命令 + `matrix --diff`），别重写；
  2. 数据未定稿 → 重测 → 定稿 → 重打 baseline；
  3. 导师标准：部分=通过（三态 verdict）。

---

## 六、给新 AI 的下一步建议

1. 先读 `MAPPING_GUIDE.md` + `STDOUT_SPEC.md`（方法论）；
2. 从**一个模块**切入（建议先啃当前手头的 ScheduledTask，或按 RETEST_BACKLOG 的 P0 顺序）；
3. 每做一个模块，产出三样：`config/mappings/<module>/<case>.json` + `docs/<MODULE>_MODULE.md` + 更新 `case_result_map.json`（三态）+ 从 RETEST_BACKLOG 划掉已解决的。
