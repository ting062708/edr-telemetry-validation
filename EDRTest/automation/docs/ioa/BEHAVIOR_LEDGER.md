# 行为台账 & 样本编号（BEHAVIOR_LEDGER）

> 本文档是「IOA 采集能力验证」的全局编号基准。行为编号 = case_id（已实现）+ 预留模块补号，编号一旦分配**不重排、不改名**；
> 重命名/改含义只改本表映射，不动编号。这是 AI 自扩展工程的地基。

## 一、样本编号表（10 已有 + 7 预留）

| 样本ID | 文件名 | 模块 | 覆盖行为 |
|---|---|---|---|
| S-001 | RegistryLifecycleTest.exe | Registry | REG-CREATE/MODIFY/DELETE |
| S-002 | ImageLoadTest.exe | Process | PROC-IMAGE-LOAD |
| S-003 | ProcessLifecycleTest.exe | Process | PROC-CREATE/ACCESS/REMOTE-THREAD/TAMPER/TERMINATE |
| S-004 | FileLifecycleTest.exe | File | FILE-CREATE/OPEN/DELETE/MODIFY/RENAME |
| S-005 | AccountLifecycleTest.exe | Account | ACCOUNT-CREATE/MODIFY/DELETE/LOGIN/LOGOFF |
| S-006 | NetworkActivityTest.exe | Network | NET-TCP/UDP/URL/DNS/DOWNLOAD |
| S-007 | HashBaselineTool.exe | Hash | HASH-MD5/SHA/IMPHASH |
| S-008 | DriverLifecycleTest.exe | Driver | DRIVER-LOAD/MODIFY/UNLOAD |
| S-009 | ScheduledTaskLifecycleTest.exe | ScheduledTask | TASK-CREATE/MODIFY/DELETE |
| S-010 | ServiceLifecycleTest.exe | Service | SVC-CREATE/MODIFY/DELETE |

| 样本ID | 文件名 | 模块 | 覆盖行为（预留，待建）|
|---|---|---|---|
| S-011 | (待建) | Storage | VDISK/USB |
| S-012 | (待建) | GroupPolicy | GPOLICY-MODIFY |
| S-013 | (待建) | Pipe | PIPE-CREATE/CONNECT |
| S-014 | (待建) | Agent | AGENT-START/STOP/INSTALL/UNINSTALL/KEEPALIVE/ERRORS |
| S-015 | (待建) | WMI | WMI-CONSUMER/FILTER/CONSUMER-TO-FILTER |
| S-016 | (待建) | BITS | BIT-JOBS |
| S-017 | (待建) | Script | SCRIPT-BLOCK |

## 二、行为编号表（53 个）

| # | 行为编号 | 英文名(同学baseline) | 中文名 | 模块 | 样本ID | 状态 |
|---|---|---|---|---|---|---|
| 1 | FILE-CREATE-001 | File Creation | 文件创建 | File | S-004 | 已定稿 |
| 2 | FILE-OPEN-001 | File Opened | 文件打开 | File | S-004 | 待重测 |
| 3 | FILE-DELETE-001 | File Deletion | 文件删除 | File | S-004 | 待重测 |
| 4 | FILE-MODIFY-001 | File Modification | 文件修改 | File | S-004 | 已定稿 |
| 5 | FILE-RENAME-001 | File Renaming | 文件重命名 | File | S-004 | 已定稿 |
| 6 | ACCOUNT-CREATE-001 | Local Account Creation | 本地账户创建 | Account | S-005 | 已定稿 |
| 7 | ACCOUNT-MODIFY-001 | Local Account Modification | 本地账户修改 | Account | S-005 | 已定稿 |
| 8 | ACCOUNT-DELETE-001 | Local Account Deletion | 本地账户删除 | Account | S-005 | 已定稿 |
| 9 | ACCOUNT-LOGIN-001 | Account Login | 账户登录 | Account | S-005 | 已定稿 |
| 10 | ACCOUNT-LOGOFF-001 | Account Logoff | 账户注销 | Account | S-005 | 已定稿 |
| 11 | REG-CREATE-001 | Key/Value Creation | 键/值创建 | Registry | S-001 | 已定稿 |
| 12 | REG-MODIFY-001 | Key/Value Modification | 键/值修改 | Registry | S-001 | 待重测 |
| 13 | REG-DELETE-001 | Key/Value Deletion | 键/值删除 | Registry | S-001 | 已定稿 |
| 14 | DRIVER-LOAD-001 | Driver Loaded | 驱动加载 | Driver | S-008 | 已定稿 |
| 15 | DRIVER-MODIFY-001 | Driver Modification | 驱动修改 | Driver | S-008 | 待重测 |
| 16 | DRIVER-UNLOAD-001 | Driver Unloaded | 驱动卸载 | Driver | S-008 | 已定稿 |
| 17 | NET-TCP-001 | TCP Connection | TCP 连接 | Network | S-006 | 已定稿 |
| 18 | NET-UDP-001 | UDP Connection | UDP 连接 | Network | S-006 | 待重测 |
| 19 | NET-URL-001 | URL | URL 访问 | Network | S-006 | 待改判 |
| 20 | NET-DNS-001 | DNS Query | DNS 查询 | Network | S-006 | 已定稿 |
| 21 | NET-DOWNLOAD-001 | File Downloaded | 文件下载 | Network | S-006 | 已定稿 |
| 22 | PROC-IMAGE-LOAD-001 | Image/Library Loaded | 映像加载 | Process | S-002 | 待定稿 |
| 23 | PROC-CREATE-001 | Process Creation | 进程创建 | Process | S-003 | 待定稿 |
| 24 | PROC-ACCESS-001 | Process Access | 进程访问 | Process | S-003 | 待定稿 |
| 25 | PROC-REMOTE-THREAD-001 | Remote Thread Creation | 远程线程注入 | Process | S-003 | 待定稿 |
| 26 | PROC-TAMPER-001 | Process Tampering Activity | 进程内存篡改 | Process | S-003 | 待定稿 |
| 27 | PROC-TERMINATE-001 | Process Termination | 进程终止 | Process | S-003 | 待定稿 |
| 28 | HASH-MD5-001 | MD5 | MD5 哈希 | Hash | S-007 | 待定稿 |
| 29 | HASH-SHA-001 | SHA | SHA 哈希 | Hash | S-007 | 待定稿 |
| 30 | HASH-IMPHASH-001 | IMPHASH | IMPHASH | Hash | S-007 | 待定稿 |
| 31 | TASK-CREATE-001 | Scheduled Task Creation | 计划任务创建 | ScheduledTask | S-009 | 待定稿 |
| 32 | TASK-MODIFY-001 | Scheduled Task Modification | 计划任务修改 | ScheduledTask | S-009 | 待定稿 |
| 33 | TASK-DELETE-001 | Scheduled Task Deletion | 计划任务删除 | ScheduledTask | S-009 | 待定稿 |
| 34 | SVC-CREATE-001 | Service Creation | 服务创建 | Service | S-010 | 待定稿 |
| 35 | SVC-MODIFY-001 | Service Modification | 服务修改 | Service | S-010 | 待定稿 |
| 36 | SVC-DELETE-001 | Service Deletion | 服务删除 | Service | S-010 | 待定稿 |
| 37 | VDISK-MOUNT-001 | Virtual Disk Mount | 虚拟磁盘挂载 | Storage | S-011 | 预留 |
| 38 | USB-MOUNT-001 | USB Device Mount | USB 设备挂载 | Storage | S-011 | 预留 |
| 39 | USB-UNMOUNT-001 | USB Device Unmount | USB 设备卸载 | Storage | S-011 | 预留 |
| 40 | GPOLICY-MODIFY-001 | Group Policy Modification | 组策略修改 | GroupPolicy | S-012 | 预留 |
| 41 | PIPE-CREATE-001 | Pipe Creation | 命名管道创建 | Pipe | S-013 | 预留 |
| 42 | PIPE-CONNECT-001 | Pipe Connection | 命名管道连接 | Pipe | S-013 | 预留 |
| 43 | AGENT-START-001 | Agent Start | Agent 启动 | Agent | S-014 | 预留 |
| 44 | AGENT-STOP-001 | Agent Stop | Agent 停止 | Agent | S-014 | 预留 |
| 45 | AGENT-INSTALL-001 | Agent Install | Agent 安装 | Agent | S-014 | 预留 |
| 46 | AGENT-UNINSTALL-001 | Agent Uninstall | Agent 卸载 | Agent | S-014 | 预留 |
| 47 | AGENT-KEEPALIVE-001 | Agent Keep-Alive | Agent 保活 | Agent | S-014 | 预留 |
| 48 | AGENT-ERRORS-001 | Agent Errors | Agent 错误 | Agent | S-014 | 预留 |
| 49 | WMI-CONSUMER-TO-FILTER-001 | WmiEventConsumerToFilter | WMI 消费者→过滤器 | WMI | S-015 | 预留 |
| 50 | WMI-CONSUMER-001 | WmiEventConsumer | WMI 消费者 | WMI | S-015 | 预留 |
| 51 | WMI-FILTER-001 | WmiEventFilter | WMI 过滤器 | WMI | S-015 | 预留 |
| 52 | BIT-JOBS-001 | BIT JOBS Activity | BITS 任务 | BITS | S-016 | 预留 |
| 53 | SCRIPT-BLOCK-001 | Script-Block Activity | 脚本块活动 | Script | S-017 | 预留 |

## 三、状态说明

- **已定稿**：verdict 已定（见 config/case_result_map.json）
- **待重测/待改判**：与同学 baseline 有差异，见 RETEST_BACKLOG.md
- **待定稿**：有样本、有 case_id，但 verdict 未定（Process/Hash/ScheduledTask/Service）
- **预留**：样本未建，仅有同学 baseline 结论

