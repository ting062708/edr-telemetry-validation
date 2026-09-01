# 归档（Archive）

> 本文档是项目的**决策与变更归档**。所有重要的逻辑决策、行为链重构、方法优化或修改，以及尚未自动化的预留部分，都必须在这里登记，编号记录，方便未来复查与回档。

---

## 一、归档原则（所有重要决策 / 问题必须归档）

**必归档事项：**

1. 整个流程中尚未考虑实现的自动化（如 USB 插拔、EDR 运维、云端导出日志）→ 记录「未实现 + 原因 + 预留接口位置」。
2. 未来的重要逻辑决策（行为链重构、方法优化、方案修改）→ 记录「决策内容 + 原因 + 影响」。
3. 重大失误 / 错误（如「声称完成但未落地」这类）→ 记录「错误内容 + 原因 + 防止再犯措施」。
4. 写完关键文件一律 read_file 回读确认真实落地，再对外声称完成；不凭工具返回就宣布完成。

**归档格式**：每条归档加编号（如 `ARC-001`、`ARC-002`），方便未来复查；编号永不重用。

**可回档**：归档后随时可查、可回滚（需要时按对应编号即可恢复当时状态）。每条归档保留「原状态 → 新状态」对照。

---

## 二、全局提示词（自验证 + 决策权收敛）

1. **自验证**：每个行为先思考「怎么验证这个行为是对的」——不是做完就完，要能证明对。
2. **优化方案**：每个行为先思考「有没有更好的方案」——不是想到一个就做，要比较。
3. **收敛到决策权**：优化到「给出方案 + 利弊」，我只需要拍板——不是我选最优解，而是你给出最优解 + 我确认。
4. **实事求是**：不确定就说不确定，不猜测、不侥幸、不编造。
5. **指令研判**：对我的指令进行思考，判断我的指令会不会影响最终目标实现。
6. **决策必归档（自动，无需询问）**：每个重要逻辑决策、行为链重构、方法优化、修改，以及重大失误/错误，都必须在落地时立即归档（写进 ARCHIVE.md，编号记录、回读确认）——不得攒批补记；归档自动执行，**无需征求用户同意，直接记录**。
7. **例外**：不确定时可以不遵循「收敛到决策权」——直接说「我不确定，需要你确认」。

---

## 三、未自动化的部分（预留接口，不写代码）

| 编号 | 内容 | 状态 | 说明 |
|---|---|---|---|
| ARC-001 | **USB 插拔**（DEVICE-USB-MOUNT-001 / DEVICE-USB-UNMOUNT-001） | 预留，不实现 | 需要真实 USB 设备，不适合自动化投递。保留在 `status.py` RESERVED_MODULES。 |
| ARC-002 | **EDR 运维**（AGENT-START/STOP/INSTALL/UNINSTALL/KEEPALIVE/ERROR 共 6 项） | 预留，不实现 | 属运维行为，非样本可触发。保留在 `status.py` RESERVED_MODULES。 |
| ARC-003 | **云端日志导出**（IOA 云端 → 本地 JSON） | 未自动化，需人工 | 目前由人工在 IOA 后台导出。样本 stdout 为 UTC，导出时须选对时间范围（覆盖样本运行时间窗），否则 NOT_COVERED。 |

---

## 四、已实施的重要逻辑决策（按编号回档）

### ARC-101　判定标准变更：进程锚定 → 能力存在性
- 日期：2026-08-24　类型：行为链重构 / 逻辑决策　状态：已实施
- **原**：matcher 用 actor/PID/MD5 锚定链过滤，capability 仅作兜底。导致 File 模块样本进程文件事件为 0 条时，靠系统进程的同类事件误判「采集到」。
- **新**：`capability_detected`（云端日志 operation 匹配，即能力存在性）升格为主结论；锚定降级为辅助证据，不再决定对错。
- 影响文件：`core/matcher.py`、`core/verdict.py`。

### ARC-102　verdict 三态化
- 日期：2026-08-24　类型：逻辑决策　状态：已实施
- **原**：五态（IMPLEMENTED/PARTIALLY/NOT/PENDING/VIA_WINDOWS_EVENTLOG + 错误态）。
- **新**：三态语义——**对**（能力存在+精确变体命中）、**错**（无该行为事件）、**疑问**（有基础事件但精确变体未采到）。保留五态枚举名兼容前端，新增 base/full 两层 capability 判定。

### ARC-103　case_id 统一：WMI-BINDING-001 → WMI-BIND-001
- 日期：2026-08-24　类型：命名统一　状态：已实施
- **原**：样本 `WmiActivityTest` 用 `WMI-BINDING-001`，体系用 `WMI-BIND-001`。
- **新**：统一为 `WMI-BIND-001`（对齐 `status.py` / 前端 `CASE_CN`）。

### ARC-104　module 统一：VirtualDisk → Device
- 日期：2026-08-24　类型：命名统一　状态：已实施
- **原**：样本 `VirtualDiskMountTest` 输出 module=`VirtualDisk`。
- **新**：统一为 `Device`（对齐 RESERVED_MODULES / MODULE_DISPLAY）。

### ARC-105　PIPE-DISCONNECT-001 删除
- 日期：2026-08-24　类型：范围裁剪　状态：已实施
- **原**：Pipe 样本含 create/connect/disconnect 三个 case。
- **新**：删掉 disconnect，仅保留 `PIPE-CREATE-001`、`PIPE-CONNECT-001`（对齐 baseline 的 2 项）。

### ARC-106　GPO 样本改 HKCU（免管理员）
- 日期：2026-08-24　类型：方法优化　状态：已实施
- **原**：`GroupPolicyModifyTest` 写 `HKLM\...\Policies\System`，需管理员权限。
- **新**：改为 `HKCU\...\Policies\Explorer`（用户可写，仍属组策略标准位置，IOA 仍按 RegSetValue + RegGroupName 检测），移除 IsAdministrator 检查。

### ARC-107　Process 模块 pre_start 前置逻辑
- 日期：2026-08-24　类型：方法优化　状态：已实施
- **原**：terminate/access/remotethread/tamper 需预先有 `ProcessTarget.exe` 在运行，自动化投递不启动，导致 FAIL。
- **新**：`deliverer.py` 新增 pre_start 逻辑——case 配置 `pre_start` 时，投递后先 `start ""` 后台启动 target 再跑样本；`test_cases.json` 给这 4 个 case 加 `"pre_start": "ProcessTarget.exe"`。

### ARC-108　预留模块接入前端（9 case）
- 日期：2026-08-24　类型：范围扩展　状态：已实施
- **内容**：新增 9 个 case 接入 `test_cases.json` + `config/mappings/`——Pipe×2、WMI×3、Device-VDISK×1、GPO×1、BITS×1、PowerShell×1。
- 注意：operation 字段对 ✅ 模块（Pipe=NamedPipe / GPO=RegSetValue / PS=ScriptScan）用同学实测值；对 ❌ 模块（WMI=WmiCreate / BITS=BitsJobCreate / Device=VirtualDiskMount）用样本 stdout 的 Operation 值，**待日志导出后校准**。

### ARC-109　日志导出时机 / 事件类型坑（导早了 + 导错表）
- 日期：2026-08-25　类型：问题记录 / 操作坑　状态：已记录，避免再犯
- **现象**：File 创建样本（FILE-CREATE-001）跑完导出的日志，只有 ProcEvents（ProcessCreate ×114）+ CmdLineAssocEvents（×4），**0 条文件事件**（无 FileWriteClose / FileCreate），样本创建的 `FileLifecycle_Target.dll` 在日志里 0 命中。
- **原因（两个坑叠加）**：
 1. **导早了 / 时间范围没覆盖**：导出时间范围早于或未完整覆盖样本运行窗口。样本 stdout 是 UTC，IOA 云端是北京时间，差 8 小时，选时间要换算（或直接选全天）。
 2. **导错表**：IOA 云端日志按事件类型分表（ProcEvents / FileEvents / …），这次只导了进程表，没导文件表。
- **正确做法**：
 1. 导出时间范围选**全天**，或明确覆盖样本运行时间窗 ± 余量。
 2. 样本跑完后**等 IOA 云端数据落库 / 同步**（有延迟）再导出。
 3. 按**事件类型分表导出**——验证哪个能力就导哪张表（文件行为 → FileEvents，进程行为 → ProcEvents）。
 4. 导出后自查：日志里至少应有样本进程的 ProcessCreate，且应有目标行为类型的事件；两者缺一即为导出范围 / 类型有误。

### ARC-110　Sysmon 现状：L2 参照半闭环
- 日期：2026-08-25　类型：现状记录　状态：已记录
- **已实现**：`deliverer.export_sysmon_log`（`wevtutil epl Microsoft-Windows-Sysmon/Operational` → copy 回本地），在 deliver/run 后、快照回滚前自动执行；当前已有 24 个 `runs/<模块>/<CASE>/sysmon_<CASE>.evtx`。
- **未实现**：evtx 解析工具（`tools/` 下暂无），即「导出 ≠ 可用」。
- 用途：当 IOA 未采到样本行为时，用 Sysmon 佐证「样本确实执行了该行为」（区分「IOA 没采」与「样本没执行」）。

### ARC-111　映射更新规则（拍板制）
- 日期：2026-08-25　类型：流程规则　状态：已生效
- **规则**：映射（behavior_fields / observed_fields）变更，须用户拍板确认后才生效；拍板后 AI 直接更新 `docs/MAPPING.md` + `config/mappings/*.json` + `docs/MAPPING_CHANGELOG.md`（记 MAP 编号）。
- 决策由用户提出、AI 执行；AI 不得自行改动映射语义。

### ARC-112　evtx 解析工具 parse_evtx.py
- 日期：2026-08-25　类型：新增工具　状态：已实施
- **内容**：`tools/parse_evtx.py`，用 PowerShell `Get-WinEvent` 做后端（python-evtx 未安装，Windows 原生可读 evtx），支持 EventID 分布统计、字段搜索、JSON 输出。
- 用法：`python tools\parse_evtx.py <evtx> [--search 关键词] [--field 字段 --top N]`。

### ARC-113　前端映射显示（mapping API + 卡片）
- 日期：2026-08-25　类型：方法优化　状态：已实施
- **内容**：`server.py` 新增 `/api/case/<id>/mapping`（返回 behavior_fields + observed_fields）；`index.html` 新增「映射」卡片（match 视图展示）。
- **附带修复**：module 大小写 bug——`config/mappings/` 目录是小写（file），`test_cases.json` 的 module 是大写开头（File），mapping API 需 `module.lower()` 才能命中路径。

### ARC-114　Sysmon 佐证 IOA 漏采（目标文件是 .exe 不是 .dll）
- 日期：2026-08-25　类型：重要发现　状态：已记录
- **发现**：用 parse_evtx 分析 `sysmon_FILE-CREATE-001.evtx`，Sysmon 完整采到了样本文件创建（EventID 11 FileCreate，Image=FileLifecycleTest.exe → TargetFilename=**FileLifecycle_Target.exe**）。
- **纠正**：样本创建的目标文件是 `FileLifecycle_Target.exe`（**.exe 不是 .dll**，此前多处记成 .dll）。
- **结论**：IOA 没采到样本进程的文件创建（全表日志 FileLifecycle_Target 0 命中），但 Sysmon 采到了——坐实「IOA 漏采」，排除「样本没执行」。
- 教训：Sysmon 的 Message 字段为空（manifest 未注册），之前用 Message 匹配误判「FileLifecycle 命中 0」，实际 EventData 字段（TargetFilename/Image）里有。

### ARC-115　能力判定：全量 → 时间窗内（主结论改动）
- 日期：2026-08-25　类型：行为链重构　状态：已实施
- **原**：`capability_detected` 在全量 events 上找 operation（「能力是全局的」）。
- **新**：改为在时间窗内（`window_pool`，stdout 时间 ± pre/post_slack）匹配锁定——主结论回归「样本运行窗口内 IOA 有没有留痕」。
- 原因：全量会扫到历史/其他进程事件，几乎总判「通过」，失去区分度；时间窗内才对应「样本这次运行」。
- 影响文件：`core/matcher.py`（capability_detected / capability_base_detected 均改 window_pool）。

### ARC-116　方法论：先 match 后找映射
- 日期：2026-08-25　类型：方法论　状态：已生效
- **顺序**：先 match（定 operation + capability_probe，判采到/没采到）→ 再找映射（对「采到」的 case 跑值扫描写 behavior_fields）。
- 原因：match 主结论（能力判定）不依赖映射；而值扫描需「日志里有样本值」，对未采到的 ❌ 模块扫不到，先找映射会卡死。

### ARC-117　数据源角色定位（简化版）
- 日期：2026-08-25　类型：逻辑澄清　状态：已生效（此前「三角色分工」过度设计，本条目已简化为最终版）
- **stdout**：提供时间窗（RUN-BEGIN~RUN-END）+ 对象值 V，是匹配锁定的锚点来源。**必需**。
- **IOA 日志**：被验证对象，看「时间窗内有没有采到 V 的记录」。**必需**。
- **Sysmon**：**可选辅助兜底**——只在「IOA 没采到、需确认样本确实做了行为」时用。**非必需**。
- 判定：时间窗内用 operation + V 锁定，有记录 = 采到；无记录 = 没采到。

### ARC-118　重大失误：声称落地但实际未落地
- 日期：2026-08-25　类型：重大失误 / 错误　状态：已记录，防止再犯
- **错误**：上一轮声称「补了 6 条归档 ARC-112~117」，实际只写入沙箱，真实环境 `ARCHIVE.md` 只到 ARC-111。
- **原因**：edit_file 后未回读确认，凭工具返回即声称完成。
- **防止再犯**：写完关键文件一律 read_file 回读确认真实落地，再对外声称完成；错误级失误也要归档。

### ARC-119　批量/全量跑样本的两个问题（module 大小写 + EXE 缺失）
- 日期：2026-08-25　类型：问题修复　状态：已修复
- **问题1：module 大小写过滤**——`run_all.py` 的 `_select`/`cmd_status`/`cmd_matrix` 用精确匹配 `c.get('module') != args.module`，test_cases.json 里 module 是大写（Pipe/WMI/Device/…），用小写 `--module` 会「Nothing to deliver」。修复：改为 case-insensitive `.lower()`（3 处）。
- **问题2：3 个样本 EXE 缺失**——GPO/BITS/PowerShell 未编译，全量投递失败。修复：用 csc.exe 编译 GroupPolicyModifyTest.exe / BitsJobTest.exe / PowerShellScriptBlockTest.exe，放进 `samples/GPO`、`samples/BITS`、`samples/PowerShell`。
- 备注：快照策略 File/Account=required（每 case 强制恢复快照、批量慢），ScheduledTask/Service=never；Driver 用 Baseline_Driver 快照。

### ARC-120　命名统一（GPO / BIT / ScheduleTask / WMI-CONSUMER-TO-FILTER-001）
- 日期：2026-08-25　类型：命名统一　状态：已实施
- **决策**：module 名统一——GPO（不变）、BITS→BIT、ScheduledTask→ScheduleTask；case_id WMI-BIND-001→WMI-CONSUMER-TO-FILTER-001。
- **涉及**：test_cases.json（7 处）、status.py（2 处）、index.html（3 处）、config/mappings（bits→bit 目录 + 2 文件重命名）、samples/EDRTelemetry（目录重命名）、WMI 源码 + 重编译 EXE。
- **验证**：45 case JSON 有效、残留 0、status.py 编译通过、WMI EXE UTF-16 验证 case_id 已更新。

### ARC-121　快照策略：ScheduleTask/Service never→required（执行隔离 vs 分析隔离）
- 日期：2026-08-25　类型：逻辑决策　状态：已实施
- **决策**：ScheduledTask/Service 的快照策略从 never 改成 required（方案 A：判定可靠优先，宁可慢不要不可信）。
- **附改名对齐**：snapshot_policy_map 的 key "ScheduledTask"→"ScheduleTask"（module 改名后的遗漏，已补）。
- **核心结论**：快照恢复是「执行层隔离」（样本执行时 VM 干净、行为纯），时间窗是「分析层隔离」（只看样本运行窗口日志），两者互补、不可替代——时间窗救不了「样本因残留而 FAIL」。
- 影响文件：`config/vm_config.json`（snapshot_policy_map）；解析逻辑 `telemetry_runner.py` `_resolve_snapshot`（case 级 → module 级 → 全局 auto）。

### ARC-122　前端功能增强（中断/全量投递/批量归档 + 删快照开关）
- 日期：2026-08-25　类型：功能增强　状态：已实施
- **决策必归档入提示词**：全局提示词新增第 6 条「决策必归档」（每个决策落地立即归档、回读确认）。
- **删「不恢复快照」开关**：快照策略改 required 后该开关失效，删除（buildInfoBar 的 toggle）。
- **中断增强**：server.py `Task.stop()` 从 `proc.kill()`（只杀 python）改为 `taskkill /PID /T /F`（杀整个进程树，含 vmrun），解决「停不干净」。
- **全量投递**：server.py 新增 `/api/all/deliver`（run_all.py deliver 不带 --module）；前端加号菜单新增「全量投递」。
- **批量输出归档**：run_all.py `cmd_deliver` 打印 `===CASE-BEGIN/END===` 边界标记；前端 `streamTask` 解析标记，把每个 case 的输出段 saveHistory 到对应 case 卡片。
- 验证：server.py / run_all.py 编译通过，index.html JS 语法通过（vm.Script）。

### ARC-123　批量投递乱码修复（编码不匹配）
- 日期：2026-08-25　类型：问题修复　状态：已修复
- **现象**：批量/全量投递时前端终端出现 � 乱码（`===CASE-BEGIN===` 前后有乱码分隔线）。
- **根源**：run_all.py `_run` 用 `'─'*64`（box-drawing，非 ASCII）+ telemetry_runner.py 里的 `…`/`→`，Windows 下 Python 默认按 GBK 输出，而 server.py `_worker` 用 UTF-8 解码（errors=replace）→ GBK 字节解码失败产生 �。
- **修复**：① server.py `_worker` 的 subprocess.Popen 加 `PYTHONIOENCODING=utf-8` 环境变量（治本，强制 Python 子进程 UTF-8 输出）；② run_all.py 分隔符 `'─'` 改成 `'='`（消除 box-drawing）。
- 验证：server.py / run_all.py 编译通过。

### ARC-124　server.py 改后需重启进程（旧进程不热重载）
- 日期：2026-08-25　类型：坑 / 操作提醒　状态：已记录
- **现象**：改完 server.py（stop 杀进程树 + PYTHONIOENCODING）后，前端仍「停不掉 + 乱码」——排查发现运行中的 server.py 进程（24416）启动时间 21:53:10 早于代码修改时间 21:55:19，进程加载的是旧代码。
- **根因**：Python 不热重载，改 server.py 必须重启进程才生效。
- **防止再犯**：改完 server.py 后主动重启（taskkill 旧进程 + 用 Anaconda python 启动），不再只丢一句「记得重启」。

---

## 五、文档结构（防止乱套）

| 文档 | 职责 | 编号 |
|---|---|---|
| `ARCHIVE.md` | 决策 / 问题 / 坑归档（行为链重构、方法优化、逻辑决策、预留部分、现状记录）| `ARC-XXX` |
| `MAPPING.md` | 映射的「当前真相」（stdout 字段 → 日志字段），唯一真相源，拍板后更新 | — |
| `MAPPING_CHANGELOG.md` | 映射修改记录（每次变更历史，可回档）| `MAP-XXX` |

规则：决策 → ARCHIVE；映射现状 → MAPPING.md（不许有第二份）；映射变更 → 先记 CHANGELOG（MAP 编号）→ 同步 MAPPING.md + `config/mappings/*.json`。

---

## 六、样本源码位置速查

| 模块 | 源码目录（E:\EDR\EDRTelemetry\） | 备注 |
|---|---|---|
| Pipe | `Pipe\PipeLifecycleTest_frozen_protocol_final\` | 已删 disconnect，括号配平 ✅ |
| WMI | `WMI\WmiActivityTest_fixed\` | ⚠️ 用 fixed 版本（frozen 版本仍是旧的 WMI-BINDING-001） |
| Device | `Device\VirtualDiskMountTest_frozen_protocol_final\` | module 已改 Device，括号已修 |
| GPO / BITS / PowerShell | 待你编译（Program.cs 见下载包） | GPO 已改 HKCU |
