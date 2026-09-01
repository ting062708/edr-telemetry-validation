# 前端 ↔ 自动化 交接说明（HANDOFF）

> 目的：前端（E:\EDR\frontend）与自动化（E:\EDR\EDRTest\automation）之间的接口契约、中文命名约定、未完成事项清单。由前端侧整理，供自动化侧（Python/VM 侧）同学接续开发。
> 更新：2026-08-23

---

## 一、前端已接入的接口（server.py 现有路由，勿删勿改参数名）

| 路由 | 前端用途 |
|---|---|
| `GET /api/overview` | 侧栏模块树、三色统计、case 的 run_state / verdict |
| `POST /api/case/<id>/run` | 「执行样本」按钮（body: `{no_restore: bool}`）|
| `POST /api/case/<id>/match` | 「匹配」按钮（body: `{json: 日志路径}` 或空→`--non-interactive`）|
| `GET /api/task/<id>/events` | SSE 终端日志流 |
| `GET /api/case/<id>/stdout` | 匹配视图「样本自报 stdout」卡片 |
| `GET /api/case/<id>/result` | 匹配结果卡（读 `runs/<module>/<case>/match_result.json`）|
| `GET /api/case/<id>/logs` | 「导入日志」日志候选列表 |
| `POST /api/case/<id>/sample` | 「更新样本」上传（自动更新哈希）|
| `POST /api/module/<module>/deliver` | 加号菜单「批量投递本模块」（调 run_all.py deliver）|

---

## 二、前端展示的 match_result.json 字段（自动化侧保证这些字段稳定存在）

前端 `renderMatchResult` 读取以下字段（`match_result.json` 顶层）：

- `verdict`（字符串，如 `IMPLEMENTED` / `ERROR_LOG_INPUT`）→ 前端映射中文
- `verdict_icon`（前端不显示 emoji，可留）
- `test_case_id`、`sample_result`、`message`
- `field_coverage[]`：`{field, status(PASS/FAIL/...), actual_value, rule}` → 进度条 + 命中字段高亮（PASS=填充色块，非 PASS=灰字+状态）
- `match_stats`：`total_events / after_hostname / after_time / after_actor / after_pid / after_operation / candidate_count / coverage_status / filter_log[]` → 「事件漏斗」一行 + 可折叠「匹配过程」
- `observed_fields`：`{filled, total}` → 「观察字段填充 x/y」
- `missing_required_fields` / `partial_fields`（暂未展示，可后续接入）

**verdict 中文映射（前端内置）：**
`IMPLEMENTED=已实现、PARTIALLY_IMPLEMENTED=部分实现、NOT_IMPLEMENTED=未实现、PENDING=待判定、VIA_WINDOWS_EVENTLOG=Windows 事件日志、ERROR_SAMPLE=样本错误、ERROR_LOG_INPUT=日志输入错误、AMBIGUOUS=匹配歧义`

---

## 三、中文命名约定（前端内置映射，建议后端同步）

前端内置两套映射（`index.html` 顶部 JS）：

1. **模块名** `MOD_CN`：display 英文 → 中文（注册表/进程/文件/账户/网络/哈希/驱动/计划任务/服务/设备操作/命名管道/EDR 系统运维/WMI/BIT 任务/PowerShell/其他）
2. **行为名** `CASE_CN`：53 个 `case_id` → 中文行为名（如 `REG-CREATE-001→键/值创建`、`NET-TCP-001→TCP 连接`，全表见 index.html）

**给自动化的建议**：在 `test_cases.json` 每个 case 加 `"behavior": "键/值创建"` 字段（中文行为名），`collect_status()` 已把 `behavior` 透传为 `case.display`，前端可优先用 `c.display`、无则回退内置 `CASE_CN`。这样行为名维护在配置侧，前端映射表仅作兜底。

---

## 四、已完成模块（可直接用于前端演示/回归）

| 模块 | 结论 | 依据文档 |
|---|---|---|
| File（5）| 4 IMPLEMENTED + OPEN known_gap | `docs/FILE_MODULE.md`（已定稿）|
| Account（5）| 2 IMPLEMENTED（CREATE/LOGIN）+ MODIFY/DELETE/LOGOFF known_gap | `docs/ACCOUNT_MODULE.md`（已定稿）|
| Registry（3）| mappings 已建；REG-CREATE 有完整 behavior_fields，DELETE/MODIFY 为占位 | `config/mappings/registry/` |
| Driver（3）| mappings 已建（LOAD/MODIFY 有 behavior_fields，UNLOAD 占位）| `config/mappings/driver/` |

**File 关键认知（不要改回）：** CREATE=FileWriteClose+`Child.FileTotalWrite=0`（不是 FileCreate）；DELETE 必须 sleep≥5s 避开去重；锚定禁用 `Child.NodeName`（128 字符截断）。

**Account 关键认知：** 账户事件 Parent=lsass（走 skip_process_anchor+target_user），登录事件 Parent=样本（标准 MD5 锚定）；post_slack 配 3s 防串扰。

---

## 五、待自动化侧完成（TODO，按优先级）

### P0 — 前端依赖的配置
1. `case_result_map.json` 填二元映射（目前空 `{}`，前端全灰「待判定」）。格式 `{"REG-CREATE-001": "采集", ...}`，前端侧栏圆点/徽章自动变绿红灰。
2. `test_cases.json` 补 `behavior` 中文字段（见第三节），否则前端用内置表兜底（能跑，但改行为名要改前端）。

### P1 — 预留模块样本开发（前端已显示 17 个灰 case，点进去提示「预留模块，样本未接入」）
按 `SAMPLE_INVENTORY.md` 的 Migration gate（7 条标准）交付：

| 模块 | 需要的 EXE | 行为 | 快照 |
|---|---|---|---|
| Device Operations | VirtualDiskMountTest.exe（已有）/ UsbTest.exe（待建）| 虚拟盘挂载、USB 挂载/卸载 | ioa |
| Other (GPO) | GroupPolicyModificationTest.exe（已有）| 组策略修改 | ioa |
| Named Pipe | PipeLifecycleTest.exe（已有）| 管道创建/连接 | ioa |
| EDR SysOps | EDRAgentTest.exe（待建）| start/stop/install/uninstall/keepalive/error | ioa |
| WMI | WmiTest.exe（待建）| filter/consumer/bind | ioa |
| BIT JOBS | BitsTest.exe（待建）| create/transfer/cancel | ioa |
| PowerShell | PowerShellTest.exe（待建）| script-block | ioa |

新样本契约（见 README）：每个行为 = 一条 Action 参数，`TARGET-BEGIN/TARGET-END` 间单一行为，输出 RunID/TestCaseID/PID/hostname/UTC 时间/目标对象/结果/退出码，exit 0=成功 1=执行失败 2=用法错误。

### P2 — mappings 补全（config/mappings/<module>/<CASE-ID>.json）
已建：account / driver / file / registry。
**缺失：network、hash、process、scheduled_task、service**（9 个已接入模块里这 5 个没有映射目录）。格式参照 file 模块：
```json
{ "case_id": "...", "module": "...", "behavior_fields": {"stdout字段": "Child.日志字段"}, "observed_fields": ["Child.*"] }
```
方法照 `docs/STDOUT_SPEC.md` 第四节 checklist：跑样本→锁事件→列有值字段→反推 stdout 该补什么→反推映射。

### P3 — 需要向自动化确认/不清楚的点

**已确认（用户答复 2026-08-23）：**
1. ✅ **Network 样本是合并的**：`NetworkActivityTest.exe` 是多 Action 样本，`--case NET-TCP-001` 等参数区分 5 个行为。SAMPLE_INVENTORY.md 里 DnsTest/TcpTest/UdpTest/UrlTest/DownloadTest 是旧独立样本描述，未同步进 test_cases.json。前端可直接用合并样本，无需改造。
2. ✅ **批量投递需要单独的快照开关**：快照策略有三态（required/never/auto），前端「不恢复快照」只是透传 `--no-restore-snapshot`，required 策略会强制恢复、never 本来就跳过。需要自动化侧配合：给 run_all.py deliver 加「忽略快照策略」参数（如 `--force-no-restore`，覆盖 required），前端在加号菜单/信息条加对应开关。具体参数名与语义由自动化侧定，前端照透传。

**待查（用户尚未答复）：**
1. ❓ Process 的 RemoteThread/Tamper 是否已在 ProcessLifecycleTest.exe 实现（需读 Process 源码）。
2. ❓ Hash 模块 3 个行为（md5/sha256/imphash）是否已在 IOA 日志验证过字段（需跑 Hash 日志）。

### P4 — 前端侧想接但还缺的
1. **capability_matrix.csv**（run_all.py matrix 产物）：前端想做「能力矩阵总览」视图，需要后端出一个 `GET /api/matrix` 路由解析 CSV。
2. **stdout 命中字段高亮**：现在 stdout 卡片是纯文本；想按 field_coverage 的 actual_value 在 stdout 里高亮命中行（值扫描可视化），需要确认 stdout TARGET 块的值和日志字段值的大小写/前缀差异（如 `.\\` 前缀坑，见 STDOUT_SPEC 五）。
3. **本地日志接入**：目前日志靠手动导出 JSON 上传选择；若 IOA 端点本地有落盘日志目录，可加路由直读，省去手动导出。

---

## 六、前端当前运行方式

```powershell
cd E:\EDR\frontend
python server.py        # http://127.0.0.1:8000
```
- 静态页 `index.html` 改完刷新即生效，无需重启。
- `server.py` 的 `ROOT` 指向 `E:\EDR\EDRTest\automation`（frontend 移到 E:\EDR 下后已改）。
- 全局串行队列：同一时刻只跑一个 VM 任务（run/match/deliver 共用）。


---

## 七、第二轮前端改造（2026-08-23）— 新增对接要求

### 前端本轮已自行实现（无需后端改动）
1. **本地测试状态记录**：localStorage 记录每个 case 的「已测 / 时间 / 终端日志 / 上次判定」，侧栏显示「已测」小标，进详情自动恢复上次终端输出（带执行时间头）。重装浏览器/换机器会丢失，如需跨端持久化需后端存。
2. **case 侧栏状态文案**：已采集（采集）/ 采集缺失（未采集=IOA 遥测缺失）/ 待判定（匹配过未定论）/ 未匹配（还没跑匹配）。基于 overview 的 binary + has_match_result。
3. **匹配前日志确认流程**：点「匹配」先弹日志确认卡——默认「自动探测最新」（显示最新文件名+mtime），可选其他候选；无日志时明确报错（提示到 log/<模块>/ 导出）；最新日志超过 24h 显示过期警告。确认后才发匹配请求，避免盲匹配。

### 需要自动化侧支持（P5，按优先级）
1. **result 记录日志来源**（P5.1，推荐）：matcher/runner 把本次实际使用的日志（文件名 + mtime + 路径）写进 match_result.json（如 used_log: {name, mtime, path}）。前端在代码卡 header 显示「本次匹配日志：xxx（时间）」，用户才能确认刚导出的新日志确实被用上。现在前端只能从 /logs 候选列表推断，无法证明。
2. **快照三态开关**（P5.2，P3.4 后续）：run_all.py deliver 加「忽略快照策略」参数（覆盖 required），前端加号菜单加对应开关；参数名语义由自动化侧定。
3. **批量投递进度**（P5.3，可选）：deliver 是模块级多 case，SSE 日志很长；建议 server.py 在 deliver 事件里带当前进度（如 progress: 3/6），前端可渲染进度条。
4. **P3 待查项**（提醒）：Process RemoteThread/Tamper 是否实现、Hash 字段是否验证，仍需答复。

### 前端文案约定（自动化 test_cases.json 可选同步）
- 建议给每个 case 加 behavior 中文字段（如 行为: "键/值创建"），前端 CASE_CN 映射与此对齐；不加则前端继续用内置 53 项映射。


---

## 八、第三轮前端改造（2026-08-23 晚）— 新增接口与快照三态

### 快照三态（已确认，来自 config/vm_config.json）
- `snapshot_policy: auto`（全局默认）+ `snapshot_policy_map`：File/Account=required（强制恢复）、ScheduledTask/Service=never（永不恢复）、其余走 auto（默认恢复，除非 --no-restore-snapshot）。
- 前端信息条「不恢复快照」开关 = 透传 --no-restore-snapshot，只影响 auto 策略；required 仍强制恢复。
- 前端建议（P5.2 已提）：加「忽略快照策略」开关覆盖 required，需 run_all.py/telemetry_runner.py 加参数。

### 前端新增接口（server.py 已实现，自动化 CLI 无需改动）
1. `GET /api/case/<id>/stdouts`：stdout 版本列表（历史 {case}_{RunID}_stdout.txt + 最新指针标记），按最新优先排序。
2. `GET /api/case/<id>/stdout?path=<name>`：按版本读指定 stdout（不带参数读最新指针，行为不变）。
3. `POST /api/case/<id>/logupload`：上传本地 IOA 导出 JSON 到 log/<module>/，上传后自动进入匹配候选探测。
4. `GET /api/case/<id>/sampleinfo`：样本文件信息（文件名/大小/mtime/Support 附属清单），供前端右键查看。

### 前端本轮交互改动
- 侧栏 30%（右 70%）、组件缩小一档（模块头 64px/18px、case 15px）。
- 「概览」标题下加横线。
- 匹配日志确认改为**搜索栏式窄条**（默认自动最新，点开可滚动候选，超 24h 过期警告）。
- 代码卡 header 新增 **stdout 版本下拉 + 日志版本下拉**（默认最新）。
- **右键行为**：查看样本文件名/更新时间/大小/附属文件 +「更新样本」快捷项。
- 「导入日志」= 本地上传 JSON；「更新样本」= 本地上传 EXE + Support 文件（含哈希审计回执）。

### 版本更新制探讨（自动化侧待完善，P6）
前端目前：stdout 版本 = 按 RunID 历史文件列表；日志版本 = log 目录候选（mtime 倒序）。均为「文件即版本」的粗粒度版本制。建议自动化侧：
1. 日志文件命名规范（如 `<模块>_<YYYYMMDD_HHMM>.json`），便于按导出时间识别版本；
2. 过期日志归档目录（log/<模块>/archive/），候选列表只列活跃版本；
3. match_result.json 记录 used_log（P5.1），把「本次判定用了哪个版本」落盘。

### 映射文件说明
新增 `docs/MAPPING_GUIDE.md`：映射文件格式、dot-path 规则、写新映射的工作流程（跑样本→导日志→初匹配→对字段→重匹配→写结论）、verdict 状态表、常见坑（时间窗、.\\ 前缀、账户类 WinEventLog、PID 缺失）。用户可按此文档直接在工具上开展数据采集能力验证。
