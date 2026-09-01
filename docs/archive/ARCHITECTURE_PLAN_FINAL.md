# EDR 遥测验证工程 · 最终架构计划（待确认）

> 版本：2026-09-01（终稿，供确认）
> 范围：`E:\EDR` 全量
> 说明：本文是「目标架构 + 命名规范 + 方法论 + 落地顺序」的唯一权威文档。编号带 `✔确认` 表示我建议你直接点头；带 `?拍板` 表示需要你选一个。

---

## 〇、一句话结论

你的两大判断我都认同，且都用实测证据核对过：

1. **「多样本验证一个能力」方向对，且你现有 `test_cases.json` 已经在用这个命名**（`REG-CREATE-001` 这种就是 `<模块>-<能力>-<触发>`），不用推翻重来，只需**把「能力级并集判定」和「Sysmon L2 独立参照」补进方法论，并统一命名大小写**。
2. **重构方案骨架可行**，但 B 类删除清单必须加 3 条例外（5 个模块定稿源码不存在 + 3 个无解压目录的 zip），否则删完没法重建。

---

## 一、方法论确认：多样本验证一个能力 ✔确认

这部分你写得很完整，我逐条确认，并补上与你 docs 里已有雏形的衔接：

### 1.1 核心结论（能力 ≠ 触发方式）

- 一个「能力」有多个「触发方式」。例：「注册表键写入」能力 = Run 键 / RunOnce / RunServices / IFEO 劫持 等多个触发点。
- EDR 采集有**偏向性**：只对部分触发点采得到，其余是盲区。
- 所以判定必须是**能力级并集**，不能指望单样本必中。

### 1.2 命名规范（与你现有 id 一致，固化它）

```
<模块>-<能力>-<触发方式>-<序号>
```

实测：你现有 45 个 id 已是此结构，如：

| 现有 id          | 模块   | 能力     | 触发方式      |
| ---------------- | ------ | -------- | ------------- |
| `REG-CREATE-001` | Registry | Create | Run 键       |
| `REG-CREATE-002` | Registry | Create | RunOnce 键（示例，需补充） |
| `SCHEDTASK-CREATE-001` | ScheduleTask | Create | schtasks+XML |
| `SCHEDTASK-CREATE-002` | ScheduleTask | Create | COM API（示例） |

> **唯一需要改的**：`test_cases.json` 里 `id` 前缀用了短形（`PROC`/`REG`/`NET`），而 `module` 字段用了全称（`Process`/`Registry`/`Network`）。两套并存面试被追问会卡。**建议统一用全称**（见第三节命名规范），id 改成 `PROCESS-CREATE-001`、`REGISTRY-CREATE-001`、`NETWORK-TCP-001`。`mappings/` 目录已用全称小写（`network/` `powershell/`），对得上。

### 1.3 判定规则（能力级并集）

| 情况 | 判定 |
| ---- | ---- |
| 任一触发方式被采到 | ✅ 能力存在（对） |
| 部分被采到 | ⚠️ 采集有偏向（只覆盖部分触发路径） |
| 全部没采到 + Sysmon 证明行为发生了 | ❌ 能力缺失/盲区 |
| 全部没采到 + Sysmon 也没检测到行为 | 🔧 样本问题（样本没触发行为），不是能力问题 |

### 1.4 最关键的一步：Sysmon（L2）独立参照 ✔确认

「IOA 没采到」有两种可能：(a) 样本根本没触发行为；(b) 触发了但 EDR 没采。
**只有用 Sysmon 证明「行为确实发生 + IOA 没采到」，才能归因「采集盲区」。**
这正是把「单个样本没命中」从「能力缺失」误判里解脱出来的钥匙——本质是你 docs 里「行为定义清单 + Sysmon 独立参照」的落地，把它说成「能力级并集判定」就完整了。

---

## 二、目标架构（GitHub-ready + 面试好讲）✔确认

```
EDR/                                    ← repo 根（先 git init，见第五节）
├── README.md                           # 项目是什么 / 架构 / 怎么跑 / 能力矩阵
├── .gitignore                          # 忽略 logs/ *.zip bin obj .vs __pycache__ *.log runs/**/normalized_events.json
│
├── docs/                               # 全部文档集中（.md）
│   ├── README.md                       #   文档导航
│   ├── AI_ENGINE.md / PROJECT_LAYOUT.md
│   ├── chain/                          #   ①样本构建 ②跑样本 ③找映射 ④结论
│   ├── spec/                           #   stdout协议 / 映射规范 / 端到端方法 / Sysmon L2 参照规范(新增)
│   ├── ioa/                            #   模块结论 / 行为台账 / baseline
│   ├── ai/                             #   AI 映射方法论
│   ├── handoff/                        #   交接文档
│   └── archive/                        #   历史决策存档
│
├── automation/                         # 自动化工具链（Python，只留代码）
│   ├── README.md + requirements.txt
│   ├── run_all.py / generate_report.py
│   ├── runner/   core/   tools/        # 脚本按职责分
│   └── config/                         # test_cases / case_result_map / 字段映射 / baseline / capability_rules_v2
│
├── samples/                            # 测试样本源码（一模块一份定稿，源码进 git）
│   ├── README.md                       #   样本清单 + 构建说明 + 触发方式矩阵
│   ├── process/  registry/  file/  account/  driver/
│   ├── network/  hash/  schedule_task/  service/
│   ├── pipe/  wmi/  powershell/  device/  bit/  gpo/
│   └── support/                        # TestLibrary.dll 等共享支撑库（原 samples/Support）
│
├── build/                              # 编译产物（.gitignore，不上传；配构建脚本重建）
├── frontend/                           # server.py + summary/index/about.html（原样保留）
├── results/                            # 能力矩阵 / 映射产物 / 报告（.gitignore 生成物 + 配生成脚本）
├── logs/                               # 运行日志（.gitignore，只留最近 3 个）
└── tools/                              # 第三方工具（Sysmon 等，binary 不进库）
```

---

## 三、命名规范（统一，全仓唯一标准）✔确认

> 一句话：**模块名全仓统一用 PascalCase 全称**，目录用全称小写，id 用全称大写。消灭现有的 `process`/`Net`、`PROC`/`REG` 两套并存的脏东西。

### 3.1 模块标准命名映射（实测现状 → 目标）

| 能力模块 | 源码目录(EDRTelemetry) | samples 目录 | case module 字段 | case id 前缀 | mappings/ |
| -------- | ---------------------- | ------------ | ---------------- | ------------ | --------- |
| Process  | `process` ⚠️(小写)      | `Process`     | `Process`        | `PROC` ⚠️    | —(缺)     |
| Registry | `Registry`             | `Registry`    | `Registry`       | `REG` ⚠️     | registry |
| File     | `File`                 | `File`        | `File`           | `FILE`       | file     |
| Network  | `Net` ⚠️(缩写)          | `Network`     | `Network`        | `NET` ⚠️     | network  |
| Hash     | `Hash`                 | `Hash`        | `Hash`           | `HASH`       | hash     |
| Driver   | `Driver`               | `Driver`      | `Driver`         | `DRIVER`     | driver   |
| ScheduleTask | `ScheduleTask`     | `ScheduleTask` | `ScheduleTask`  | `TASK` ⚠️    | —(缺)     |
| Service  | `Service`              | `Service`     | `Service`        | `SVC` ⚠️     | —(缺)     |
| WMI      | `WMI`                  | `WMI`         | `WMI`            | `WMI`        | wmi      |
| Pipe     | `Pipe`                 | `Pipe`        | `Pipe`           | `PIPE`       | —(缺)     |
| Device   | `Device`               | `Device`      | `Device`         | `DEVICE`     | device   |
| GPO      | `Other` ⚠️(归并)        | `GPO`         | `GPO`            | `GPO`        | gpo      |
| BIT      | `BIT`                  | `BIT`         | `BIT`            | `BIT`        | bit      |
| PowerShell | `PowerShell`         | `PowerShell`  | `PowerShell`     | `PS` ⚠️      | powershell |
| Support  | —                      | `Support`     | —                | —            | —        |

### 3.2 ⚠️ 定稿判定实测（2026-09-01 重扫，修正上一版）

用 `test_cases.json` 的 `sample_md5` 反查源码树 exe，15 模块分为两类：

**✔ 11 个模块可重建**（源码树 exe 与部署二进制 MD5 一致，可放心扁平化/删旧版）：
Account · Device · Driver · File · Hash · Network(Net) · Process(3 个 exe) · Registry · ScheduleTask · Service

**✘ 5 个模块不可重建**（源码树无匹配 MD5，**源码是唯一资产，任何副本都不准删**）：
BIT · GPO · Pipe · PowerShell · WMI

> 注意 Pipe 和 WMI 各有**两份源码**（`_fixed` + `_frozen_protocol_final`），
> 因为二进制 MD5 对不上，**无法判定留哪份** —— 这两个需人工拍板（见第六节）。

### 3.3 三处必须统一的命名修正（实测确认不一致）

1. **源码目录**：`EDRTelemetry/process` → `Process`；`EDRTelemetry/Net` → `Network`；`EDRTelemetry/Other` → `GPO`（Other 里只有 `GroupPolicyModifyTest`，就是 GPO）。
2. **case id 前缀**：统一全称大写。`PROC→PROCESS`、`REG→REGISTRY`、`NET→NETWORK`、`TASK→SCHEDULETASK`、`SVC→SERVICE`、`PS→POWERSHELL`。
3. **samples/Other 空目录**：实测为空，删除；samples/Support 保留为支撑库（不是能力模块，不参与 case）。

> ⚠️ 提醒：`test_cases.json` 的 `module` 字段 + `case id` + `runs/` 产物目录三处联动。改命名必须**同一批改 + 跑一遍验证 verdict 没变**（见第五节顺序）。

---

## 四、重构动作清单

### A. 移动/重组（可逆，只归位）✔确认

| 源 | 目标 | 说明 |
| ---- | ---- | ---- |
| `EDRTest/automation/docs/*` | `docs/` | 合并所有 .md |
| `EDRTest/automation/{runner,core,tools,config}` | `automation/` | 脚本按职责分 |
| `run_all.py`、`generate_report.py` | `automation/` | 入口脚本归位 |
| `EDRTelemetry/<模块>/*定稿*` | `samples/<模块>/` | 源码进 git |
| `EDRTest/samples`（编译产物） | `build/` | .gitignore，配构建脚本重建 |
| `frontend/` | 原样保留 | 只改 4 处硬编码路径 |
| `EDRTest/samples/Support/` | `samples/support/` | 共享支撑库 |

### B. 删除/清理（不可逆，需你点头后再执行）

**B1 冗余副本（每模块只留一份定稿）**
- 各模块 `_bak_*`、`_modified`、`_protocol_v2`、`*_Frozen_Candidate*`、`frozen`、`special` 等旧版本
- 所有 `*.zip`

**B2 automation/ 根目录垃圾**
- 散落 `*.log`、`file_rerun_logs`、`run_logs`
- `_verify_account.py`、`file_rerun_batch.ps1`、`TencentEdrCloudExportDebug_modified.py`
- 根目录误落的 `normalized_events.json`（12.9MB）

**B3 空目录 & 冗余配置**
- 空的 `EDRTest/docs/`
- `config/` 里 `.xls`、`.txt`、`archive/`
- `capability_rules.json`（**v1**，全仓无人引用，安全；保留 v2）

**B4 构建缓存**
- `.workbuddy/`、`__pycache__`、`.vs`、`bin/obj`

**⚠️ B 类清单必须先加 3 条例外（实测，删了无法重建）：**

1. **5 个模块的定稿源码根本不存在，任何副本都别删**：
   - `BIT` / `GPO` / `PowerShell`：源码在，但**从未归档编译产物**，源码是唯一资产
   - `WMI` / `Pipe`：源码树里有 exe，但 **MD5 对不上**部署的二进制（WMI `7f72af02` vs `acf3b288`，Pipe `04c878a2` vs `2a20e660`）
2. **3 个 zip 无对应解压目录**：`process/EDR_预留模块样本设计.zip`、`_v2.zip`（从未解压的设计文档，删了就没）；`ImageLoadTest.zip` 是构建打包，可删。
3. **`samples/Support/` 保留**（不是垃圾，是共享支撑库）。

---

## 五、落地顺序（带回滚点，不一把梭）

1. **`git init` + 首次 commit** ← 先做这个，之后每一步移动/删除都是可 revert 的 diff
2. 写 `.gitignore`（logs/ *.zip bin obj .vs __pycache__ *.log runs/**/normalized_events.json build/ results/生成物）
3. **A 类移动**（git mv，保留历史）
4. **日志三处合一** + 探测链改单点 + **找不到就报错**（不能静默回退）→ 跑 `FILE-CREATE-001` 验证 verdict 没变
5. **B 类删除**：先列最终删除清单给你二次确认 → 再执行（含 3 条例外）
6. 修 4 处跨目录硬编码路径（`frontend/server.py:24`、`telemetry_runner.py:262` + 日志探测链两份；**`vm_config.json` 的 `guest_samples_root=C:\EDRTest\samples` 千万别改**，那是 VM 内路径）
7. **统一命名**（第三节 3 处）+ 同步更新 `test_cases.json`/`runs/` 目录 → 全量跑一遍验证
8. 刷文档（PROJECT_LAYOUT / README / case 数 36→45 / 补 Sysmon L2 参照规范）
9. 生成 `build.sh` / `build.ps1` 构建脚本（否则 clone 下来 build/ 空着跑不起来）

---

## 五·补、对「用户重构方案」的逐条核验（2026-09-01 二轮）

用户在新方案里提出「源码工程名已一致、只需扁平化」——**实测只对一半**。逐条核验：

| 用户方案说法 | 实测结论 |
| ------------ | -------- |
| 工程名其实已一致，只是被版本后缀+嵌套包住 | ⚠️ **仅对 11 个可重建模块成立**。Pipe/WMI 各有 2 份源码且 MD5 都对不上，Process 是 3 个不同 exe（非一个工程） |
| `Service/VirtualDiskMountTest_fixed` 挪回 Device | ❌ **应删除而非挪**。MD5 铁证：Device 的 `_frozen_protocol_final`=`514d1ac2` 三方一致（定稿）；Service 的 `_fixed`=`96fa25fc` 是旧版。删 Service 版 + 散落的 `VirtualDiskMountTest_Program.cs` |
| 命名规则 `<模块>LifecycleTest`/`<模块>ActivityTest`/语义名 | ✔ 基本成立（File/Account/Driver=LifecycleTest，Network=ActivityTest，HashBaselineTool=工具） |
| exe 名不动 | ✔ 同意。exe 名是 `test_cases.json` 的 `program` 锚点 + samples 部署位，改名牵连 MD5，风险大 |
| 7 处宿主路径 | ✔ 文件都存在：server.py / t0_test.py / telemetry_runner.py / audit_hashes.py / vm_config.json。`deliverer.py` 在 `core/`，VM 内不动 |
| 5 模块只保留源码 | ⚠️ **不完整**。Pipe/WMI 各有 2 份，需人工定留哪份；这 5 个的 exe 要留在 samples/（唯一二进制） |

### 本轮修正的三处

1. **VirtualDiskMountTest 是「删」，不是「挪」**（上表）。
2. **Pipe/WMI 定稿需人工拍板**：源码树两份都对不上二进制，MD5 判定失效。
3. **Process 是 3 个 exe**：`ImageLoadTest` + `ProcessLifecycleTest` + `ProcessTarget`，samples/Process 已含这 3 个 + Support，不是「一模块一工程」。

---

## 六、待你拍板（3 个点）

1. **File 定稿**：留 `FileLifecycleTest_frozen_protocol`（MD5 三方一致：`test_cases` + 源码 + samples）。已铁证，建议直接确认。
2. **命名统一范围**：只改源码目录（`process`→`Process`、`Net`→`Network`、`Other`→`GPO`），还是**连 case id 前缀也一起统一成全称**（`PROC→PROCESS` 等）？我建议全改，一次到位。
3. **二进制策略**：源码进 git、`.exe`/`build/` 进 .gitignore + 构建脚本重建。已建议，确认即可。若你想保留固定 MD5 冻结样本，放 **GitHub Releases** 而非代码库。

**新增 1 个待拍板（二轮发现）**：

4. **Pipe / WMI 留哪份源码？** 两份都保留（`_fixed` + `_frozen_protocol_final`），还是各留其一？因 MD5 判定失效，需你按「最近改动 / 命名更像定稿」人工选。**未拍板前这两个模块的 `_fixed` 进删除例外，一律不删。**

**你方案里被我改为「删」的动作**：

- `Service/VirtualDiskMountTest_fixed` → **删**（不是挪回 Device）。Device 已有定稿 `_frozen_protocol_final`。顺带删 `Service/VirtualDiskMountTest_Program.cs` 散落文件。
- `samples/Other/`（空目录）→ 删；GPO 的 exe 在 `samples/GPO/`（已有）。
