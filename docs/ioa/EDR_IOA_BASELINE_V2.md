# IOA 采集能力 Baseline V2（基于全量日志重判）

> 数据源：`E:\EDR\EDRTest\log\logs_export_1787765540356922676_27329565-63c0-4895-bea7-11fd74c589dc.zip`（08-26 导出）
> 生成：2026-08-27（AI 基于 stdout + 日志逐字段比对重写）
> 定位：推翻 v4.0.0 中「暂按 baseline=有/无」「待确认」的占位结论，改为**日志实证**口径。

---

## 0. 最重要的一条（先读）

**目标日志不是全量导出，而是一段时间切片**，只覆盖约 **16:04–17:31 UTC（08-26）**：

| 导出文件 | 导出时刻(UTC) | 覆盖样本批次 |
|---|---|---|
| `logs_export_1787753795721497177` | ~14:56 | 更早批次（含 Registry 值 `EDRTelemetryRunTest`）|
| `logs_export_1787761952278191504` | ~16:32 | File/Account/Registry 早期批次 |
| `logs_export_1787763133596614815` | ~16:52 | Hash/Driver/Task/Service 批次 |
| `logs_export_1787765540356922676` ← 目标 | ~17:32 | **WMI/GPO/BIT/PS/Process/Network（16:04 之后）** |

- Registry/File/Account/Hash/Driver/Task/Service/Pipe 样本在 **15:06–16:01** 运行，落在**早期导出**里，**不在目标日志时间窗内**。
- 因此目标日志里「找不到」它们的样本值 ≠ 「IOA 不采」，而是「时间窗没覆盖」。
- **要得到完整 baseline，需合并 4 个导出，或重新导出一份覆盖 15:00–17:00 全窗口的日志。**

---

## 1. IOA 事件类型词汇表（operation 权威清单）

这是 match 规则 `operation` 字段的**唯一正确取值来源**。目标日志实测计数：

| 行为 | 真实 Action.Name | 计数 | 备注 |
|---|---|---|---|
| 进程创建 | `ProcessCreate` | 3507 | ProcEvents |
| 文件删除 | `FileDelete` | 4291 | FileEvents |
| 文件写入/关闭 | `FileWriteClose` | 899 | 创建/修改共用，无独立 FileCreate |
| 登录成功 | `LoginSuccess` | 999 | LoginEvents |
| HTTPS 请求 | `HttpsRequest` | 126 | NetworkEvents |
| 文件重命名 | `FileRename` | 134 | **不是 MoveFileExW** |
| 服务启动 | `StartService` | 54 | ServiceEvents |
| HTTP 请求 | `HttpRequest` | 44 | NetworkEvents |
| Socket 请求 | `SocketRequest` | 38 | NetworkEvents |
| 本地组枚举 | `UserLocalGroupEnum` | 34 | AccountEvents |
| 注册表写值 | `RegSetValue` | 25 | RegEvents（仅覆盖写）|
| 计划任务创建 | `RpcSchedTaskCreate` | 23 | ServiceEvents，**不是 SchedTaskCreate** |
| 文件读 | `FileRead` | 22 | 仅系统 .cab |
| 映像加载 | `LoadDll` | 16 | 仅进程启动期 DLL，非运行时 LoadLibrary |
| 远程线程 | `RemoteThread` | 11 | Proc 类 |
| 驱动加载 | `LoadDriver` | 11 | ModuleEvents，内核态 |
| 脚本扫描 | `ScriptScan` | 8 | ScriptEvents |
| 命名管道 | `NamedPipe` | 6 | FileEvents |
| 打开进程 | `NtOpenProcess` | 5 | RemoteInjectEvents |
| 虚拟内存分配 | `VirtualAllocEx` | 3 | RemoteInjectEvents |
| 网络绑定 | `NetBind` | 2 | NetworkEvents |
| 写虚拟内存 | `NtWriteVirtualMemory` | 2 | RemoteInjectEvents，**不是 WriteProcessMemory** |
| 写进程内存 | `WriteProcessMemory` | 1 | RemoteInjectEvents |
| 加密上下文 | `CryptAcquireContextW` | 1 | hook（哈希误判源，见 §4）|
| 打开 URL | `InternetOpenUrlW` | 1 | InternetEvents |

**确认不存在（0 条）的事件类型 → IOA 无该采集能力：**

| 行为 | 期望的 Action.Name（均 0 条）| 结论 |
|---|---|---|
| 进程终止 | `ProcessTerminate` | 无 |
| 注册表删除 | `RegDeleteValue` / `RegDeleteKey` / `RegCreateKey` | 无 |
| 账户创建 | `AccountCreate` | 无（仅 UserLocalGroupEnum）|
| 账户改密 | `AccountPwdChange` | 无 |
| 账户删除 | `AccountDelete` | 无 |
| 账户注销 | `AccountLogoff` | 无 |
| 驱动卸载 | `UnloadDriver` | 无 |
| DNS 查询 | `NetDnsQuery` | 无 |
| 计划任务修改/删除 | `SchedTaskUpdate` / `SchedTaskDelete` | 无（仅 RpcSchedTaskCreate）|
| 服务创建/修改/删除 | `CreateService` / `ModifyService` / `DeleteService` | 无（仅 StartService）|
| WMI 事件 | `WmiCreate` | 无（仅经 ScriptScan 可见）|
| 虚拟磁盘挂载 | `VirtualDiskMount` | 无 |
| BITS 作业 | `BitsJobCreate` | 无（仅经 bitsadmin cmdline 可见）|

---

## 2. 字段映射修正（stdout 值 → 日志 dot-path）

| 模块 | 样本值 | 实际落点 | 修正说明 |
|---|---|---|---|
| 网络 URL | `baidu.com` | `Child.Host` **和** `Child.Url` 都有 | v4 说「Url 恒空」**是错的**，本日志 `Child.Url="https://www.baidu.com"` |
| 网络 TCP/下载 | `proof.ovh.net` | `Child.Host` + `Child.DstPort` + `Child.Protocol` | — |
| 文件重命名 | 源/目标名 | `Child.OldFilePath`（源）+ `Child.FilePath`（目标）| 用 OldFilePath，禁用截断的 NodeName |
| 文件 MD5 | 样本算的 MD5 | `Child.FileMd5`（+`Child.FileMd5Type":"全文"`）| **哈希能力判定的正确依据** |
| 注册表 | 值名/值数据 | `Child.RegValName` / `Child.RegValData` / `Child.RegKeyPath` / `Child.RegOldValData` | 路径是全 hive 路径 `HKEY_...` |
| 进程 | 目标进程 | `Child.FileName` / `Child.FilePath`（ProcEvents 用 Child 当 actor）| normalizer 已修 |
| PowerShell | 脚本内容 | `Parent.ProcCmdline`（powershell.exe 命令行）| 靠内容值锚定，非进程 |
| 账户/登录 | 用户名 | `Child.TargetUserName`（LoginEvents）| 仅登录类 |
| 驱动 | 驱动路径 | `Child.FilePath` | 无 ServiceName/DriverName 字段 |

---

## 3. Baseline 判定表（三态：对 / 疑问 / 错）

> 覆盖标记：`✅窗内` = 目标日志时间窗内可判；`⚠️窗外` = 样本在早期导出，需补日志才能定论。

### 3.1 目标日志窗内（16:04 之后，可定论）

| Case | 判定 | 证据 |
|---|---|---|
| PROC-CREATE-001 | **对** | `ProcessTarget.exe` 命中 ProcessCreate（Child.FileName/FilePath/ProcCmdline 齐全）|
| PROC-IMAGE-LOAD-001 | **错** | LoadDll×16 无 `TestLibrary.dll`（运行时 LoadLibrary 不采，仅采启动期 DLL）|
| PROC-ACCESS-001 | **疑问** | NtOpenProcess×5 存在但非样本进程（rundll32/注入 hook）|
| PROC-REMOTE-THREAD-001 | **疑问** | RemoteThread×11 存在，归属待查 |
| PROC-TAMPER-001 | **疑问** | NtWriteVirtualMemory×2/VirtualAllocEx×3 存在，来自 BIT/PS 样本注入 |
| PROC-TERMINATE-001 | **错** | ProcessTerminate×0 |
| NET-TCP-001 | **待重测** | 样本 FAIL（连接 93.184.216.34:80 被拒），非能力问题 |
| NET-UDP-001 | **错** | 单播 8.8.8.8:53 未采（SocketRequest 仅系统广播/组播）|
| NET-URL-001 | **对** | baidu.com 命中 HttpsRequest，`Child.Url` 非空 |
| NET-DNS-001 | **错** | NetDnsQuery×0，example.com 全日志无 |
| NET-DOWNLOAD-001 | **对** | proof.ovh.net 命中 HttpsRequest |
| PS-BLOCK-001 | **对** | `EDRTelemetryScriptBlock_c462f682` 命中 powershell 命令行 |
| WMI-FILTER-001 | **疑问** | 无 WmiCreate；经 ScriptScan 可见 `EDRTelemetryWmiFilter` |
| WMI-CONSUMER-001 | **疑问** | 同上 |
| WMI-CONSUMER-TO-FILTER-001 | **疑问** | 同上 |
| GPO-MODIFY-001 | **错** | `EDRTelemetryGpoTest` 未采（RegSetValue 仅 Uninstall 系统键）|
| BIT-JOB-001 | **疑问** | 无 BitsJobCreate；bitsadmin cmdline 可见但 CreateResult=FAIL |
| DEVICE-VDISK-MOUNT-001 | **待重测** | 样本未执行（stdout=Usage，投递参数错）|

### 3.2 目标日志窗外（15:06–16:01，需合并早期导出）

| Case | 判定（暂）| 说明 |
|---|---|---|
| REG-CREATE-001 | 错（待复核）| 值 `EDRTelemetryRunTest` 在早期导出中；创建(ABSENT→value)不采为既有结论 |
| REG-MODIFY-001 | 对（待复核）| 覆盖写 notepad→calc 在早期导出有铁证 |
| REG-DELETE-001 | 错 | 无 RegDeleteValue（能力缺失，全日志无）|
| FILE-CREATE/OPEN/DELETE/MODIFY/RENAME | 待复核 | 样本写 `C:\EDRTest\samples` 盲区 vs 早期导出 |
| ACCOUNT-CREATE/MODIFY/DELETE/LOGIN/LOGOFF | 待复核 | `EDR_Test_User` 全目录无；账户走 WinEventLog 通道 |
| HASH-MD5-001 | **对** | 重定义：以 `Child.FileMd5` 字段存在判定（非 CryptAcquireContextW）|
| HASH-SHA-001 | 错 | 样本 SHA256 `6e41b23f...` 全日志无 |
| HASH-IMPHASH-001 | 错 | 样本 IMPHASH `bc467363...` 全日志无 |
| DRIVER-LOAD/MODIFY/UNLOAD | 待复核 | `nonpnp.sys` 全目录无；LoadDriver 仅系统驱动 |
| TASK-CREATE/MODIFY/DELETE | 待复核 | 任务名在早期导出；`SchedTaskUpdate/Delete`×0 |
| SVC-CREATE/MODIFY/DELETE | 错（待复核）| `EDR_Telemetry_Test_Service` 全目录无；仅 StartService |
| PIPE-CREATE/CONNECT | 待复核 | 样本 08-25/08-26 运行，管道名未命中目标日志 |

---

## 4. Match 规则修正清单（重新写 test_cases.json / capability_rules_v2.json）

1. **PROC-TAMPER-001** `operation`: `["VirtualAllocEx","WriteProcessMemory"]` → **`["NtWriteVirtualMemory","VirtualAllocEx","WriteProcessMemory"]`**（真实事件是 NtWriteVirtualMemory）。
2. **TASK-CREATE-001** `operation`（当前为空）→ **`RpcSchedTaskCreate`**；TASK-MODIFY/DELETE 维持 0 条判定但 operation 从 `SchedTaskUpdate/Delete` 改为留空+注记「IOA 无此事件」。
3. **HASH 三个 case**：删除 `operation: "CryptAcquireContextW"` 口径；改 `field` 类能力：`capability_probe.field = "Child.FileMd5"`（MD5 有 / SHA、IMPHASH 无）。
4. **FILE-RENAME-001**：operation `FileRename` 正确，但 expected_fields 加 `Child.OldFilePath` 做源文件锚定。
5. **FILE-CREATE/MODIFY**：capability_probe 从 `FileCreateOpName=新建/覆盖写` 改为 `Child.FileTotalWrite=0`（创建）区分度更高。
6. **NET-URL-001**：expected_fields 移除「Url 恒空」假设；`Child.Host` 与 `Child.Url` 都验。
7. **NET-UDP-001**：operation 从 `NetBind` → `SocketRequest`；并注记「单播不采」。
8. **NET-DNS-001**：operation 从 `NetDnsQuery`（0 条）→ 维持，注记「无此事件类型」。
9. **DRIVER-LOAD-001**：`Child.FilePath` 锚定（无 ServiceName 字段）；`kernel_mode: true` 保留。
10. **SVC 三个 case**：operation `CreateService/ModifyService/DeleteService` → 留空+注记「仅 StartService，无创建/修改/删除」。
11. **WMI 三个 case**：operation `WmiCreate` → 留空+注记「无 WmiCreate，经 ScriptScan 可见」。
12. **PS-BLOCK-001**：operation `ScriptScan` 正确，但值锚定走 `Parent.ProcCmdline`（actor=powershell.exe），非 sample 进程。
13. **DEVICE-VDISK-MOUNT-001**：样本未执行，需修 `--case` 投递参数后重测。

---

## 5. 建议下一步

1. **重新导出一份全窗口日志**（覆盖 15:00–17:00 UTC 08-26），或把 4 个增量导出合并进 `log/`，一次性定稿 §3.2 的「待复核」项。
2. 定稿后跑 `python run_all.py match`（或前端点「匹配」）验证 verdict 与上表一致。
3. 用 `run_all.py baseline` 重打 `config/baseline.json`，再用 `matrix --diff` 做回归对比。
4. 修复 DEVICE-VDISK 样本投递参数、重跑 NET-TCP（样本连接被拒需换可达目标或加容错）。
