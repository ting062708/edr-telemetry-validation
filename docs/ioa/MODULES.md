# IOA 各模块采集结论（MODULES）

> 本文件汇总各模块的 **IOA 采集结论与关键认知**，属于**底层实例层**（IOA 专属）。
> 上层通用方法论见 `../AI_ENGINE.md`、`../E2E_VALIDATION_METHOD.md`、`../MAPPING_GUIDE.md`。
> 更新：2026-08-26

---

## 一、结论总表

| 模块 | 采集能力 | 一句话 |
|---|---|---|
| Registry | 1/3 | 只采「覆盖写/修改」，不采「首次创建」和「删除」 |
| File | 4/5 | 创建/删除/修改/重命名采到；「打开」不采（行业常态缺口） |
| Account | 2/5 | 创建/登录采到；修改/删除/注销不采 |
| Driver | 2/3 | 加载/修改采到；「卸载」无事件 |
| Network | 3/5 | TCP/URL/下载采到；UDP 单播/DNS 不采 |

> Process / Hash / Service / ScheduleTask / Pipe / WMI / Device / GPO / BIT / PowerShell 待全量重测后补充。

---

## 二、Registry（1/3）— ⭐ 已更正（2026-08-26 推翻旧结论）

| Case | verdict | 依据 |
|---|---|---|
| REG-CREATE-001 | ❌ NOT_IMPLEMENTED | 创建（ABSENT→notepad）无 RegSetValue 事件 |
| REG-MODIFY-001 | ✅ IMPLEMENTED | 修改（notepad→calc 覆盖写）采到，RegOldValData→RegValData 齐全 |
| REG-DELETE-001 | ❌ NOT_IMPLEMENTED | 无 RegDeleteValue |

**⭐ 关键认知（更正）**：
- 旧结论「IOA 只采『值从无到有』（创建），不采『覆盖写』（修改）」**是错的**。
- 新日志实证（导出覆盖 14:05:22~14:07:51）：唯一一条 RegSetValue = `RegOldValData=notepad → RegValData=calc`（即**修改**）；创建（首次写入）没采到、删除没采到。
- **正确结论**：IOA 的 RegSetValue 只覆盖「值已存在→被覆盖写」，**不覆盖「首次创建」(ABSENT→value)**，且无 RegDeleteValue。
- 字段（实证）：`Child.RegKeyPath`（完整路径）/ `Child.RegValName` / `Child.RegValData` / `Child.RegValType`（中文「字符串」）/ `Child.RegGroupName` / `Child.RegOldValData`。

---

## 三、File（4/5）

| Case | verdict | 依据 |
|---|---|---|
| FILE-CREATE-001 | ✅ IMPLEMENTED | 创建落 FileWriteClose，靠 `Child.FileTotalWrite=0` 锚定（**无独立 FileCreate 事件**） |
| FILE-OPEN-001 | ❌ NOT_IMPLEMENTED（known_gap） | 读 .exe/.txt 均不触发 FileRead（行业常态缺口） |
| FILE-DELETE-001 | ✅ IMPLEMENTED | FileDelete 独立采到（sleep ≥5s 避开建删去重） |
| FILE-MODIFY-001 | ✅ IMPLEMENTED | FileWriteClose |
| FILE-RENAME-001 | ✅ IMPLEMENTED | FileRename，`Child.OldFilePath`（源）+ `Child.FilePath`（目标） |

**关键认知（踩坑）**：
1. ⭐ **无 FileCreate 事件**——「创建+写」统一记为 FileWriteClose；区分「纯创建」靠 `Child.FileTotalWrite=0`（只有纯创建是 0），`FileCreateOpName` 无区分度（都是「新建文件」）。
2. ⭐ **`Child.NodeName` 截断到 128 字符**——深目录长路径丢尾部；行为锚定统一用 `Child.FilePath`/`Child.OldFilePath`，禁用 NodeName。
3. **建删去重**：创建→删除间隔必须 `sleep ≥5s`（2s 会被 IOA 去重合并，回归教训）。
4. **FileRead 只采 .cab 归档**（系统进程），普通 .exe/.txt 读不上报 → OPEN known_gap。
5. **内核 minifilter 与 API hook 是两套采集**：现有样本 .NET 只触发内核层；API 层（IFileOperation/CopyFileExW）不在矩阵范围。

---

## 四、Account（2/5）

| Case | 行为 | verdict | EventLogId |
|---|---|---|---|
| ACCOUNT-CREATE-001 | NetUserAdd | ✅ IMPLEMENTED | 4720 |
| ACCOUNT-MODIFY-001 | 改密码 | ❌ NOT_IMPLEMENTED | 4723/4724 无独立事件 |
| ACCOUNT-DELETE-001 | NetUserDel | ❌ NOT_IMPLEMENTED | 无 4726 |
| ACCOUNT-LOGIN-001 | LogonUser | ✅ IMPLEMENTED | 4624 |
| ACCOUNT-LOGOFF-001 | CloseHandle | ❌ NOT_IMPLEMENTED | 无 4634/4647 |

**关键认知（踩坑）**：
1. **账户事件 Parent=lsass.exe**（进程锚点失效），登录事件 Parent=样本进程（MD5 锚定有效）——两类锚定方式不同。
2. **账户事件走 WinEventLog**：`Action.Name` = 英文内部名（AccountCreate/4720），中文名是 `Alert.RuleName`（仅告警命中才有）。
3. **AccountPwdReset 是建账户副产品**（4720+4724 成对），不是「改密码」；改密码（NetUserSetInfo 1003）无独立事件 → MODIFY known_gap。
4. **建删去重**：TARGET 后 `sleep 5s` 再 cleanup，否则 lsass 异步上报来不及。
5. **post_slack 串扰**：账户事件每 ~22s 一次，默认 30s post_slack 会串扰相邻 case → Account case 配 `pre/post_slack_s=3s`。

---

## 五、Driver（2/3）

| Case | verdict | 依据 |
|---|---|---|
| DRIVER-LOAD-001 | ✅ IMPLEMENTED | LoadDriver 内核态事件，靠「时间窗 + Action.Name + Child.FilePath 值」锚定 |
| DRIVER-MODIFY-001 | ✅ IMPLEMENTED | 本质是文件修改（FileWriteClose），MD5 锚定有效 |
| DRIVER-UNLOAD-001 | ❌ NOT_IMPLEMENTED | IOA 只有「加载 LoadDriver」，无「卸载驱动」 |

**关键认知（踩坑）**：
1. **LoadDriver 是内核态**：Parent=SystemIdle（PID=0，MD5=AAAA…），进程锚点全失效 → `matcher.py` 加 `kernel_mode: true` 跳过 actor/PID/MD5，只靠时间窗+operation+值。
2. **IOA 不采「服务名/驱动名」**：`Child.ServiceName`/`Child.DriverName` 不存在，可靠的是 `Child.FilePath`（值 = nonpnp.sys 路径）。
3. **Driver MODIFY 采为文件事件**（FileWriteClose+FileDelete），非驱动事件。
4. **快照必须用 `Baseline_Driver`**（加载 nonpnp.sys 需内核态环境，勿用普通快照）。

---

## 六、Network（3/5）

| Case | verdict | 依据 |
|---|---|---|
| NET-TCP-001 | ✅ IMPLEMENTED | HttpRequest（DstIp=93.184.216.34:80） |
| NET-UDP-001 | ❌ NOT_IMPLEMENTED | UDP 单播 sendto 未采 |
| NET-URL-001 | ✅ IMPLEMENTED | HttpsRequest（Host=www.baidu.com） |
| NET-DNS-001 | ❌ NOT_IMPLEMENTED | DnsQuery_W 无对应事件 |
| NET-DOWNLOAD-001 | ✅ IMPLEMENTED | HttpsRequest（Host=proof.ovh.net） |

**关键认知（踩坑）**：
1. **TCP/URL/Download 都落 HttpRequest/HttpsRequest**——URL 和 Download 靠 `Child.Host` 区分（不是靠 Action.Name）。
2. **`Child.Url` 恒空，实际在 `Child.Host`**（不含 `https://` 前缀）——正向值扫描方向反了命中不了，URL 走 match extra field。
3. **UDP 只采系统广播/组播**（DHCP/NTP/LLMNR/mDNS），应用层单播不采 → UDP known_gap。
4. **DNS 解析（DnsQuery_W）不采** → DNS known_gap。
5. 锚定用 MD5 正常（Parent=样本进程 NetworkActivityTest.exe）。

---

## 七、样本改动速查（历史）

| 模块 | 关键样本改动 |
|---|---|
| File | CREATE 改纯创建；DELETE 加 sleep 5s；OPEN 改读 .txt |
| Account | MODIFY 改密码(1003)；CREATE/MODIFY TARGET 后 sleep 5s |
| Registry | TARGET 补 RegistryPath；加 sleep 5s（对覆盖写无效） |
| Driver | （无）|

> 样本源码在 `E:\EDR\EDRTelemetry\`；编译产物在 `E:\EDR\EDRTest\samples\`。
