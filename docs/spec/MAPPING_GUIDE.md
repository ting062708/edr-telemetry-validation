# 行为映射记录说明（MAPPING_GUIDE）

本文档说明 `config/mappings/<module>/<CASE-ID>.json` 映射文件的写法，以及如何用这套工具开展「目标产品 数据采集能力验证」工作。映射文件是匹配判定的核心：它把**样本 stdout 自报的 TARGET 字段**和**目标产品 云端日志实际落点**对应起来。

## 一、文件位置与命名

```
config/mappings/<module>/<CASE-ID>.json
```

- `<module>`：模块目录名，与 test_cases.json 的 module 字段一致（小写形式，如 `file`、`account`、`network`）
- `<CASE-ID>`：用例 ID（如 `FILE-CREATE-001`），**一个 case 一个文件**

## 二、文件格式

```json
{
  "case_id": "FILE-CREATE-001",
  "module": "file",
  "behavior_fields": {
    "Path": "Child.FilePath",
    "FileName": "Child.FileName"
  },
  "observed_fields": [
    "Child.FileCreateOpName",
    "Child.FileName",
    "Child.FilePath",
    "Child.FileSize",
    "Child.NodeName",
    "Child.Type",
    "Child.FileMd5"
  ],
  "known_gap": "可选。目标产品 已知不采集的字段说明（如 File OPEN 事件 FileMd5 恒空）"
}
```

| 键 | 必填 | 含义 |
|---|---|---|
| `case_id` | 是 | 用例 ID |
| `module` | 是 | 模块名 |
| `behavior_fields` | 是 | stdout TARGET 字段名 → 目标产品 日志 dot-path（值验证的核心） |
| `observed_fields` | 否 | 本行为预期出现在 目标产品 事件里的字段清单（`*` 前缀声明的全覆盖校验） |
| `known_gap` | 否 | 已确认 目标产品 采集缺失的字段/说明，写入后可解释 FAIL，不必反复排查 |

**dot-path 规则**：用 `.` 表示 JSON 层级（`Child.FilePath` = `{"Child": {"FilePath": ...}}`）。如果同一字段在日志里有多个候选落点，可用数组：`["Child.Target", "Child.CmdLine"]`（按顺序取第一个命中）。

## 三、怎么写一个新 case 的映射（工作流程）

1. **跑样本**：前端点「执行样本」，VM 里运行样例 EXE，stdout 落盘 `runs/<module>/<case>/<case>_stdout.txt`。stdout 里的 `[TARGET]` 块是行为自报 ground truth，`[RUN-BEGIN]` 给出 RunID 和时间窗。
2. **导出日志**：在 目标产品 控制台导出该模块云端日志 JSON，放到 `log/<模块>/`（或前端「+ → 导入日志」上传）。
3. **初匹配**：点「匹配」，前端自动探测最新日志。查看匹配结果卡的「匹配过程」（折叠面板）里的锚定链（主机 → 时间窗 → 进程 → PID → 操作 → 候选）和 behavior_fields 逐条验证结果。
4. **对字段**：
   - 在导出日志里找到该行为的事件，确认 TARGET 值实际落在哪个 dot-path；
   - 把「stdout 字段名 → 实际 dot-path」写进 `behavior_fields`；
   - 把该事件里的其他字段补进 `observed_fields`。
5. **重匹配**：改完映射后重新点「匹配」，目标 verdict 从 `ERROR_LOG_INPUT`/`NOT_IMPLEMENTED` 变成 `IMPLEMENTED`（前端显示「已实现」）。
6. **写结论**：`IMPLEMENTED` → 用户填 `case_result_map.json`（二元映射）；确认 目标产品 缺失的字段 → 记入 `known_gap`。

## 四、判定状态（verdict）含义

| verdict | 含义 | 通常原因 |
|---|---|---|
| `IMPLEMENTED` | 采集成功（绿） | 锚定命中 + behavior_fields 全部 PASS |
| `PARTIALLY_IMPLEMENTED` | 部分采集 | 锚定命中，部分字段缺失 |
| `NOT_IMPLEMENTED` | 未采集（红） | 日志里找不到该行为事件 |
| `PENDING` | 待判定 | 用户未在 case_result_map.json 下结论 |
| `VIA_WINDOWS_EVENTLOG` | 经 Windows 事件日志采到 | 账户/登录类行为走 WinEventLog 通道 |
| `ERROR_SAMPLE` | 样本问题 | 样本没跑起来 / stdout 解析失败 |
| `ERROR_LOG_INPUT` | 日志输入问题 | 日志时间窗没覆盖 TARGET 窗口、导错模块、日志过旧 |
| `AMBIGUOUS` | 匹配歧义 | 候选 >1，需要行为字段进一步区分 |

## 五、常见坑（来自 STDOUT_SPEC 已踩过的）

1. **时间窗**：TARGET 时间必须落在日志覆盖范围内。日志过旧（前端超过 24h 会警告）时重新导出。
2. **`.\\` 前缀**：stdout 里的路径有时带 `.\\` 前缀（如 `.\\Windows\\Temp`），日志里可能是 `C:\\Windows\\Temp`。值对不上时把前缀差异写进 known_gap 或让 normalizer 处理。
3. **账户类行为**：Account Login/Logoff 走 Windows 事件日志通道（Parent=lsass.exe），匹配时自动切换 WinEventLog 代执行动作，字段落点不同。
4. **PID**：日志若不带 actor_pid，PID 过滤会被跳过（filter_log 会记录 "source carries no actor_pid — filter omitted"）。

## 六、与前端匹配结果的对应关系

前端「匹配结果」代码卡展示的就是这个文件 + 日志的匹配产物：
- **判定** = verdict；**字段 x/y** = behavior_fields 的 PASS 数；
- 命中字段在 stdout 代码区高亮（选中式）；
- 「匹配过程」折叠 = 锚定链 + filter_log + FAIL 字段明细。

改映射文件后**无需重启前后端**，重新点「匹配」即生效。
