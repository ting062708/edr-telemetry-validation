# EDR 遥测验证工程 · 架构评审

> 评审时间：2026-09-01  
> 评审范围：`E:\EDR` 全量（EDRTelemetry / EDRTest / frontend / log）  
> 依据：实测目录树 + 代码入口 + 配置与文档交叉比对（非仅看文档）

---

## 一、先说结论

**核心架构是对的，不用推倒重来。** `config / core / runner / tools / docs / runs / results` 的分层很干净，  
`docs/` 的「总纲 → 行为链 → 规范 → 存档 → 实例」五层递进设计是这套工程最有价值的部分，  
「换产品只替换 `ioa/` 实例层」的抽象也站得住。

**但有 5 处需要调整**，按严重度排序：

| # | 问题                           | 严重度    | 影响                                      |
| - | ---------------------------- | ------ | --------------------------------------- |
| 1 | **整个 `E:\EDR` 没有 git**       | 🔴 阻断级 | 125MB 产物 + 45 个 case 结论 + 30 份映射，一次误删全没 |
| 2 | **日志目录三处并存，代码按优先级盲探测**       | 🔴 高   | 拿到旧/错的日志也不会报错，结论 silently 出错            |
| 3 | **`automation/` 根目录被临时文件污染** | 🟠 中   | 20+ 陈旧 log、12.9MB 中间产物、3 个孤儿脚本          |
| 4 | **文档与代码已漂移**                 | 🟠 中   | AI 按文档干活会踩坑（PROJECT_LAYOUT 已过期 8 天）     |
| 5 | **模块命名三套标准不一致**              | 🟡 低   | 源码目录 / 编译产物 / case 定义 各说各话              |

---

## 二、实测现状（数字来自今天扫描，不是文档抄的）

### 2.1 规模

```
E:\EDR\EDRTelemetry    样本 C# 源码    22 个 csproj / 18 个 slnx / 20 个 zip
E:\EDR\EDRTest\automation
  ├─ config/   260 KB   45 个 case / 30 份映射 / 16 个配置文件
  ├─ core/     236 KB   6 个模块，2889 行
  ├─ runner/            1 个 CLI，1173 行
  ├─ tools/    52 KB    5 个脚本
  ├─ docs/     205 KB   7 层，23 个文件
  ├─ runs/     683 MB   15 个模块 / 43 个 case 产物
  ├─ results/  2.7 MB
  └─ log/      78 MB    含一个 47MB 的全量导出
E:\EDR\frontend        Flask 后端 18KB + index/about/summary 三个页面
```

### 2.2 代码入口（三个，职责有重叠）

| 入口                           | 行数   | 角色                        | 子命令                                          |
| ---------------------------- | ---- | ------------------------- | -------------------------------------------- |
| `frontend/server.py`         | ~500 | **实际主入口**（Flask，带任务队列）    | HTTP API，内部调下面两个                             |
| `runner/telemetry_runner.py` | 1173 | 单 case CLI                | run / deliver / match / inspect-csv          |
| `run_all.py`                 | 486  | 批量编排（subprocess 调 runner） | deliver / match / status / matrix / baseline |

> `deliver` 和 `match` 在 `run_all.py` 与 `telemetry_runner.py` 里各有一套实现。  
> 目前靠 `run_all.py` 转调 runner 还算能跑，但两套参数、两份进度判定，迟早对不上。

### 2.3 数据流（实际路径，来自代码）

```
改样本源码 E:\EDR\EDRTelemetry\<Module>\
   ↓ 编译
样本产物 E:\EDR\EDRTest\samples\<Module>\        ← vm_config.samples_root 指向这里
   ↓ run_all.py deliver / server.py 任务队列
core\deliverer.py → VM 执行 → runs\<Module>\<CASE>\<case>_stdout.txt
   ↓ 人导 IOA 日志
log\ （三处候选，见问题 2）
   ↓ run_all.py match
core\matcher + normalizer + stdout_parser → verdict
   ↓
runs\<Module>\<CASE>\match_result.json + normalized_events.json
   ↓
config\case_result_map.json（人定稿）→ frontend 展示
```

---

## 三、问题详解与建议

### 🔴 问题 1：没有版本控制（最该先做的一件事）

`E:\EDR` 不是 git 仓库。当前靠 `_bak_20260822_211601` 这种目录后缀和 `_protocol_v2`、`_final` 做版本管理。  
22 个 csproj 里至少 6 个是同一个样本的重复版本。

**建议**：先 `git init`，配 `.gitignore` 把产物排除，**只管源码 + 配置 + 文档**。

```gitignore
runs/**/normalized_events.json     # 单文件最大可达 MB 级，运行时可再生成
runs/**/*.evtx
log/**/*.json
log/**/*.zip
**/__pycache__/
**/.vs/
*.log
samples/**/*.exe                    # 编译产物不入仓
EDRTelemetry/**/*.zip
EDRTelemetry/**/_bak_*/
```

> 关键：`config/case_result_map.json`、`config/mappings/`、`config/test_cases.json`、`docs/`、`core/`、`runner/`、`tools/`、`EDRTelemetry/**/*.cs` 必须全部入仓——这些是你的结论资产，丢了无法重建。

---

### 🔴 问题 2：日志目录三处并存 + 盲探测（最容易出错的一处）

`telemetry_runner.py:394-396` 和 `frontend/server.py:182-183` 都写着同一个探测链：

```python
_ROOT / 'log',              # E:\EDR\EDRTest\automation\log   78 MB
_ROOT.parent / 'log',       # E:\EDR\EDRTest\log              多份 logs_export_*.json/zip
_ROOT.parent.parent / 'log' # E:\EDR\log                      只有空的 BIT\
```

**风险**：三处都有同名文件时，取谁全看遍历顺序；取到 8 月 25 日的旧导出，匹配结果会悄悄变成「疑问」或「错」，  
**不会报错，只会给你一个看起来正常的错误结论**。这是验证类工程最危险的失败模式。

**建议**：

1. 收敛成唯一落点 `E:\EDRTest\automation\log\<Module>\json\`（`PROJECT_LAYOUT.md` 里本来就是这么写的，只是没执行）
2. 探测链改成**只认这一个目录**；找不到就明确报错，不静默回退
3. 47MB 的 `full_export_2026-08-25.json` 和根目录 `新建文件夹\` 移入 `_cold/`
4. `E:\EDR\log\BIT`（空）直接删掉

---

### 🟠 问题 3：`automation/` 根目录被临时文件污染

根目录现在躺着 35 个条目，其中大半是垃圾：

| 类型     | 具体文件                                                                                                                     | 处置                                               |
| ------ | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ |
| 陈旧日志   | `file_deliver{,_v2,_v3}_*.log`、`file_match{,2}_*.log`、`acct_batch_*.log`、`fdel_run3_*.log`、`del_norestore_*.log` 等 20+ 个 | 移入 `automation/_tmp/`                            |
| 孤儿中间产物 | `normalized_events.json`（12.9MB）、`match_result.json`、`run_metadata.json`                                                 | 应在 `runs/<Module>/<CASE>/` 下，根目录这三份是误落           |
| 孤儿脚本   | `_verify_account.py`、`generate_report.py`、`fix_report.txt`、`file_rerun_batch.ps1`、`run_deliver.bat`                      | `generate_report.py` 看着有用，进 `tools/`；其余进 `_tmp/` |
| 巨型脚本   | `TencentEdrCloudExportDebug_modified.py`（38KB）+ `.zip`                                                                   | 这是**导出工具**，不该躺在根目录。进 `tools/export/`             |
| 空/小目录  | `file_rerun_logs/`、`run_logs/`                                                                                           | 进 `_tmp/`                                        |

**建议**：新增 `automation/_tmp/` 统一收容（前缀 `_` 表示不参与任何流程），确认跑通两周后再删。

---

### 🟠 问题 4：文档与代码已漂移

`docs/` 7 层结构本身设计得很好，但内容是 8 月 27 日重组的，`PROJECT_LAYOUT.md` 停留在 8 月 24 日，已经对不上：

| 位置                     | 文档写的                                               | 实测                                             |
| ---------------------- | -------------------------------------------------- | ---------------------------------------------- |
| `PROJECT_LAYOUT.md` §二 | case 定义 **36** 个                                   | **45** 个                                       |
| `PROJECT_LAYOUT.md` §二 | `docs/` 是平的，`E2E_VALIDATION_METHOD.md` 在 `docs/` 根 | 已移入 `docs/spec/`                               |
| `PROJECT_LAYOUT.md` §二 | 未提 `samples/` 目录                                   | 实际在 `EDRTest\samples\`，且是 VM 投递源               |
| `docs/README.md` 索引    | `ioa/` 列了 5 个文件                                    | 实际 6 个，多出 `EDR_IOA_BASELINE_V2.md` 未登记         |
| `PROJECT_LAYOUT.md` §四 | 自认「README.md 内容过时」                                 | 仍未修（`automation/README.md`，8/20 距今 12 天）       |
| `PROJECT_LAYOUT.md` §二 | `tools/` 列 3 个脚本                                   | 实际 5 个（多 `parse_evtx.py`、`sysmon_evidence.py`） |

另外 `config/` 里混进了非配置资产：

- `谢爱莲_baseline.csv`（含人名的文件）
- `classmate_baseline.json`、`comparison_classmate_20260823.md`（横向对比资料）
- `capability_rules.json` + `capability_rules_v2.json`（同文件两版本并存）

**建议**：

1. 重写 `PROJECT_LAYOUT.md`，数字全部以 `config/test_cases.json` 实测为准
2. `config/` 里非运行时读的文件（人名 baseline、同学对比、v2 规则）移到 `results/comparison/`
3. `capability_rules.json` 与 `_v2` 二选一，确认 server.py 读的是哪个后再删另一个
4. `automation/README.md` 重写为 30 秒上手：怎么装依赖、怎么跑一个 case、日志放哪

---

### 🟡 问题 5：模块命名三套标准不一致

| 源码 `EDRTelemetry\`            | 产物 `samples\` | case 定义 `test_cases.json` | 一致?          |
| ----------------------------- | ------------- | ------------------------- | ------------ |
| `Net`                         | `Network`     | `Network`                 | ❌            |
| `process`（小写）                 | `Process`     | `Process`                 | ❌            |
| `Other\GroupPolicyModifyTest` | `GPO`         | `GPO`                     | ❌ 三重不一致      |
| `Other`                       | `Other`       | （无此模块）                    | ⚠️ 悬空        |
| —                             | `Support`     | （无此模块）                    | ⚠️ 支撑件，非行为模块 |

Windows 文件系统大小写不敏感，但 **Python 字典 key 是敏感的**——`runs/Process/` 和 `mappings/process/` 一旦在代码里做 key 比对就会 miss。

**建议**：以 `test_cases.json` 的 15 个模块名为唯一标准，统一改名：  
`Net → Network`、`process → Process`、`Other → GPO`。`Support` 和 `Other\GroupPolicyModifyTest` 明确标注为「支撑件，非行为模块」。

---

## 四、建议的目标结构（最小改动版）

不动 `EDRTest` 这个名字（改动成本大、收益低），只做收敛：

现状我已经摸透了。问题很明确，我给你一版完整的重构方案，你确认后我再动手（涉及删除，我会把"删什么"单独列清楚给你点头）  
。

一、现在的核心问题

1. 样本源码一模块多副本：EDRTelemetry/File 里同时有     
   FileLifecycleTest_frozen_protocol、\_modified、\_protocol_v2、\_bak_20260822_211601 三个版本 + 三个 .zip；Registry     
   也有 Frozen_Candidate_v1.0.0、frozen、special、.zip。这是最乱的地方。
2. automation 目录是垃圾场：run_all.py、generate_report.py 这些正经脚本，和几十个     
   *.log、*.zip、\_verify_account.py、TencentEdrCloudExportDebug_modified.py 临时脚本混在一起。
3. docs 位置混乱：真正的文档在 EDRTest/automation/docs/，而 EDRTest/docs/ 是个空目录。
4. 样本拆成两处：源码在 EDRTelemetry/，编译产物在 EDRTest/samples/，职责不清。
5. config 冗余：case_result_map 同时有 .json/.txt/.xls 三份，还有 archive/、capability_rules.json + \_v2.json 等。

二、目标架构（GitHub-ready + 面试好讲）

EDR/                                  ← repo 根  
├── README.md                         # 项目是什么 / 架构 / 怎么跑 / 能力矩阵  
├── .gitignore                        # 忽略 logs、*.zip、bin、obj、.vs、**pycache**、*.log  
│  
├── docs/                             # 全部文档集中（.md）  
│   ├── README.md                     #   文档导航  
│   ├── AI_ENGINE.md / PROJECT_LAYOUT.md  
│   ├── chain/                        #   ①样本构建 ②跑样本 ③找映射 ④结论  
│   ├── spec/                         #   stdout协议 / 映射规范 / 端到端方法  
│   ├── ioa/                          #   模块结论 / 行为台账 / baseline  
│   ├── ai/                           #   AI 映射方法论  
│   ├── handoff/                      #   交接文档  
│   └── archive/                      #   历史决策存档  
│  
├── automation/                       # 自动化工具链（Python，只留代码）  
│   ├── README.md + requirements.txt  
│   ├── run_all.py / generate_report.py  
│   ├── runner/   core/   tools/      # 脚本按职责分  
│   └── config/                       # test_cases / case_result_map / 字段映射 / baseline  
│  
├── samples/                          # 测试样本源码，按能力划分（一模块一份定稿）  
│   ├── README.md                     #   样本清单 + 构建说明  
│   ├── process/ registry/ file/ account/ driver/  
│   ├── network/ hash/ scheduled_task/ service/  
│   └── pipe/ wmi/ powershell/ device/ bit/ other/  
│  
├── frontend/                         # server.py + summary/index/about.html  
├── results/                          # 能力矩阵 / 映射产物 / 报告（可提交）  
├── logs/                             # 运行日志（.gitignore，只留最近几个）  
└── tools/                            # 第三方工具（Sysmon）

三、具体动作（分两类）

A. 移动/重组（可逆，只是归位）

- EDRTest/automation/docs/* → docs/
- EDRTest/automation/{runner,core,tools,config} → automation/
- run_all.py、generate_report.py → automation/
- EDRTelemetry/<模块>/*\_定稿版 → samples/<模块>/
- frontend/ 原样保留
- EDRTest/samples（编译产物）→ 单独放 build/ 并 .gitignore（不上传二进制）

B. 删除/清理（不可逆，需你点头）

- 各模块的 *bak*、*_modified、*\_protocol_v2、*\_Frozen_Candidate*、frozen、special    
  等冗余副本（每个模块只留一份最终定稿）
- 所有 *.zip（源码包 + 已解压的重复）
- automation/ 里散落的    
  *.log、file_rerun_logs、run_logs、\_verify_account.py、file_rerun_batch.ps1、TencentEdrCloudExportDebug_modified.py    
  等临时文件
- 空的 EDRTest/docs/ 目录
- config/ 里 .xls、.txt、archive/、capability_rules.json（保留 v2）等冗余
- .workbuddy/、**pycache**、.vs、bin/obj（构建缓存）

四、需要你拍板 3 个点

1. File 模块留哪个定稿？ 你现在有 frozen_protocol / modified / protocol_v2     
   三个，我要留哪一个？（其余模块我默认留"最新定稿"那个）
2. 编译产物要不要进 GitHub？ 我建议 .gitignore 掉 build/（二进制不进库），只传源码 + 文档 + 脚本。
3. 日志保留口径：logs/ 只留最近 3 个，还是全删（反正 .gitignore 了，本地留多少随意）？

---

你先回这 3 个点（尤其 File 留哪个），或者直接说"按你的默认来"。确认后我就开始动手重构——我会先做 A  
类移动、再列一份最终删除清单让你二次确认再删 B 类，稳妥起见不一把梭。你觉得这个

---

## 五、落地顺序（按「先止血、再清理、最后改名」）

**第 1 步 · 止血（30 分钟，零风险）**

1. `git init` + 写 `.gitignore` + 首次提交
2. 确认 `E:\EDR\log\BIT` 是空的 → 删除
3. 备份 `config/` 到 `E:\EDR\_backup_20260901\`

**第 2 步 · 收敛日志（1 小时）**  
4\. 三处 log 合并到 `automation\log\`，大文件移入 `automation\log\_cold\`  
5\. 改 `telemetry_runner.py:394-396` 与 `server.py:182-183` 的 `_log_roots()`，只留一个路径，找不到就报错  
6\. 跑 1 个已定稿的 case（如 `FILE-CREATE-001`）验证 verdict 没变

**第 3 步 · 清理根目录（1 小时）**  
7\. 建 `automation\_tmp\`，把 20+ log、3 个孤儿脚本、`file_rerun_logs/`、`run_logs/` 移进去  
8\. 根目录的 `normalized_events.json`/`match_result.json`/`run_metadata.json` 移进对应 `runs/` 目录（确认 case_id 后）  
9\. `TencentEdrCloudExportDebug_modified.py` → `tools\export\`  
10\. 再跑一遍 `FILE-CREATE-001`，确认没破坏

**第 4 步 · 文档对齐（2 小时）**  
11\. 重写 `PROJECT_LAYOUT.md`（以实测数字为准）  
12\. 补 `docs/README.md` 索引：加 `EDR_IOA_BASELINE_V2.md`、`tools/` 两个新脚本  
13\. 重写 `automation/README.md` 为快速上手  
14\. `config/` 里对比类文件 → `results/comparison/`

**第 5 步 · 统一命名（按需，风险最低但影响面广）**  
15\. `Net→Network`、`process→Process`、`Other→GPO`  
16\. 全仓 grep 一遍旧名，重点查 `test_cases.json`、`vm_config.json`、`config/mappings/`

---

## 六、暂时别动的

- **`core/` 六个模块**：分层干净、职责单一，是本工程写得最好的部分，别重构
- **`docs/` 七层结构**：抽象层次是对的，只是内容需要刷新，不是结构问题
- **`frontend/server.py` 的任务队列设计**：单 VM 串行执行这个约束踩得很准，别改
- **`run_all.py` 与 `runner/` 的合并**：现在能跑，优先级排在最后，等前四步做完再说

---

## 附：一句话总结

> 骨架不用动，**先 `git init`**，再把日志从三处收成一处，然后把 `automation/` 根目录扫干净——  
> 这三件事做完，这套工程的可信度会上一个台阶。文档刷新和命名统一可以慢慢来。

---

# 附录 A：对上面这版重构方案的评审

> 评审对象：用户 2026-09-01 提出的重构方案（已贴在本文档第四节）

## A.0 总体判断

**方向认同，可以执行。** 拍平 `EDRTest/` 空壳层、docs 集中到根、一模块一份定稿、二进制不进库、
A 类先行 B 类二次确认——这五条都对，尤其是「不一把梭」的节奏控制。

但有 **3 处会真正踩坑**，且方案里未提及；另有 **3 条删除例外** 必须加进 B 类清单。

---

## A.1 坑 1：移动会打断 4 处跨目录硬编码引用（方案完全没提）

移动目录本身不危险，危险的是路径引用。核查结果：

### ✅ 移动后自动跟随，不用改（好消息）

| 位置 | 写法 |
|---|---|
| `core/matcher.py:174` | `os.path.dirname(os.path.abspath(__file__)) / '..' / 'config'` |
| `runner/telemetry_runner.py:149-153` | `Path(__file__).resolve().parent` 系列 |

这些相对自身定位，`automation/` 从 `EDRTest/automation/` 移到根目录后自动生效。

### ❌ 必须手工改（4 处）

| # | 位置 | 现写法 | 改为 |
|---|---|---|---|
| 1 | `frontend/server.py:24` | `_HERE.parent / 'EDRTest' / 'automation'` | `_HERE.parent / 'automation'` |
| 2 | `runner/telemetry_runner.py:262` | `_ROOT.parent.parent / 'EDRTest' / 'samples'` | `_ROOT.parent / 'build'` |
| 3 | `telemetry_runner.py:394-396` | 三处 log 探测链 | 改成单点（见坑 2） |
| 4 | `server.py:182-183` | 三处 log 探测链 | 同上 |

### ⚠️ 特别注意：`vm_config.json` 里有两个 samples 路径，别一起改

```json
"samples_root":       "E:\\EDR\\EDRTest\\samples"   ← 宿主机路径，要改
"guest_samples_root": "C:\\EDRTest\\samples"        ← VM 内的路径！不要跟着改
```

`guest_samples_root` 是样本在**虚拟机里**的挂载位置（`core/deliverer.py:341` 读取）。
宿主机目录改名不影响它，但两者一旦在文档里被混写就会出事。

---

## A.2 坑 2：日志其实没收敛，只是换了个名字

方案里新建了 `logs/`，**但没有说要删 `automation/log/`（78MB）和 `EDRTest/log/`**。
结果是三处变四处，我上一轮标的 P0 问题原样保留。

必须在方案里显式补上：

1. 三处 log 合并为一个落点
2. 探测链改成单点，找不到就**明确报错**，不静默回退
3. 47MB 的 `full_export_2026-08-25.json` 移入 `_cold/`

> 静默回退是验证类工程最危险的失败模式：取到旧导出不会报错，只会悄悄把 verdict 变成「疑问」。

---

## A.3 坑 3：`results/` + `config/case_result_map` 会制造新的重复

方案把 `case_result_map` 留在 `automation/config/`，同时又建 `results/` 存「能力矩阵 / 映射产物 / 报告」。
**这正是方案第五节抱怨的重复，只是换了个位置。**

建议明确二选一：

| 位置 | 角色 | 是否入库 |
|---|---|---|
| `automation/config/case_result_map.json` | **唯一权威源** | ✅ 入库 |
| `results/` | 只放生成物（csv/xls/报告） | ⛔ `.gitignore` + 配生成脚本 |

否则 `.json` / `.csv` / `.xls` 三份漂移会原样重演。

---

## A.4 回答拍板的 3 个点

### 点 1：File 留哪个 → **留 `FileLifecycleTest_frozen_protocol`**（有铁证）

用编译产物 MD5 三方比对：

| 版本 | exe MD5 | 结论 |
|---|---|---|
| `FileLifecycleTest_frozen_protocol` | `156ca9cf54e5ae8e919375026d60a02b` | ✅ 三方一致 |
| `FileLifecycleTest_modified` | `3a18db8235cd56971eff11fb5e18f20d` | ❌ |
| `FileLifecycleTest_protocol_v2` | `3a18db8235cd56971eff11fb5e18f20d` | ❌ 与 `modified` **字节相同** |

三方 = `test_cases.json.sample_md5` / 源码树 `bin/x64/Release/` / `EDRTest/samples/File/`。

**`protocol_v2` 是个陷阱**：名字像更新版本，构建时间（8/21 22:32）却比 `frozen_protocol`（8/24 15:15）早三天，
产物与 `modified` 逐字节相同。按「名字」或「时间戳」选都会选错。

### 点 2：编译产物不进库 → **同意，但要加构建脚本**

否则 clone 下来 `build/` 是空的，跑不起来且没有任何报错提示。补一个 `samples/build.ps1` 或在 README 写清楚。

### 点 3：日志 → **建议全删，但删之前先验证**

`.gitignore` 之后本地留多少都不影响仓库。删除前先跑一个已定稿 case（推荐 `FILE-CREATE-001`）确认 verdict 不变。

---

## A.5 B 类清单必须加的 3 条例外

### 例外 1：5 个模块的定稿源码不存在，任何副本都别删

用 `test_cases.json` 的 `sample_md5` 反查全部 15 个模块：**10 个命中，5 个未命中**。

| 状态 | 模块 |
|---|---|
| ✅ 已定位 | Account / Device / Driver / File / Hash / Network / Process / Registry / ScheduleTask / Service |
| ❌ 未定位 | **BIT / GPO / PowerShell / WMI / Pipe** |

未定位的 5 个模块细分：

- **BIT / GPO / PowerShell**：源码存在（`BitsJobTest/Program.cs`、`Other/GroupPolicyModifyTest/Program.cs`、
  `PowerShellScriptBlockTest/Program.cs`），但**没有归档的编译产物** → 源码是唯一资产
- **WMI / Pipe**：源码树里有 exe，但 MD5 与 `test_cases` 记录不符
  （WMI `7f72af02…` vs `acf3b288…`；Pipe `04c878a2…` vs `2a20e660…`）→ 部署的二进制是在别处构建的

> **这 5 个模块的二进制无法从现有源码重建，删源码 = 放弃可复现性。**

### 例外 2：有 3 个 zip 没有对应解压目录，删了就没了

`EDRTelemetry/` 下 20 个 zip，17 个有同名目录（可安全删），**3 个没有**：

- `process/EDR_预留模块样本设计.zip` ← 从未解压的设计文档
- `process/EDR_预留模块样本设计_v2.zip` ← 同上
- `process/ImageLoadTest/.../ImageLoadTest.zip`（构建打包，可删）

「所有 `*.zip` 都删」这条需排除前两个。

### 例外 3：`capability_rules.json` 可以删 —— **这条方案是对的**

已核实：`core/matcher.py:176` 只读 `capability_rules_v2.json`，v1 全仓无人引用。**删除安全**。

---

## A.6 建议改一处执行顺序

**在 A 类移动之前先 `git init` + 首次 commit。**

方案的顺序是 A（移动）→ B（删除），但 A 之前没有 commit，一旦移动脚本中途出错就没有回滚点。
先 commit 一次，之后每个移动都是一条可 `git revert` 的 diff。

## A.7 一个命名提醒

方案的 `samples/` 用小写目录（`process/ registry/ file/`），但 `test_cases.json` 里是 `Process/ Registry/ File/`。
这等于把大小写不一致**固化**了，在面试讲解时会成为被追问的点。建议二选一到底：
要么全小写（同时改 `test_cases.json`），要么全 PascalCase。
