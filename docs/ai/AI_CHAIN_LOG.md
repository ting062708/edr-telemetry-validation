# AI 自动化链路拆解 + 行为记录（AI_CHAIN_LOG）

> 定位：AI 辅助映射自扩展工程的「链路形态 + 每步/每模块完成状态」台账。
> 维护规则：链路每增长一步、每个行为模块每完成一次，都更新本表 + changelog；有问题实时追加，不改历史（留痕）。

---

## 一、自动化链路拆解（当前形态）

```
① 样本(触发行为, Migration gate 7条)
   → ② 冻结协议 stdout（只补确定性字符串值）
   → ③ 手动导出 IOA 日志(json)
   → ④ 正向值扫描：stdout 值 → 扫日志找落点（discover_mapping.py）
   → ⑤ 反向剖析：日志有值字段 → 反推样本补什么 stdout 值
   → ⑥ 生成映射：behavior_fields + observed_fields
   → ⑦ verdict 三态判定（对 / 疑问 / 错）
   → ⑧ 收紧样本行为：EDR 反哺（触发方式）+ Sysmon 验证（行为确实发生）
   → ⑨ 行业对比：IOA 三态 × Sysmon/MDE/CrowdStrike/SentinelOne
```

---

## 二、各环节状态

| # | 环节 | 状态 | 说明 / 落点 |
|---|---|---|---|
| ① | 样本 | ✅ 已就绪 | Migration gate 7 条 + 10 样本编号（BEHAVIOR_LEDGER.md）|
| ② | stdout | ✅ 已就绪 | 冻结协议（STDOUT_SPEC.md）|
| ③ | 导出日志 | ⚠️ 手动 | 不走自动化（目标已更新）|
| ④ | 正向值扫描 | ✅ 可用 | `tools/discover_mapping.py` |
| ⑤ | 反向剖析 | 🟡 方法论已定，工具待完善 | STDOUT_SPEC.md 反向剖析方法论 |
| ⑥ | 生成映射 | ✅ 可用 | `config/mappings/<module>/` |
| ⑦ | verdict 三态 | ✅ 已定稿 | `config/case_result_map.json`（对/疑问/错）|
| ⑧a | EDR 反哺（触发方式）| ✅ 已做 File | 边界：只反哺触发方式，禁反哺锚点值 |
| ⑧b | Sysmon 验证 | ✅ 已跑通 | evtx 自动导出 + 平行对照（AI_MAPPING_METHODOLOGY §八）|
| ⑧c | 行业规范样本（方式 3）| 🟡 全局定义已定，样本待重编译 | 每个 case 必做：收紧样本 + 行业规范样本两个版本（§十.4）|
| ⑨ | 行业对比 | ✅ 已落地 | `config/industry_baseline.json` + summary 行业对比列 |

---

## 三、行为模块完成记录

| 模块 | 状态 | 记录文档 | 备注 |
|---|---|---|---|
| **File** | ✅ 样本审计 + 重跑 | `FILE_SAMPLE_AUDIT.md` | 目标文件类型已定稿 A（有内容的 .exe）|
| Account | ⏳ 待做 | — | |
| Registry | ⏳ 待做 | — | |
| Driver | ⏳ 待做 | — | 驱动修改定义待对齐 |
| Network | ⏳ 待做 | — | |
| Process / Hash / ScheduledTask / Service | ⏳ 待做 | — | 15 待定稿 case |

---

## 四、changelog（实时更新，留痕）

- **2026-08-24**：链路新增 ⑧（EDR 反哺 + Sysmon 验证）与 ⑨（行业对比）；File 模块完成样本审计 + 重跑（见 FILE_SAMPLE_AUDIT.md）。
- **2026-08-24**：全局执行指令（备份记录 / 链路增长记录 / 实时更新）写入 AI_MAPPING_METHODOLOGY §十。
- **2026-08-24**：File 目标文件类型定稿 A（有内容的 .exe），写入 METHODOLOGY §九方式 3；链路新增 ⑧c 行业规范样本（每个 case 必做收紧+规范两个版本）。
- **2026-08-24**：stdout_parser 全周期适配——单/多 phase 匹配改为按 `test_case_id`/`phase_id` 精确取时间窗（不再盲目取 runs[0]），适配 5-phase 行业规范样本。
- **2026-08-24**：Sysmon 配置补盲区——新增 FileDelete include `C:\EDRTest`（原 SwiftOnSecurity 配置无 FileDelete 规则，连 .exe 删除都不记录）+ FileCreate 补 `C:\EDRTest`，配置已应用（待重打快照固化）。
- **2026-08-24**：诊断 IOA 云端无事件根因——Agent 登录态过期（登录/身份缓存停在 7/23），本地 EDR 采集正常（08-24.db 有样本事件）但未上报云端；待重新登录 IOA 后重打快照。
- **2026-08-24（更正）**：上一条「登录态过期」为**误诊**——真实原因是 IOA 控制台**筛查条件选错**（云端实际有日志）。相关结论作废：登录态 30 天有效期、登录态自检工具；快照重打不再依赖「登录 IOA」前提。
- **2026-08-24**：日志导出路径规范定稿——首选 `log/<module>/json/*.json`，`<module>` 首字母大写（File/Registry/…，非小写），探测范围与排序规则见行为链 ② 02_run_sample.md「目前规则」。

---

## 五、搁置与待办（2026-08-24，用户拍板：先用冻结版样本跑 baseline）

> 以下工程/问题已「记录思路、暂不实施」，恢复时从此处认领。

### 搁置项（工程量较大，暂缓）

| 项 | 状态 | 说明 |
|---|---|---|
| ~~IOA 登录态自检工具 `ioa_health.py`~~ | ❌ 作废 | 基于「登录态过期」误诊设计；真实根因是**筛查条件选错**。可改做「导出筛查条件检查清单」替代 |
| 行业规范样本（方式 3）重编译 | 🅿️ 搁置 | 回退 3 处 EDR 反哺（创建写内容/删除不 sleep/OPEN 改 .exe）+ 统一 .exe；同学重编译 + 同步哈希 |
| Sysmon 配置补盲区后的快照重打 | ⏸️ 待做（不依赖登录）| 已应用 FileDelete/FileCreate include，但还没重打 IOA_Sysmon 固化 |
| Driver 模块 Baseline_Driver 快照装 Sysmon | ⏸️ 待 Driver 重测前 | |

### 关键结论（不搁置，已定型）

- **文件类型 = 有内容的 .exe（方案 A）**：.txt 是 IOA + Sysmon 双盲区，测出的“未采集”说服力弱。
- ~~**IOA 登录态有效期 ≈ 30 天**~~ ❌ 作废（误诊）：真实根因是导出时筛查条件选错，云端有日志，无「登录态过期」问题。
- **EDR 反哺红线**：只动触发方式、禁反哺锚点值（METHODOLOGY §九）。
- **冻结版样本已验证可用**：File 5 case 全 PASS + Sysmon evtx 就绪，是当前 baseline 的数据源。
