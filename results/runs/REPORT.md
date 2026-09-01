# EDR 采集能力验证报告

> 生成时间：2026-09-02 03:36:08
> 覆盖用例：54 / 36（另有预留模块 17 个未接入）

## 概览

| 状态 | 数量 |
|---|---|
| 🟢 采集通过 | 27 |
| 🔴 采集未通过 | 18 |
| ⚪ 待判定 | 9 |

## 能力矩阵

### Registry

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| REG-CREATE-001 | --case REG-CREATE-001 | 🟢 采集通过 | — | 1/3 |
| REG-MODIFY-001 | --case REG-MODIFY-001 | 🟢 采集通过 | — | 1/4 |
| REG-DELETE-001 | --case REG-DELETE-001 | 🔴 采集未通过 | — | 0/4 |
| REG-CREATE-002 | --case REG-CREATE-002 | ⚪ 待判定 | — | 0/0 |

### Process

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| PROC-IMAGE-LOAD-001 | imageload | 🟢 采集通过 | 否 | 1/7 |
| PROC-CREATE-001 | create | 🟢 采集通过 | 是 | 3/0 |
| PROC-ACCESS-001 | access | 🟢 采集通过 | 是 | 1/3 |
| PROC-REMOTE-THREAD-001 | remotethread | 🟢 采集通过 | 否 | 2/2 |
| PROC-TAMPER-001 | tamper | 🟢 采集通过 | 是 | 2/3 |
| PROC-TERMINATE-001 | terminate | 🔴 采集未通过 | 否 | 1/2 |
| PROC-IMAGE-LOAD-002 | --case PROC-IMAGE-LOAD-002 | ⚪ 待判定 | — | 0/0 |
| PROC-TAMPER-002 | --case PROC-TAMPER-002 | ⚪ 待判定 | — | 0/0 |

### File

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| FILE-CREATE-001 | --case FILE-CREATE-001 | 🟢 采集通过 | — | 1/4 |
| FILE-OPEN-001 | --case FILE-OPEN-001 | 🟢 采集通过 | — | 1/4 |
| FILE-DELETE-001 | --case FILE-DELETE-001 | 🟢 采集通过 | — | 0/3 |
| FILE-MODIFY-001 | --case FILE-MODIFY-001 | 🟢 采集通过 | — | 3/4 |
| FILE-RENAME-001 | --case FILE-RENAME-001 | 🟢 采集通过 | — | 0/6 |
| FILE-CREATE-002 | --case FILE-CREATE-002 | ⚪ 待判定 | — | 0/0 |
| FILE-CREATE-003 | --case FILE-CREATE-003 | ⚪ 待判定 | — | 0/0 |

### Account

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| ACCOUNT-CREATE-001 | --case ACCOUNT-CREATE-001 | 🔴 采集未通过 | — | 0/5 |
| ACCOUNT-MODIFY-001 | --case ACCOUNT-MODIFY-001 | 🔴 采集未通过 | — | 0/4 |
| ACCOUNT-DELETE-001 | --case ACCOUNT-DELETE-001 | 🔴 采集未通过 | — | 0/2 |
| ACCOUNT-LOGIN-001 | --case ACCOUNT-LOGIN-001 | 🟢 采集通过 | — | 1/2 |
| ACCOUNT-LOGOFF-001 | --case ACCOUNT-LOGOFF-001 | 🔴 采集未通过 | — | 0/3 |
| ACCOUNT-CREATE-002 | --case ACCOUNT-CREATE-002 | ⚪ 待判定 | — | 0/0 |

### Network

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| NET-TCP-001 | --case NET-TCP-001 | 🟢 采集通过 | — | 0/0 |
| NET-UDP-001 | --case NET-UDP-001 | 🟢 采集通过 | 否 | 3/6 |
| NET-URL-001 | --case NET-URL-001 | 🟢 采集通过 | 是 | 2/1 |
| NET-DNS-001 | --case NET-DNS-001 | 🔴 采集未通过 | 否 | 0/2 |
| NET-DOWNLOAD-001 | --case NET-DOWNLOAD-001 | 🟢 采集通过 | 是 | 5/2 |

### Hash

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| HASH-MD5-001 | --case HASH-MD5-001 --target C:\EDRTest\samples\Hash\Support\TestLibrary.dll | 🟢 采集通过 | — | 1/2 |
| HASH-SHA-001 | --case HASH-SHA-001 --target C:\EDRTest\samples\Hash\Support\TestLibrary.dll | 🟢 采集通过 | — | 0/4 |
| HASH-IMPHASH-001 | --case HASH-IMPHASH-001 --target C:\EDRTest\samples\Hash\Support\TestLibrary.dll | 🟢 采集通过 | — | 1/3 |

### Driver

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| DRIVER-LOAD-001 | --case DRIVER-LOAD-001 | 🟢 采集通过 | — | 0/3 |
| DRIVER-MODIFY-001 | --case DRIVER-MODIFY-001 | 🟢 采集通过 | — | 0/5 |
| DRIVER-UNLOAD-001 | --case DRIVER-UNLOAD-001 | 🔴 采集未通过 | — | 0/3 |

### ScheduleTask

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| TASK-CREATE-001 | --case TASK-CREATE-001 | 🟢 采集通过 | — | 3/4 |
| TASK-MODIFY-001 | --case TASK-MODIFY-001 | 🔴 采集未通过 | — | 3/4 |
| TASK-DELETE-001 | --case TASK-DELETE-001 | 🔴 采集未通过 | — | 3/5 |
| TASK-CREATE-002 | --case TASK-CREATE-002 | ⚪ 待判定 | — | 0/0 |
| TASK-MODIFY-002 | --case TASK-MODIFY-002 | ⚪ 待判定 | — | 0/0 |

### Service

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| SVC-CREATE-001 | --case SVC-CREATE-001 | 🔴 采集未通过 | — | 0/4 |
| SVC-MODIFY-001 | --case SVC-MODIFY-001 | 🔴 采集未通过 | — | 0/5 |
| SVC-DELETE-001 | --case SVC-DELETE-001 | 🔴 采集未通过 | — | 1/2 |
| SVC-CREATE-002 | --case SVC-CREATE-002 | ⚪ 待判定 | — | 0/0 |

### Pipe

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| PIPE-CREATE-001 | --case PIPE-CREATE-001 | 🟢 采集通过 | — | 0/3 |
| PIPE-CONNECT-001 | --case PIPE-CONNECT-001 | 🟢 采集通过 | 否 | 0/3 |

### WMI

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| WMI-FILTER-001 | --case WMI-FILTER-001 | 🔴 采集未通过 | 否 | 2/2 |
| WMI-CONSUMER-001 | --case WMI-CONSUMER-001 | 🔴 采集未通过 | 否 | 2/2 |
| WMI-CONSUMER-TO-FILTER-001 | --case WMI-CONSUMER-TO-FILTER-001 | 🔴 采集未通过 | 否 | 2/2 |

### Device

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| DEVICE-VDISK-MOUNT-001 | --case DEVICE-VDISK-MOUNT-001 | 🔴 采集未通过 | — | 0/0 |

### GPO

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| GPO-MODIFY-001 |  | 🟢 采集通过 | 否 | 1/2 |

### BIT

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| BIT-JOB-001 |  | 🔴 采集未通过 | 否 | 2/2 |

### PowerShell

| 用例 | 行为 | 能力判定 | 锚定样本 | 值扫描命中/缺失 |
|---|---|---|---|---|
| PS-BLOCK-001 |  | 🟢 采集通过 | 否 | 2/1 |

## 异常采集现象

（暂无）

## baseline 对比

- PROC-CREATE-001: IMPLEMENTED → 采集通过
- PROC-ACCESS-001: IMPLEMENTED → 采集通过
- PROC-REMOTE-THREAD-001: IMPLEMENTED → 采集通过
- PROC-TAMPER-001: IMPLEMENTED → 采集通过
- PROC-TERMINATE-001: NOT_IMPLEMENTED → 采集未通过
- FILE-CREATE-001: NOT_IMPLEMENTED → 采集通过
- FILE-OPEN-001: NOT_IMPLEMENTED → 采集通过
- FILE-DELETE-001: NOT_IMPLEMENTED → 采集通过
- FILE-MODIFY-001: NOT_IMPLEMENTED → 采集通过
- FILE-RENAME-001: NOT_IMPLEMENTED → 采集通过
- ACCOUNT-CREATE-001: NOT_IMPLEMENTED → 采集未通过
- ACCOUNT-MODIFY-001: NOT_IMPLEMENTED → 采集未通过
- ACCOUNT-DELETE-001: NOT_IMPLEMENTED → 采集未通过
- ACCOUNT-LOGIN-001: IMPLEMENTED → 采集通过
- ACCOUNT-LOGOFF-001: IMPLEMENTED → 采集未通过
- DRIVER-LOAD-001: IMPLEMENTED → 采集通过
- DRIVER-MODIFY-001: IMPLEMENTED → 采集通过
- DRIVER-UNLOAD-001: NOT_IMPLEMENTED → 采集未通过
