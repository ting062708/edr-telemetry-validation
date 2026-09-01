# stdout 定义规范 & IOA 记录逻辑剖析

> 目的：样本 stdout 的 TARGET 块应该输出「样本确定知道、且 IOA 会原样记录」的值，让值扫描能精确映射到日志字段。本文档记录每个模块的「样本行为 ↔ IOA 记录逻辑」剖析结果，作为写样本和补映射的对照基准。
>
> 方法论：**反向剖析** —— 从日志里样本事件的「有值字段」反推 stdout 该输出什么、映射该补什么，而不是正向猜值。

---

## 一、核心原则（通用）

| 值类型 | 例子 | 是否补 | 原因 |
|---|---|---|---|
| 字符串标识值 | 账户名、文件名、路径、主机名、进程名、注册表值名 | ✅ **补** | IOA 原样透传，值扫得到 |
| 枚举/状态值 | LogonType、FileCreateOpName | ⚠️ 用中文或走 match | IOA 用中文本地化，样本输出英文对不上 |
| 系统加工值 | UAC flags、空文件 MD5 | ❌ 不补 | IOA 会规范化，值永远对不上 |
| 不稳定值 | SID | ❌ 不补 | 每次重建对象会变 |

**一句话**：补「样本能算出、且 IOA 记的就是这个值」的字段，避开「IOA 会翻译/加工/重算」的字段。

---

## 二、File 模块剖析

### 2.1 行为 ↔ 事件对照

| 样本行为 | 样本 API | IOA 事件 | 判定字段 | verdict |
|---|---|---|---|---|
| CREATE | FileStream(CreateNew)+Write | **FileWriteClose** | FileCreateOpName=新建文件, FileSize=0 | IMPLEMENTED |
| OPEN | FileStream(Open,Read) | **无事件** | — | known_gap |
| DELETE | File.Delete | FileDelete | — | IMPLEMENTED |
| MODIFY | FileStream(Open,Write) | FileWriteClose | FileSize=149 | IMPLEMENTED |
| RENAME | File.Move | FileRename | OldFilePath源+FilePath目标 | IMPLEMENTED |

### 2.2 关键发现

1. **FileCreate 不存在** —— IOA 把「创建+写」统一记为 FileWriteClose，靠 `FileCreateOpName=新建文件` + `FileSize=0` 区分"空创建"。

2. **FileCreateOpName 是 IOA 内部判定**（对 CreateFile disposition 的判定），三值：
   - `新建文件` = CREATE_NEW
   - `打开文件` = OPEN_EXISTING
   - `覆盖写文件` = CREATE_ALWAYS / TRUNCATE
   样本无法预知 IOA 会写哪个值 → **stdout 不补此字段**。

3. **FileRead 只采 .cab 归档文件** —— 全表 FileRead 全是系统进程（wuauclt/mousocoreworker/OneDriveSetup/svchost）读 `.cab`。普通 .exe/.txt 读不上报。这是 IOA 策略，改样本读普通文件没用。→ OPEN 判 known_gap（除非读 .cab）。

4. **FileRename 是字段最全的事件**：OldFilePath（源）+ FilePath（目标）+ FileMd5 + FileContentType。

5. **FileMd5 只对有内容文件有值** —— 空文件（CREATE 纯创建 Size=0）IOA 不记 FileMd5。所以 ContentMd5 对 CREATE 扫不到，对 MODIFY/RENAME 能扫到。

### 2.3 File 各 case 的 stdout 定义

| Case | 该输出（能对上）| 不该输出 |
|---|---|---|
| CREATE | Path、FileName、Size(=0) | ContentMd5（空文件无 FileMd5）|
| OPEN | Path、FileName | —（本身无事件）|
| DELETE | Path、FileName | — |
| MODIFY | Path、FileName、Size、ContentMd5（有内容→FileMd5）| — |
| RENAME | SourcePath、DestinationPath、FileName（目标）| — |

---

## 三、Account 模块剖析

### 3.1 行为 ↔ 事件对照

| 样本行为 | 样本 API | IOA 事件 | Parent | verdict |
|---|---|---|---|---|
| CREATE | NetUserAdd | AccountCreate(4720) + AccountPwdReset(4724) | lsass.exe | IMPLEMENTED |
| MODIFY | NetUserSetInfo(改密码) | 无独立事件 | — | known_gap |
| DELETE | NetUserDel | 无（4726 缺失）| — | known_gap |
| LOGIN | LogonUser | LoginSuccess(4624) + LoginExplicitCredentials(4648) | **样本进程** | IMPLEMENTED |
| LOGOFF | CloseHandle(token) | 无（4634/4647 缺失）| — | known_gap |

### 3.2 关键发现

1. **账户事件 Parent=lsass，登录事件 Parent=样本进程** —— 两类锚定方式不同：账户事件走 skip_process_anchor + target_user 值锚定，登录事件走标准 MD5 锚定。

2. **AccountPwdReset 是建账户副产品** —— NetUserAdd 带初始密码，同时触发 4720（创建）+ 4724（密码重置）。改密码（NetUserSetInfo1003）没有独立事件。→ MODIFY known_gap。

3. **枚举值中英不对应** —— stdout `LogonType=Interactive`（英文），IOA 记 `Child.LogonType=交互式`（中文）。枚举值走 match 固定值（中文），不走值扫描。

4. **系统加工值** —— 样本设 `Flags=0x221`，IOA 记 `NewUacValue=0x15`（系统规范化）。→ 不补。

5. **不稳定值** —— TargetSid 每次重建账户都变。→ 不补。

### 3.3 Account 各 case 的 stdout 定义

| Case | 该输出 | 不该输出 |
|---|---|---|
| CREATE | Account（去 `.\` 前缀）、SamAccountName、Comment（若日志有）| Flags/UacValue |
| LOGIN | Account、SamAccountName | LogonType（走 match 中文）|
| MODIFY/DELETE/LOGOFF | Account | —（known_gap）|

---

## 四、后续模块剖析 checklist

每做一个模块，按这个顺序剖析：

1. **跑样本 → 拿日志 → 锁定样本事件**（时间窗 + 进程名 + Action.Name）
2. **列出样本事件的「有值」字段**（`Child.*` 非空值）
3. **逐字段判定**：样本能确定输出吗？值格式对得上吗（尤其中文/英文、系统加工）？
4. **反推 stdout**：能对上的 → 补进 TARGET 块；对不上的 → 走 match 固定值或放弃
5. **反推映射**：值扫描 stdout 值 → 落到日志哪些字段 → behavior_fields；日志有值字段 → observed_fields

---

## 五、已踩过的坑（避免重蹈）

1. `.\` 前缀导致值扫描 0 命中（Account）→ 去掉前缀
2. 枚举值英文 vs IOA 中文（LogonType）→ 走 match 中文
3. 空文件 MD5 样本算 d41dcd9，IOA 不记 FileMd5 → 空文件不补 ContentMd5
4. UAC flags 0x221 vs IOA NewUacValue 0x15（系统加工）→ 不补
5. 连续快速启动同一 exe → IOA 进程监控去重 → 快照策略用 required 拉大间隔
