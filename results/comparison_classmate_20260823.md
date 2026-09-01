# 对比报告：我的 case_result_map vs 同学 baseline

> 生成时间 2026-08-23 · 我 21 case / 同学 53 行为

## 一、总览

- 重叠 case：21
- ✅ 一致：14
- ⚠️ 冲突：4
- ❓ 同学不确定：3
- 我未覆盖（同学已测）：32

## 二、冲突（4 个）

### FILE-OPEN-001（File Opened）

- 我：**通过(部分)?**
- 同学：**✅**
- 同学字段：FileWriteClose，子事件打开文件。
- 同学备注：JSON文件可检测，TXT无法检测

### REG-MODIFY-001（Key/Value Modification）

- 我：**通过(部分)?**
- 同学：**✅**
- 同学字段：RegSetValue，同时比对Child.RegOldValData与Child.RegValData对注册表路径有筛选，
- 同学备注：新建的测试路径不检测，从启动项路径创建成功检测

### NET-UDP-001（UDP Connection）

- 我：**通过(部分)?**
- 同学：**✅**
- 同学字段：网络监听，NetBind，Child.Protocol为udp，
- 同学备注：但是感觉只是刚好碰巧撞上了测试集，换种可能就不行了

### DRIVER-MODIFY-001（Driver Modification）

- 我：**通过**
- 同学：**❌**
- 同学字段：无字段
- 同学备注：(空)

## 三、同学不确定（3 个，需复测）

### FILE-DELETE-001（File Deletion）

- 我：**通过**
- 同学：**❓**（TXT和JSON删除都没检测出来，可能是调用方式或者文件类型或者文件大小问题）

### NET-URL-001（URL）

- 我：**通过**
- 同学：**❓**（但是edr没记录url。）

### NET-DNS-001（DNS Query）

- 我：**未通过**
- 同学：**❓**（但是edr没记录目标端口）

## 四、我未覆盖、同学已测（32 个）

| 行为 | 同学结论 | 字段/事件 |
|---|---|---|
| Process Creation | ✅ | ProcessCreate |
| Process Termination | ❌ | 有字段，可以读取到进程通信的NtOpenProcess动作。其他终端没有任何事件。 |
| Process Access | ✅ | NtOpenProcess |
| Image/Library Loaded | ✅ | 有字段，也有其他终端的事件，但是换了四种测试方法就是没测出来 |
| Remote Thread Creation | ✅ | RemoteThread |
| Process Tampering Activity | ✅ | WriteProcessMemory，其他几种方法没试 |
| MD5 | ✅ | 以创建文件为基础，Child.FileMd5 |
| SHA | ❌ | 无字段，以创建文件为基础 |
| IMPHASH | ❌ | 无字段，以创建文件为基础 |
| Scheduled Task Creation | ✅ | SchedTaskCreate， |
| Scheduled Task Modification | ✅ | SchedTaskUpdate， |
| Scheduled Task Deletion | ❌ | 有字段，没有其他终端事件，疑似无实现 |
| Service Creation | ✅ | CreateService |
| Service Modification | ❌ | 有字段，没有其他终端事件，疑似无实现 |
| Service Deletion | ❌ | 有字段，没有其他终端事件，疑似无实现 |
| Virtual Disk Mount | ❌ | 无字段 |
| USB Device Unmount | ❌ | 无字段 |
| USB Device Mount | ❌ | 无字段 |
| Group Policy Modification | ✅ | RegSetValue， Child.RegGroupName为组策略，对注册表路径有筛选， |
| Pipe Creation | ✅ | NamedPipe， Child.PipeOpName为创建管道 |
| Pipe Connection | ✅ | NamedPipe， Child.PipeOpName为打开管道 |
| Agent Start | ❓ | 还没测 |
| Agent Stop | ❓ | 还没测 |
| Agent Install | ❓ | 还没测 |
| Agent Uninstall | ❓ | 还没测 |
| Agent Keep-Alive | ❓ | 还没测 |
| Agent Errors | ❓ | 还没测 |
| WmiEventConsumerToFilter | ❌ | WmiOperation，但是跟能力无关，读的都是11事件 |
| WmiEventConsumer | ❌ | WmiOperation，但是跟能力无关，读的都是11事件 |
| WmiEventFilter | ❌ | WmiOperation，但是跟能力无关，读的都是11事件 |
| BIT JOBS Activity | ❌ | 无字段 |
| Script-Block Activity | ✅ | ScriptScan，并进一步通过命令内容判断 |
