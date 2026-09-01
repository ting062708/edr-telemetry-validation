# 前端设计规范（DESIGN SPEC）

> 目标：把当前"文档阅读式"前端，改造成**深色测试控制台**。本规范供 Kimi 实现时照做，字段名 / 路由 / 状态值均为契约，不要另起炉灶。
> 视觉参考：同目录 `_mockup.html`（自包含，双击即可在浏览器看效果）。

---

## 一、定位与设计原则

1. **一句话**：「跑完就能看到结果，看到结果就能继续操作」——主界面不跳页完成所有高频操作。
2. **三级操作**：单 case / 单模块 / 全量，每级都有"跑"和"匹配"。
3. **状态前置**：判定 / 样本 / 日志 / Sysmon 四列状态一眼看全。
4. **接口可扩展**：为回归 + Sysmon 对照 + baseline 校验预留接口，前端先留位、后端返回占位。

## 二、技术约束

- **不引入前端框架**（不用 React/Vue），原生 HTML + CSS + 原生 JS 即可，保持现有"改 html 即生效"的轻量模式。
- Flask 后端 `server.py` 的**现有路由和参数名一律不动**（见 FRONTEND_HANDOFF.md 契约）。
- 静态文件放 `frontend/` 下，`server.py` 的 `static_folder` 已指向该目录。
- 允许拆文件：`index.html` / `style.css` / `app.js`，但必须无构建、无 npm。

## 三、整体布局

```
┌────────────────────────────────────────────────────────────────────┐
│ 顶栏 topbar (48px)                                                  │
│  ◈ EDR 采集验证    [快照:ioa✓] [全量投递▶] [全量匹配✓] [导入日志]      │
├─────────┬──────────────────────────────────────────────────────────┤
│ 侧栏     │  能力矩阵 matrix（主区，滚动）                              │
│ sidebar │  ┌─────────┬────────┬──────┬─────┬─────┬──────┬────────┐  │
│ (160px) │  │ Case    │ 行为   │ 判定 │ 样本 │ 日志 │Sysmon│ 操作   │  │
│ 模块列表 │  ├─────────┼────────┼──────┼─────┼─────┼──────┼────────┤  │
│         │  │REG-CREATE│键/值创建│🟢    │ ✓  │ ✓  │ ✓   │ ▶ ✓   │  │
│         │  └─────────┴────────┴──────┴─────┴─────┴──────┴────────┘  │
│         │  模块头：Registry  [跑本模块▶][匹配本模块✓]                  │
├─────────┴──────────────────────────────────────────────────────────┤
│ 终端 terminal（可折叠，展开约 220px）                                  │
│  [12:00:01] ▶ REG-CREATE-001 → TARGET Operation=RegistryCreate      │
└────────────────────────────────────────────────────────────────────┘
```

- 侧栏固定 160px；终端默认折叠成一条 28px 的把手，点击展开 220px。
- 详情不进主区，用**右侧抽屉 drawer**（点击矩阵行滑出，宽 560px）。

## 四、视觉规范（CSS 变量，直接复制）

```css
:root {
  /* 背景层 */
  --bg:         #0f1117;   /* 页面底色 */
  --panel:      #161a23;   /* 卡片/表格/抽屉底 */
  --panel-2:    #1b202c;   /* 悬浮/表头底 */
  --border:     #2a3040;   /* 分割线/边框 */

  /* 文字 */
  --text:       #e6e8ee;   /* 主文字 */
  --text-dim:   #8b93a7;   /* 次要文字 */
  --text-faint: #5a6272;   /* 占位/禁用 */

  /* 状态色（判定徽章，全站统一） */
  --ok:     #2fbf71;   /* 采集/通过 */
  --warn:   #f0a52a;   /* 疑问/部分 */
  --bad:    #e5484d;   /* 缺失/失败 */
  --muted:  #5a6272;   /* 待测/未接 */

  /* 强调 */
  --accent: #4c8dff;   /* 主按钮/链接 */
  --mono:   "JetBrains Mono", Consolas, "Courier New", monospace;
  --sans:   -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
}
```

**硬约束：**
- 深色主题，禁止浅色/白色大底。
- 状态色只允许上面四个 `--ok/--warn/--bad/--muted`，不得另造绿黄红灰。
- 终端与字段值用 `--mono`，其余用 `--sans`。
- 行高 36px、表格紧凑，一屏尽量塞 20+ case；**禁止**大圆角、投影、渐变背景、营销风大图。

## 五、组件规格

### 5.1 顶栏 topbar（48px）
- 左：`◈ EDR 采集验证`（标题）
- 中：快照状态胶囊 `[快照: ioa ✓]`（读 `vm_config.json` 当前快照，可选）
- 右按钮（大，primary）：
  - `全量投递 ▶` → `POST /api/all/deliver`
  - `全量匹配 ✓` → `POST /api/all/match`
  - `导入日志` → 触发文件上传（拖拽 .json/.zip），落到当前选中模块
- 运行中：对应按钮转 spinner + 禁用，防重复提交。

### 5.2 侧栏 sidebar（160px）
- 模块列表：Account / BIT / Device / Driver / File / GPO / Hash / Network / Pipe / PowerShell / Process / Registry / ScheduleTask / Service / WMI。
- 每项显示：模块名 + 该模块 case 数徽章。
- 点击切换矩阵主区的过滤（默认"全部"）。
- 模块名中文映射沿用 `MOD_CN`（见 FRONTEND_HANDOFF 第三节）。

### 5.3 能力矩阵 matrix（主区）

**列定义（顺序固定）：**

| 列 | 字段来源 | 显示 |
|---|---|---|
| Case | `case.id` | `REG-CREATE-001`（等宽） |
| 行为 | `case.behavior` 或内置 `CASE_CN` | 中文行为名 |
| 判定 | `case_result_map[case.id]` | 四色徽章：采集/缺失/待测/手动 |
| 样本 | `run_state`（是否已跑过） | `✓` 已投递 / `−` 未投递 |
| 日志 | 该 case 是否有日志候选 | `✓` 有 / `−` 无 |
| Sysmon | 该 case 是否有 sysmon evtx | `✓` 有 / `−` 无 |
| 操作 | 行内按钮 | `▶` 跑 + `✓` 匹配 |

**数据来源：** 现有 `GET /api/overview`（`collect_status()`）已返回每 case 的 `run_state / verdict / has_match_result / binary` 等，前端按此渲染，不够的字段在 overview 侧补，不改前端逻辑。

**判定徽章映射：**
- `采集`（绿）← binary 采集/verdict IMPLEMENTED
- `缺失`（红）← 采集缺失/verdict NOT_IMPLEMENTED
- `疑问`（琥珀）← 部分/UNCERTAIN
- `待测`（灰）← 未匹配/无结果
- `手动`（蓝紫，新增）← USB / EDR 运维 两个手动能力（见第七节）

**模块头行**：`Registry  [跑本模块 ▶] [匹配本模块 ✓]` → `POST /api/module/<module>/deliver` 和 `run_all.py match --module`（如无 module 级 match 路由，则前端循环逐个 case 调 `/api/case/<id>/match`，或等后端补 `/api/module/<module>/match`）。

### 5.4 详情抽屉 drawer（560px，点矩阵行滑出）

Tab 结构（顶部 4 个 tab，默认「结果」）：

| Tab | 内容 | 数据来源 |
|---|---|---|
| 结果 | verdict 徽章 + 字段命中列表（`field_coverage`）+ 事件漏斗（`match_stats`）+ 匹配过程折叠 | `GET /api/case/<id>/result` |
| 样本 | stdout 自报（`TARGET` 块高亮）+ 样本文件信息 | `GET /api/case/<id>/stdout` + `/api/case/<id>/sampleinfo` |
| 日志 | IOA 日志候选列表（可切换版本）+ 归一化事件 | `GET /api/case/<id>/logs` + `/api/case/<id>/events` |
| Sysmon | **预留**：行为是否真实触发的对照 | `GET /api/case/<id>/sysmon`（占位） |

抽屉底部操作条：`▶ 跑样本` / `✓ 匹配` / `关闭`。

### 5.5 终端 terminal（底部）

- 默认折叠成 28px 把手（显示最后一行日志 + `▸`）。
- 点击展开 220px，内容为 SSE 流：`GET /api/task/<id>/events`。
- 顶部右侧：`清空`（前端本地清空）+ `停止`（`POST /api/task/<id>/stop`）。
- 输出等宽字体，运行中显示绿色小圆点闪烁，结束后灰点。

## 六、API 契约

### 6.1 现有（不改，直接复用）

见 FRONTEND_HANDOFF.md 第一节。核心：`/api/overview`、`/api/case/<id>/run|match|result|stdout|logs|events|sampleinfo|mapping|stdouts|logupload|sample`、`/api/module/<m>/deliver`、`/api/all/deliver|match`、`/api/task/<id>/events|stop`、`/api/industry`、`/api/classmate_baseline`。

### 6.2 新增预留（前端先做 UI + 占位请求，后端返回 `{status:"todo"}` 即可）

| 接口 | 用途 | 前端位置 |
|---|---|---|
| `GET /api/case/<id>/sysmon` | 返回该 case 的 Sysmon 对照结论（行为是否真实触发）| 矩阵 Sysmon 列 + 详情 Sysmon tab |
| `GET /api/case/<id>/logcheck` | 返回"该 case 是否在 IOA 日志有记录"的**结论** | 矩阵「日志」列 hover 详情 |
| `GET /api/baseline/check` | 对比 `case_result_map` 与当前 match，标不一致 | 顶栏「baseline 校验」按钮 |
| `GET /api/regression` | 两轮结果 diff | 顶栏「回归对比」按钮 |

前端对这四个接口的调用要**容错**：返回 404/`{status:"todo"}` 时显示"待后端实现"，不报错不崩溃。

## 七、手动模式能力（重要）

以下两个能力**不做自动化**，复用已有手动测试结果：

| 能力 | 对应 case / 样本 | 处理 |
|---|---|---|
| USB 插拔 | Device 模块（UsbTest 待建） | 判定列显示「手动」徽章（蓝紫），无「▶ 跑」按钮，只有结果展示 |
| EDR 运维（Agent 启停/安装） | EDRAgentTest 待建 | 同上 |

- 前端从 `case_result_map` 或 `test_cases.json` 的 `runner_type=manual` 识别手动 case。
- 手动 case 的操作列置灰，仅展示结果，不调 run/match。

## 八、分阶段实现

- **Phase 1（先能测）**：顶栏 + 侧栏 + 能力矩阵 + 行内 `▶/✓` + 底部终端 + 详情抽屉（结果/样本/日志 3 tab）。全部复用现有 API，不改 server.py。
- **Phase 2（预留）**：Sysmon 列 + 详情 Sysmon tab + 4 个新接口占位 UI + 手动模式徽章。
- **Phase 3（润色）**：日志确认条、快照三态开关、批量进度条、回归/基线按钮。

## 九、验收标准

1. 从打开页面到「跑一个样本」不超过 2 次点击。
2. 矩阵一屏可见 ≥ 20 个 case，判定状态一眼可辨。
3. 跑样本 / 匹配 / 全量跑 / 全量匹配四类操作都能在终端看到实时输出。
4. 深色主题、四色状态徽章、等宽终端与 `_mockup.html` 一致。
5. 手动模式能力（USB / EDR 运维）显示「手动」徽章、无自动化按钮、结果可看。

---

## 附录 A · 视觉规范 v2（美化稿，2026-09-01 定）

> 视觉参考升级为同目录 `_mockup_v2.html`。**功能、路由、字段、组件结构全部不变**，以下为纯视觉增量，实现时以 v2 为准。第四节 CSS 变量整段替换为本节变量。

### A.1 调色板替换（层次靠明度差，不用投影/渐变）

```css
:root{
  --bg:#0b0e14; --panel:#11151d; --panel-2:#161b26; --raised:#1c2230;
  --border:#232a3a; --border-strong:#2e3750;
  --text:#e8eaf0; --text-dim:#97a0b4; --text-faint:#5b6376;
  --ok:#34c77b; --warn:#f2a93b; --bad:#e8545a; --muted:#5b6376;
  --manual:#8b7cf6; --accent:#5b93ff; --accent-dim:#3d6fd6;
  --r:6px;
}
```

### A.2 新增/改动组件（均为纯展示，数据源沿用现有 API）

| 组件 | 说明 | 数据来源 |
|---|---|---|
| 顶栏「使用手册」按钮 | **一级入口**，`--manual` 紫描边与其它按钮区分，F1 快捷键；点击滑出手册面板（640px），内容复用 `GET /api/manual` | `/api/manual` |
| 汇总条 statstrip | 矩阵顶部一行：采集/疑问/缺失/待测四张统计卡 + 覆盖率进度条；**让"重跑后结果更新了"一眼可见** | `/api/overview` 聚合 |
| 模块带 module-band | 替代原 module-head，吸顶；含模块名+中文+内联判定统计（`1 采集 1 疑问 1 待测`）+ 模块级按钮 | `/api/overview` 聚合 |
| 侧栏健康条 | 每个模块名下一排 3px 色块（每 case 一格，按判定着色），模块状态不进矩阵也能扫到 | `/api/overview` 聚合 |
| 侧栏手动分区 | 手动模块（Device/EDR 运维）与自动模块之间加分隔线 + `手动 MANUAL` 标签 | 静态 |
| 状态点 `.st` | 样本/日志/Sysmon 三列从裸 `✓/−` 改为「色点+文字」（已投递/3 版/已对照），hover 可出详情 | `/api/overview` |
| 徽章圆点 | 判定徽章内加 6px 圆点（`badge > i`），色彩识别更快 | — |
| 事件漏斗 | 详情抽屉「结果」tab 内，`match_stats` 渲染为横向阶梯条（条宽 ∝ 数量，末段绿、中间琥珀） | `/api/case/<id>/result` |
| 终端分级配色 | 输出行按级别着色：INFO 蓝 / OK 绿 / WARN 琥珀 / ERR 红；行尾闪烁光标；终端栏右置「清空/停止」 | SSE 流 |
| 图标系统 | 全部内联 SVG（play/check/upload/book/radar），**不引用外部图标库、不用 emoji 当图标** | — |

### A.3 硬约束继承（不变）

深色主题、四状态色+手动紫、等宽终端、行高 ≤38px 紧凑表格、禁大圆角/投影/营销渐变、无框架无构建。

### A.4 用户已确认的口径变更（2026-09-01）

1. **L2 Sysmon 归因不在前端做判定**——样本由人工先验证再入 case，前端 Sysmon 列/tab 只做「有无对照」展示，不承担「样本待验证 vs 能力缺失」的归因逻辑（归因口径本身已认可，线下执行）。
2. **前端历史不迁后端**，保留 localStorage；结果可见性由汇总条（A.2）保证。
3. **回归方式：45 个 case 全量重跑**（真开 VM），测试框架复用现有 runner；前端只需保证重跑后状态正确刷新。

---

## 附录 B · 视觉规范 v3（浅色现代风，2026-09-01 晚定稿）

> 用户反馈 v2「太黑、风格老气」。**v3 起改为浅色主题**，视觉参考为同目录 `_mockup_v3.html`，附录 A 的调色板与「深色硬约束」作废；功能、路由、字段、组件结构仍全部不变。

### B.1 调色板（替换 A.1，浅色分层：浅灰底 + 白卡片 + 柔和状态色）

```css
:root{
  --bg:#f2f4f9; --panel:#ffffff; --panel-2:#f6f8fc; --raised:#eef1f8;
  --border:#e4e8f0; --border-strong:#d3d9e6;
  --text:#1d2433; --text-dim:#5b6579; --text-faint:#98a1b3;
  --ok:#16a34a;  --ok-bg:#e7f6ec;
  --warn:#d97706;--warn-bg:#fdf1e0;
  --bad:#e11d48; --bad-bg:#fde8ec;
  --muted:#8b94a7;--muted-bg:#eef0f4;
  --manual:#7c6cf0;--manual-bg:#efedfd;
  --accent:#4f6ef7;--accent-dim:#3b57d9;--accent-bg:#eef1fe;
  --r:10px; --r-sm:7px;
  --shadow:0 1px 2px rgba(20,30,60,.05),0 4px 14px rgba(20,30,60,.05);
}
```

**风格要点**：白卡片 + 10px 圆角 + 极轻投影 + 状态色一律「浅底深字」（徽章、图标座）；logo 用蓝紫渐变方块；**终端保留深色**（#10141d，现代 IDE 惯例），终端配色沿用 v2 分级方案。

### B.2 新增两个顶栏一级入口（用户点名）

| 入口 | 面板内容 | 数据源 |
|---|---|---|
| `Baseline 对比` | 右侧滑出面板：行业基线 / 同学基线分段切换（seg 控件），模块 ×「本产品 / 基线 / 差异」对照表，▲超出绿、▼落后红、= 持平灰；底部「导出对比 CSV」 | 现有 `GET /api/industry`、`GET /api/classmate_baseline`，差异前端即时计算 |
| `总结报告` | 右侧滑出面板：四张结论卡（总 case / 覆盖率 / 较上轮新增 / 较上轮退化）+ 结论摘要（采集强项 / 关注项 / 手动能力）+「导出报告 Markdown」 | `/api/overview` 聚合 + `case_result_map`；「较上轮」对比重跑前快照 |

三个面板（详情抽屉 / 手册 / Baseline / 报告）共用同一 `.slide` 滑出骨架 + 遮罩，Esc 关闭，互斥打开。

### B.3 硬约束更新

- ~~深色主题~~ → **浅色主题**；状态色语义不变（绿=采集/琥珀=疑问/红=缺失/灰=待测/紫=手动），仅改为浅底深字适配。
- 依然：无框架无构建、全内联 SVG 图标不用 emoji、等宽终端/Case ID、表格紧凑（行高 ≤40px）、一屏 ≥20 case。
- 允许 10px 内圆角 + 极轻投影（现代风需要），禁止营销渐变大图。

---

## 附录 C：v3 落地实现 + 两项增量（2026-09-01，已实现）

> 状态：**已实现并联调通过**。实现文件：`index.html`（壳）/ `style.css` / `app.js`；
> 后端增量：`server.py` 新增 4 个只读/动作路由（不动现有路由）；
> 附带修复：`automation/core/status.py` 的 RUNS 路径 P0（曾指向空的 `automation/runs/`，
> 导致 `/api/overview` 全读不到状态 → 改指 `results/runs/`，与 server.py 对齐）。

### C.1 增量一：样本变体（多用例确认能力，占位先行）

- 详情抽屉第 5 个 tab「变体」：占位说明页（命名约定 `<模块>-<能力>-<序号>`、并集判定口径、数据源预留）。
- 后端 `GET /api/case/<id>/variants` 已实现，当前返回 `{case_id, variants: []}`。
- 矩阵行展开子行（▸）与并集判定渲染逻辑已在 app.js 中就绪，variants 返回非空即自动启用（Phase 3 无需再改前端骨架）。

### C.2 增量二：终端加大 + 可调

- 默认高度 210px → **320px**（CSS 变量 `--term-h`）。
- 顶部 4px 拖拽条（hover 高亮），拖动范围 **120px ~ 70vh**，高度持久化到 localStorage（`edr_term_h`）。
- 「最大化」按钮：终端铺满内容区，再点或按 Esc 还原；最大化时禁用折叠与拖拽。
- 「清空」「停止」保留；任务运行时终端点绿点呼吸，空闲转灰。

### C.3 后端新增路由（全部增量，现有契约不动）

| 路由 | 说明 |
|---|---|
| `GET /api/case/<id>/variants` | 变体占位（C.1） |
| `GET /api/sysmon_evidence` | 整份 Sysmon L2 证据（矩阵 SYSMON 列 + 详情 Sysmon tab 共用） |
| `GET /api/manual` | 读 `docs/USER_MANUAL.md`，手册面板渲染 |
| `POST /api/module/<m>/match` | 匹配本模块（`run_all.py match --module`，CLI 本已支持） |

### C.4 面板数据源映射（实现口径）

- **行业基线 tab**：`industry_baseline.json` 的 categories 全量参照矩阵（行为 × Sysmon/MDE/CrowdStrike/SentinelOne，Yes/Partial/No 徽章）。
- **同学基线 tab**：`classmate_baseline.json` 逐 case 对照（本产品 badge vs 同学 有/?/无，一致/差异标记）。
- **总结报告**：四卡（总 case/覆盖率/较上轮新增/较上轮退化）——「较上轮」对比 localStorage 快照（`edr_report_snapshot`，「存为本轮基线」按钮显式打快照，**历史不迁后端**）；自动摘要（全采集模块 / 关注项 / 手动模块）；「导出报告 Markdown」前端生成下载。

### C.5 联调记录

- `status.py` 修复后 `/api/overview`：16 模块 53 case，collected 26 / not_collected 27，run_state 真实（matched/delivered）。
- 新增端点全部 200；app.js 过 `node --check`；静态资源（style.css/app.js）经 Flask static_folder 正常服务。
- 已知留白：变体数据源未接入（占位）；行业基线为行为级参照矩阵（未做模块级聚合差异，需行为中英映射表后再加）。

## 十、变体分组（能力级并集判定）

新增样本是「变体」——同一个能力（capability）的多个触发方式，命名 <模块>-<能力>-<序号>。
现有变体：PROC-IMAGE-LOAD / PROC-TAMPER / FILE-CREATE / TASK-CREATE / REG-CREATE（各 2 个变体，-001/-002）。

前端需要：

1. **按能力分组**：case_id 前缀相同（去掉末尾 -<序号>）的 case 识别为同一能力的多个变体。

2. **矩阵显示**：一个能力一行（默认折叠，行首 ▸ 展开箭头），展开显示各变体子行；或能力行加「N 变体」徽章，点击展开。

3. **能力级并集判定**：
   - 任一变体「采集到」→ 能力 verdict「对」
   - 部分变体采到 →「疑问」（有偏向，仅部分触发方式命中）
   - 全部变体没采到 →「错」（能力缺失/盲区）

4. **详情抽屉**：加「变体 tab」，列出该能力所有变体 case + 各自跑测/判定状态，对照不同触发方式。

5. **数据源**：现有 GET /api/overview 的 case 列表（case_id/module/binary/run_state），前端按 case_id 前缀分组即可，无需后端改动。
