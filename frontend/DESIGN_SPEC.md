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
