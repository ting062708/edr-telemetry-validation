# EDR-Telemetry 行业基准（对齐标准）

> 数据来源：https://github.com/tsale/EDR-Telemetry （`EDR_telem_windows.json`）
> 用途：本项目 verdict 判定口径的唯一外部权威依据。
> 取值含义：`Yes`=采集 / `No`=不采 / `Partially`=部分采集 / `Via EventLogs`=靠 Windows 安全事件日志采集 / `Via EnablingTelemetry`=需额外开启遥测。
> IOA 列 = 本项目实测（二态定稿，采集到即 Yes，未采集到即 No）。

## 本框架覆盖模块 ↔ 行业 Sub-Category 对照（含 IOA 实测）

| 本项目模块 | 行业 Category | Sub-Category | Sysmon | MDE | SentinelOne | CrowdStrike | IOA |
|---|---|---|---|---|---|---|---|
| Driver-LOAD | Driver/Module | Driver Loaded | Yes | Yes | Yes | Yes | **Yes** |
| Driver-MODIFY | Driver/Module | Driver Modification | No | No | No | Yes | **Yes** |
| Driver-UNLOAD | Driver/Module | Driver Unloaded | No | No | Partially | No | **No** |
| File-CREATE | File Manipulation | File Creation | Yes | Yes | Yes | Yes | **Yes** |
| File-OPEN | File Manipulation | File Opened | No | No | No | Partially | **Yes** |
| File-DELETE | File Manipulation | File Deletion | Yes | Yes | Yes | Yes | **Yes** |
| File-MODIFY | File Manipulation | File Modification | No | Yes | Yes | Yes | **Yes** |
| File-RENAME | File Manipulation | File Renaming | No | Yes | Yes | Yes | **Yes** |
| Account-CREATE | User Account | Local Account Creation | No | Yes | Yes | Yes | **No** |
| Account-MODIFY | User Account | Local Account Modification | No | Yes | Via EventLogs | Partially | **No** |
| Account-DELETE | User Account | Local Account Deletion | No | Yes | Via EventLogs | Yes | **No** |
| Account-LOGIN | User Account | Account Login | No | Yes | Yes | Yes | **Yes** |
| Account-LOGOFF | User Account | Account Logoff | No | No | Yes | Yes | **No** |
| Registry-CREATE | Registry | Key/Value Creation | Yes | Yes | Yes | Partially | **Yes** |
| Registry-MODIFY | Registry | Key/Value Modification | Yes | Yes | Yes | Partially | **Yes** |
| Registry-DELETE | Registry | Key/Value Deletion | Yes | Yes | Yes | No | **No** |
| Service-CREATE | Service | Service Creation | No | Yes | Yes | Yes | **No** |
| Service-MODIFY | Service | Service Modification | No | No | Via EnablingTelemetry | Partially | **No** |
| Service-DELETE | Service | Service Deletion | No | No | No | No | **No** |
| Task-CREATE | Schedule Task | Scheduled Task Creation | No | Yes | Yes | Yes | **Yes** |
| Task-MODIFY | Schedule Task | Scheduled Task Modification | No | Yes | Yes | Yes | **No** |
| Task-DELETE | Schedule Task | Scheduled Task Deletion | No | Yes | Yes | Yes | **No** |
| Process-CREATE | Process | Process Creation | Yes | Yes | Yes | Yes | **Yes** |
| Process-TERMINATE | Process | Process Termination | Yes | No | No | Yes | **No** |
| Process-IMAGE-LOAD | Process | Image/Library Loaded | Yes | Yes | Yes | Yes | **Yes** |
| Process-ACCESS | Process | Process Access | Yes | Yes | Yes | Yes | **Yes** |
| Process-REMOTE-THREAD | Process | Remote Thread Creation | Yes | Yes | Yes | Yes | **Yes** |
| Process-TAMPER | Process | Process Tampering Activity | Yes | Yes | Yes | Yes | **Yes** |
| Network-TCP | Network | TCP Connection | Yes | Yes | Yes | Yes | **Yes** |
| Network-UDP | Network | UDP Connection | Yes | No | No | Yes | **Yes** |
| Network-URL | Network | URL | No | Yes | Via EnablingTelemetry | No | **Yes** |
| Network-DNS | Network | DNS Query | Yes | Yes | Yes | Yes | **No** |
| Network-DOWNLOAD | Network | File Downloaded | No | Yes | Yes | Yes | **Yes** |
| Hash-MD5 | Hash Algorithms | MD5 | Yes | Yes | Yes | Yes | **Yes** |
| Hash-SHA | Hash Algorithms | SHA | Yes | Yes | Yes | Yes | **No** |
| Hash-IMPHASH | Hash Algorithms | IMPHASH | Yes | No | No | No | **No** |

## 关键结论（known_gap 判定依据）

1. **Account 类：Sysmon 全 No，靠 EventLogs 采集**（安全事件 4720/4726/4738/4624/4634）。IOA 仅登录(LoginSuccess)采到，其余增删改注销全 No。
2. **Account Logoff：MDE 也是 No** → 公认难采项。
3. **File Opened：Sysmon=No/MDE=No/SentinelOne=No** → 读操作公认难采；IOA 仅采系统 .cab 归档。
4. **Service Deletion：几乎所有厂商都是 No** → 服务删除公认不采；IOA 服务增删改全 No（仅 StartService）。
5. **Process Termination：MDE=No/SentinelOne=No** → 进程退出并非所有 EDR 都采；IOA 无此事件。
6. **IMPHASH：MDE=No/SentinelOne=No/CrowdStrike=No** → IMPHASH 很多 EDR 不采；IOA 无此字段。
7. **URL：Sysmon=No** → URL 采集非标配；IOA 采到(HttpsRequest+Child.Url)。
8. **DNS：Sysmon/MDE/CS/S1 全 Yes** → 行业全采，IOA 无 NetDnsQuery，属**能力缺口**。

## 判定口径

- 矩阵行为在行业基准中 **Yes 居多** 而本环境未采到 → 记为能力缺口（known_gap），标注"行业可采但本环境缺"（如 DNS、Service Creation、Task Modify）。
- 矩阵行为在行业基准中 **No 居多**（如 File Opened、Account Logoff、Service Deletion）→ 记为行业常态缺口（known_gap），标注"行业公认难采"。
- 采到但表达方式不同（如 File Creation 用 FileWriteClose+FileTotalWrite=0、Hash 用 Child.FileMd5 字段）→ 记 Yes，注明映射方式。
- **IOA 二态定稿统计：本表 36 个行业对齐行为中 Yes 21 / No 15；全量 53 项中 Yes 26 / No 27。**
