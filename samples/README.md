# 测试样本清单（Samples Inventory）

用于验证 EDR（腾讯 iOA）遥测数据采集能力的测试样本。每个模块一个可执行程序，通过命令行 `Action` 触发单一目标行为，遵循「冻结协议 stdout」输出确定性值供字段映射锚定。

> 共 **15 个模块 / 45 个用例**。样本构建标准：.NET Framework 4.7.2，Release x64，提权运行。

## 样本总表

| 模块 | 样本程序 | 用例数 | 覆盖行为 |
|---|---|---|---|
| Account | `AccountLifecycleTest.exe` | 5 | 本地账户创建/修改/删除/登录/注销 |
| BIT | `BitsJobTest.exe` | 1 | BITS 作业 |
| Device | `VirtualDiskMountTest.exe` | 1 | 虚拟磁盘挂载 |
| Driver | `DriverLifecycleTest.exe` | 3 | 驱动加载/修改/卸载 |
| File | `FileLifecycleTest.exe` | 5 | 文件创建/打开/修改/重命名/删除 |
| GPO | `GroupPolicyModifyTest.exe` | 1 | 组策略修改 |
| Hash | `HashBaselineTool.exe` | 3 | MD5/SHA256/IMPHASH 计算 |
| Network | `NetworkActivityTest.exe` | 5 | TCP/UDP/URL/DNS/下载 |
| Pipe | `PipeLifecycleTest.exe` | 2 | 命名管道创建/连接 |
| PowerShell | `PowerShellScriptBlockTest.exe` | 1 | PowerShell 脚本块 |
| Process | `ProcessLifecycleTest.exe` + `ImageLoadTest.exe` | 6 | 进程创建/访问/篡改/远程线程/终止/映像加载 |
| Registry | `RegistryLifecycleTest.exe` | 3 | 注册表键值创建/修改/删除 |
| ScheduleTask | `ScheduledTaskLifecycleTest.exe` | 3 | 计划任务创建/修改/删除 |
| Service | `ServiceLifecycleTest.exe` | 3 | 服务创建/修改/删除 |
| WMI | `WmiActivityTest.exe` | 3 | WMI 事件过滤器/消费者/绑定 |

## 分模块用例明细

### Process（进程）— `ProcessLifecycleTest.exe` / `ImageLoadTest.exe`
| 用例 | 行为 |
|---|---|
| PROC-CREATE-001 | 进程创建 |
| PROC-ACCESS-001 | 进程访问 |
| PROC-TAMPER-001 | 进程内存篡改（VirtualAllocEx + WriteProcessMemory）|
| PROC-REMOTE-THREAD-001 | 远程线程注入 |
| PROC-TERMINATE-001 | 进程终止 |
| PROC-IMAGE-LOAD-001 | 映像加载（ImageLoadTest）|

### Registry（注册表）— `RegistryLifecycleTest.exe`
| 用例 | 行为 |
|---|---|
| REG-CREATE-001 | 键/值创建（Run 键持久化）|
| REG-MODIFY-001 | 键/值修改 |
| REG-DELETE-001 | 键/值删除 |

### File（文件）— `FileLifecycleTest.exe`
| 用例 | 行为 |
|---|---|
| FILE-CREATE-001 | 文件创建 |
| FILE-OPEN-001 | 文件打开 |
| FILE-MODIFY-001 | 文件修改 |
| FILE-RENAME-001 | 文件重命名 |
| FILE-DELETE-001 | 文件删除 |

### Account（账户）— `AccountLifecycleTest.exe`
| 用例 | 行为 |
|---|---|
| ACCOUNT-CREATE-001 | 本地账户创建 |
| ACCOUNT-MODIFY-001 | 本地账户修改 |
| ACCOUNT-DELETE-001 | 本地账户删除 |
| ACCOUNT-LOGIN-001 | 账户登录 |
| ACCOUNT-LOGOFF-001 | 账户注销 |

### Driver（驱动）— `DriverLifecycleTest.exe`
| 用例 | 行为 |
|---|---|
| DRIVER-LOAD-001 | 驱动加载 |
| DRIVER-MODIFY-001 | 驱动修改 |
| DRIVER-UNLOAD-001 | 驱动卸载 |

### Network（网络）— `NetworkActivityTest.exe`
| 用例 | 行为 |
|---|---|
| NET-TCP-001 | TCP 连接 |
| NET-UDP-001 | UDP 连接 |
| NET-URL-001 | URL 访问 |
| NET-DNS-001 | DNS 查询 |
| NET-DOWNLOAD-001 | 文件下载 |

### Hash（哈希）— `HashBaselineTool.exe`
| 用例 | 行为 |
|---|---|
| HASH-MD5-001 | MD5 哈希计算 |
| HASH-SHA-001 | SHA 哈希计算 |
| HASH-IMPHASH-001 | IMPHASH 计算 |

### ScheduleTask / Service / Pipe / WMI / PowerShell / BIT / Device / GPO
| 用例 | 行为 | 样本 |
|---|---|---|
| TASK-CREATE/MODIFY/DELETE-001 | 计划任务创建/修改/删除 | `ScheduledTaskLifecycleTest.exe` |
| SVC-CREATE/MODIFY/DELETE-001 | 服务创建/修改/删除 | `ServiceLifecycleTest.exe` |
| PIPE-CREATE-001 / PIPE-CONNECT-001 | 命名管道创建/连接 | `PipeLifecycleTest.exe` |
| WMI-FILTER-001 / WMI-CONSUMER-001 / WMI-CONSUMER-TO-FILTER-001 | WMI 过滤器/消费者/绑定 | `WmiActivityTest.exe` |
| PS-BLOCK-001 | PowerShell 脚本块 | `PowerShellScriptBlockTest.exe` |
| BIT-JOB-001 | BITS 作业 | `BitsJobTest.exe` |
| DEVICE-VDISK-MOUNT-001 | 虚拟磁盘挂载 | `VirtualDiskMountTest.exe` |
| GPO-MODIFY-001 | 组策略修改 | `GroupPolicyModifyTest.exe` |

## 样本契约（Sample Contract）

每个程序通过命令行 `Action` 暴露单一行为：

```text
RegistryLifecycleTest.exe create
RegistryLifecycleTest.exe modify
RegistryLifecycleTest.exe delete
RegistryLifecycleTest.exe cleanup
```

- `SETUP` 只创建前置条件；仅 `TARGET-BEGIN` ~ `TARGET-END` 之间的行为被评估
- 每次运行输出 RunID、TestCaseID、PID、hostname、UTC 时间戳、目标对象、结果、退出码
- 退出码约定：`0` 成功 / `1` 执行失败 / `2` 用法错误

## 构建

- 工具链：.NET Framework 4.7.2，Release x64
- 每个模块一个 `.csproj` / `.sln`，编译产物 `<Module>Test.exe` 与源码同目录
- `Support/` 存放共享依赖（`TestLibrary.dll`、`nonpnp.sys`）

## 命名规范

- 目录：`samples/<模块>/`（模块名首字母大写，与 `test_cases.json` 的 `module` 字段一致）
- 程序：`<模块>LifecycleTest`（生命周期类）/ `<模块>ActivityTest`（活动类）/ 语义名（工具类如 `HashBaselineTool`）
- 用例：`<模块前缀>-<行为>-<序号>`（如 `REG-CREATE-001`）

## 已知问题

- **WMI / Pipe**：存在 `_legacy_fixed/` 旧版本，其编译产物 MD5 与部署样本不一致，定稿版本以当前主目录为准
- **GPO / BIT / PowerShell**：仅保留源码，编译产物未归档，需重新编译
- 样本行为是否"确实触发"用 Sysmon（L2）独立验证，避免把"样本没触发"误判为"EDR 没采集"
