# Baseline 进度交接文档（V2）— 2026-08-23

> 给负责 baseline 的 AI。**一句话核心：baseline/diff 命令已实现，但数据未定稿——正确顺序是「重测 → 定稿 case_result_map → 重打 baseline」，顺序不能反。**

---

## 一、已实现（别重复做，直接接着用）

| 项 | 位置/状态 |
|---|---|
| `baseline` 子命令（手动存，含规则指纹）| `run_all.py` 第 322 行 `cmd_baseline` ✅ |
| `matrix --diff` 回归对比 | `run_all.py` 第 353 行 `_cmd_diff`，输出 `runs/regression_diff.json` ✅ |
| `config/baseline.json` | 已生成（36 verdict，18 null，规则指纹 = mappings+test_cases 的 hash）✅ |
| 测后软关机 | `--shutdown-after`（deliverer.shutdown_after soft）✅ |
| `case_result_map.json` v2.0.0 | 三态 verdict + situations + changelog，21 个已定稿 ✅ |
| 行为台账 + 样本编号 | `docs/BEHAVIOR_LEDGER.md`（53 行为 / 10 样本编号）✅ |
| 重测清单 | `docs/RETEST_BACKLOG.md`（P0=7 / P1=5 / P2=6）✅ |
| 对比报告 | `results/comparison_classmate_20260823.md`（我的 21 case vs 同学 53 行为）✅ |
| ScheduledTask 样本改造 | COM API → `schtasks + XML`，MD5 已同步 ✅ |

---

## 二、核心问题：baseline 数据源未定稿（最重要，先读这条）

`baseline.json` 的 verdict 是从 `runs/<module>/<case>/match_result.json` 自动聚合的。**但 match_result.json 大量是旧/错数据**：

- FILE 模块 5 个 case 在 runs 里全是 `NOT_IMPLEMENTED`，但 `case_result_map.json` 定稿是 4 个"通过"（CREATE/DELETE/MODIFY/RENAME）——**旧数据，operation 字段没对的遗留**；
- Network 模块 runs 里 0 个 match_result，但定稿 3 采 2 不采。

**结论**：现在打出来的 baseline 是错的（FILE 全"不通过"）。必须：
1. 先重跑 match（用正确映射 + 日志）→ 得到正确的 match_result；
2. 定稿 `case_result_map.json`（三态）；
3. 最后才 `run_all.py baseline` 重打。

**判定权威看 `case_result_map.json`（三态），不拿 runs/ 的 match_result 当基准。**

---

## 三、未完成工作清单（按优先级）

### ① P0 —— 影响 baseline 结论（7 条，必须优先，详见 RETEST_BACKLOG.md）

| 行为 | 待办 |
|---|---|
| FILE-DELETE-001 | sleep5s 重测（建删去重，唯一可能"结论翻转"）|
| REG-MODIFY-001 | 启动项路径 + RegOldValData/RegValData 重测（同学重大发现）|
| FILE-OPEN-001 | JSON 文件重测（TXT 不采）|
| NET-UDP-001 | NetBind 监听重测（单播不采）|
| DRIVER-MODIFY-001 | 对齐"驱动修改"定义后改判"未通过"|
| NET-URL-001 | 改判"通过(部分)"（Host 有/Url 空），无需重测 |
| TASK-CREATE/MODIFY/DELETE | 样本已改 schtasks+XML，需重跑验证 SchedTaskCreate/Update |

### ② 待定稿 case（15 个，还没进 case_result_map）

- **Process（6）**：IMAGE-LOAD / CREATE / ACCESS / REMOTE-THREAD / TAMPER / TERMINATE
- **Hash（3）**：MD5 / SHA / IMPHASH
- **ScheduledTask（3）**：CREATE / MODIFY / DELETE
- **Service（3）**：CREATE / MODIFY / DELETE

> 同学的 baseline 已给结论（Process Creation/Access/RemoteThread/Tampering✅、Termination❌；Hash MD5✅/SHA❌/IMPHASH❌；ScheduledTask Creation✅Modification✅Deletion❌；Service Creation✅/Modification❌/Deletion❌），可直接填但标"同学结论，待复测"。

### ③ 预留模块（17 行为，样本未建，编号已占位）

VDISK / USB×2 / GPOLICY / PIPE×2 / AGENT×6 / WMI×3 / BIT / SCRIPT-BLOCK（详见 BEHAVIOR_LEDGER.md）

### ④ P1 映射核对（5 条）+ P2 原理（6 条）

详见 RETEST_BACKLOG.md。P2 属 AI 自扩展领域，可延后。

### ⑤ 杂项

- ~~`automation\1\` 误建目录~~ ✅ 已清理（2026-08-23，连同根目录误建的 `cd`/`None`/`python`/`match_result.json`/`run_metadata.json`/`probe_out.txt`/`normalized_events.json` 一并删除）；
- server.py 重启后新路由才生效（前端相关）；
- P3 待查：Process RemoteThread/Tamper、Hash 字段验证。

---

## 四、关键约束（别改）

1. **baseline 手动存**：跑 `baseline` 才更新，别自动更新（否则 diff 无意义）——已实现；
2. **diff 只读 match_result.json**，不碰 case_result_map.json——已实现；
3. **规则指纹**：区分"能力真变" vs "改了匹配规则"——已实现；
4. **case_result_map.json 是三态**（通过 / 通过(部分)? / 未通过），别退回二元；
5. **版本留痕**：改动前先归档（`config/archive/`、`results/archive/`），changelog 记录，不删旧结论。

---

## 五、关键认知（三层 ground truth，答辩方法论）

- **L0 意图**（样本声明）→ **L1 事实**（样本 API 回读确认）→ **L2 独立参照**（Sysmon/ETW 平行采集器）；
- 验证基准要建在"事实"上，不是"样本自说自话"；
- **五态 verdict**（match_result）：IMPLEMENTED / PARTIALLY_IMPLEMENTED / NOT_IMPLEMENTED / PENDING / VIA_WINDOWS_EVENTLOG（+错误态 ERROR_SAMPLE / ERROR_LOG_INPUT / AMBIGUOUS）；
- **三态 case_result_map**（定稿）：通过 / 通过(部分)? / 未通过——两个是不同层，别混；
- 导师标准（2026-08-23）：**部分情况有记录 = 通过**；
- 已知时间戳偏移问题（process.image_load 偏很久，疑似异步上报/轮询采集）已入 P2。

---

## 六、待用户拍板（先别动）

1. **L2 独立参照**：是否装 Sysmon 当参照系（A 装 Sysmon / B 用 ETW / C 暂不装）——决定 baseline 可信度上限；
2. **DRIVER-MODIFY 定义**：改 .sys 文件（文件修改）≠ 改驱动配置（真驱动修改），需和导师对齐。

---

## 七、给 baseline AI 的下一步（建议顺序）

1. **重跑 FILE 模块 5 个 case 的 match**（旧 match_result 是错的，这是最大的数据污染源）；
2. **重测 P0 的 7 条**（尤其 FILE-DELETE 的 sleep5s、REG-MODIFY 的启动项路径、TASK 的 schtasks+XML）；
3. **定稿 15 个待定稿 case**（可先用同学 baseline 结论占位，标"待复测"）；
4. **重打 baseline**（`run_all.py baseline`）；
5. 之后才用 `matrix --diff` 做回归演示。

---

## 八、L2 Sysmon 参照工程实录（Base 2026-08-24，已落地验证）

**方法论归属**：见 `AI_MAPPING_METHODOLOGY.md` 第八节；本节只记工程实现细节。

### 8.1 IOA_Sysmon 快照（已创建）

- 流程：回退 `IOA`（原快照里 **Sysmon 未安装**）→ 全新安装 Sysmon v15.21 + SwiftOnSecurity 配置（config hash `055FEBC6...`）→ 日志上限调 256MB（`WINEVT\Channels\Microsoft-Windows-Sysmon/Operational` 的 MaxSize=0x10000000、Retention 覆盖、AutoBackup 开）→ 清空日志 → 硬关机（soft 两次超时，guest 卡关机，改用 hard）→ 打快照 `IOA_Sysmon`。
- 快照内保留：`C:\EDRTest\Sysmon64.exe` + `C:\EDRTest\sysmonconfig.xml`（探针文件已删）。
- 配置注意：**Image loading 全局关闭**（噪音大）——测 `PROC-IMAGE-LOAD-001` 需 `Sysmon64 -c` 临时开；哈希 MD5/SHA256/IMPHASH 全开（Hash 模块 L2 参照可用）。

### 8.2 Sysmon 日志自动导出 hook（代码已接入）

- `core/deliverer.py`：新增 `Deliverer.export_sysmon_log(out_dir, case_id)`——guest 内 `wevtutil epl Microsoft-Windows-Sysmon/Operational` 导出 evtx → 回传 host `runs/<module>/<case>/sysmon_<case>.evtx` → 清理 guest 临时 evtx。快照未装 Sysmon 时降级跳过（WARN，不阻断 run）。
- `runner/telemetry_runner.py`：新增 `_export_sysmon_log()`，调用点在 `cmd_run` / `cmd_deliver` 的 stdout 落盘之后、**下一次 run 的 snapshot revert 之前**（revert 会清掉 guest 本地日志，所以必须在每次 run 末尾导出）。

### 8.3 已验证全链路（FILE-CREATE-001）

- evtx 2.2MB / 1357 事件；ID1 含样本进程 `Image=C:\EDRTest\samples\File\FileLifecycleTest.exe`；ID11 含行为 `Target=...FileLifecycle_Target.exe`。
- **host 读 evtx 时 `Message` 为 null**（host 无 Sysmon provider manifest），但 `Properties[]` 数组完整——写 evtx 解析器时用 `Get-WinEvent -Path x.evtx` 读 `Properties[4]`(ID1 Image) / `Properties[5]`(ID11 Target) 等，不要依赖 Message。

### 8.4 snapshot 优先级坑（已修复）

- `_resolve_snapshot` 优先级：case 级 `test_case['snapshot']` > `vm.snapshot`。`test_cases.json` 里 33 个 case 原本写死 `"snapshot": "IOA"`，导致 revert 到旧 IOA（无 Sysmon）。已批量迁移为 `IOA_Sysmon`；Driver 3 个保持 `Baseline_Driver`。

### 8.5 遗留

- `Baseline_Driver` 快照未装 Sysmon——Driver 重测前单独装一遍并重打快照；
- host 侧 evtx 解析工具（evtx → 扁平 JSON 便于与 IOA 对照）待写；
- vmrun 已知行为：locked/headless guest 用 runProgramInGuest 不要加 `-activeWindow`；run_via_bat 的 vmrun 非零返回多为良性（样本退出码以 stdout [RESULT] 为准）。

