# EDR 采集能力验证报告

> 生成时间：2026-08-24 18:45:16
> 覆盖用例：36 / 36（另有预留模块 17 个未接入）

## 概览

| 状态 | 数量 |
|---|---|
| 🟢 采集通过 | 11 |
| 🔴 采集未通过 | 8 |
| 🟡 待匹配 | 0 |
| ⚪ 待测 | 17 |

## 能力矩阵

### Registry

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| REG-CREATE-001 | --case REG-CREATE-001 | 🟢 采集通过 | — | 0/0 |
| REG-MODIFY-001 | --case REG-MODIFY-001 | ⚪ 待测 | — | 0/0 |
| REG-DELETE-001 | --case REG-DELETE-001 | 🔴 采集未通过 | — | 0/0 |

### Process

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| PROC-IMAGE-LOAD-001 | imageload | ⚪ 待测 | — | 0/0 |
| PROC-CREATE-001 | create | ⚪ 待测 | — | 0/0 |
| PROC-ACCESS-001 | access | ⚪ 待测 | — | 0/0 |
| PROC-REMOTE-THREAD-001 | remotethread | ⚪ 待测 | — | 0/0 |
| PROC-TAMPER-001 | tamper | ⚪ 待测 | — | 0/0 |
| PROC-TERMINATE-001 | terminate | ⚪ 待测 | — | 0/0 |

### File

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| FILE-CREATE-001 | --case FILE-CREATE-001 | 🟢 采集通过 | 否 | 1/4 |
| FILE-OPEN-001 | --case FILE-OPEN-001 | 🟢 采集通过 | 否 | 1/4 |
| FILE-DELETE-001 | --case FILE-DELETE-001 | 🟢 采集通过 | 否 | 0/3 |
| FILE-MODIFY-001 | --case FILE-MODIFY-001 | 🟢 采集通过 | 否 | 3/4 |
| FILE-RENAME-001 | --case FILE-RENAME-001 | 🟢 采集通过 | 否 | 0/6 |

### Account

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| ACCOUNT-CREATE-001 | --case ACCOUNT-CREATE-001 | 🔴 采集未通过 | 否 | 0/5 |
| ACCOUNT-MODIFY-001 | --case ACCOUNT-MODIFY-001 | 🔴 采集未通过 | 否 | 0/4 |
| ACCOUNT-DELETE-001 | --case ACCOUNT-DELETE-001 | 🔴 采集未通过 | 否 | 0/2 |
| ACCOUNT-LOGIN-001 | --case ACCOUNT-LOGIN-001 | 🔴 采集未通过 | 否 | 0/3 |
| ACCOUNT-LOGOFF-001 | --case ACCOUNT-LOGOFF-001 | 🔴 采集未通过 | 否 | 0/3 |

### Network

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| NET-TCP-001 | --case NET-TCP-001 | 🟢 采集通过 | — | 0/0 |
| NET-UDP-001 | --case NET-UDP-001 | ⚪ 待测 | — | 0/0 |
| NET-URL-001 | --case NET-URL-001 | 🟢 采集通过 | — | 0/0 |
| NET-DNS-001 | --case NET-DNS-001 | 🔴 采集未通过 | — | 0/0 |
| NET-DOWNLOAD-001 | --case NET-DOWNLOAD-001 | 🟢 采集通过 | — | 0/0 |

### Hash

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| HASH-MD5-001 | --case HASH-MD5-001 --target C:\EDRTest\samples\Hash\Support\TestLibrary.dll | ⚪ 待测 | — | 0/0 |
| HASH-SHA-001 | --case HASH-SHA-001 --target C:\EDRTest\samples\Hash\Support\TestLibrary.dll | ⚪ 待测 | — | 0/0 |
| HASH-IMPHASH-001 | --case HASH-IMPHASH-001 --target C:\EDRTest\samples\Hash\Support\TestLibrary.dll | ⚪ 待测 | — | 0/0 |

### Driver

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| DRIVER-LOAD-001 | --case DRIVER-LOAD-001 | 🟢 采集通过 | — | 0/0 |
| DRIVER-MODIFY-001 | --case DRIVER-MODIFY-001 | 🟢 采集通过 | — | 0/0 |
| DRIVER-UNLOAD-001 | --case DRIVER-UNLOAD-001 | 🔴 采集未通过 | — | 0/0 |

### ScheduledTask

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| TASK-CREATE-001 | --case TASK-CREATE-001 | ⚪ 待测 | — | 0/0 |
| TASK-MODIFY-001 | --case TASK-MODIFY-001 | ⚪ 待测 | — | 0/0 |
| TASK-DELETE-001 | --case TASK-DELETE-001 | ⚪ 待测 | — | 0/0 |

### Service

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| SVC-CREATE-001 | --case SVC-CREATE-001 | ⚪ 待测 | — | 0/0 |
| SVC-MODIFY-001 | --case SVC-MODIFY-001 | ⚪ 待测 | — | 0/0 |
| SVC-DELETE-001 | --case SVC-DELETE-001 | ⚪ 待测 | — | 0/0 |

## 异常采集现象

- **FILE-CREATE-001**（采集通过）：IOA 具备该行为类型的采集能力（日志中存在该行为事件），但样本进程的文件操作未出现在日志中——仅锚定到进程创建，未锚定到文件操作。可能原因：文件监控只采可信进程 / 路径排除 / cmd 包装 / 待验证。
- **FILE-OPEN-001**（采集通过）：IOA 具备该行为类型的采集能力（日志中存在该行为事件），但样本进程的文件操作未出现在日志中——仅锚定到进程创建，未锚定到文件操作。可能原因：文件监控只采可信进程 / 路径排除 / cmd 包装 / 待验证。
- **FILE-DELETE-001**（采集通过）：IOA 具备该行为类型的采集能力（日志中存在该行为事件），但样本进程的文件操作未出现在日志中——仅锚定到进程创建，未锚定到文件操作。可能原因：文件监控只采可信进程 / 路径排除 / cmd 包装 / 待验证。
- **FILE-MODIFY-001**（采集通过）：IOA 具备该行为类型的采集能力（日志中存在该行为事件），但样本进程的文件操作未出现在日志中——仅锚定到进程创建，未锚定到文件操作。可能原因：文件监控只采可信进程 / 路径排除 / cmd 包装 / 待验证。
- **FILE-RENAME-001**（采集通过）：IOA 具备该行为类型的采集能力（日志中存在该行为事件），但样本进程的文件操作未出现在日志中——仅锚定到进程创建，未锚定到文件操作。可能原因：文件监控只采可信进程 / 路径排除 / cmd 包装 / 待验证。

## baseline 对比

- PROC-CREATE-001: IMPLEMENTED → 待测
- PROC-ACCESS-001: IMPLEMENTED → 待测
- PROC-REMOTE-THREAD-001: IMPLEMENTED → 待测
- PROC-TAMPER-001: IMPLEMENTED → 待测
- PROC-TERMINATE-001: NOT_IMPLEMENTED → 待测
- FILE-CREATE-001: NOT_IMPLEMENTED → 采集通过
- FILE-OPEN-001: NOT_IMPLEMENTED → 采集通过
- FILE-DELETE-001: NOT_IMPLEMENTED → 采集通过
- FILE-MODIFY-001: NOT_IMPLEMENTED → 采集通过
- FILE-RENAME-001: NOT_IMPLEMENTED → 采集通过
- ACCOUNT-CREATE-001: NOT_IMPLEMENTED → 采集未通过
- ACCOUNT-MODIFY-001: NOT_IMPLEMENTED → 采集未通过
- ACCOUNT-DELETE-001: NOT_IMPLEMENTED → 采集未通过
- ACCOUNT-LOGIN-001: IMPLEMENTED → 采集未通过
- ACCOUNT-LOGOFF-001: IMPLEMENTED → 采集未通过
- DRIVER-LOAD-001: IMPLEMENTED → 采集通过
- DRIVER-MODIFY-001: IMPLEMENTED → 采集通过
- DRIVER-UNLOAD-001: NOT_IMPLEMENTED → 采集未通过
