# File 模块样本规范审查 + 重跑结果（2026-08-24）

## 一、样本版本链真相

| 版本 | 目标文件 | 内容 | fixture | 结论 |
|---|---|---|---|---|
| frozen_protocol（旧 samples 在用） | `FileLifecycle_Target.exe` | **0 字节空文件** | 自带 | 不符合规范 |
| modified / protocol_v2（源码） | `FileLifecycle_Target.txt` | 64 字节有内容 | modified 自带 / v2 交 runner | 见下 |
| **当前 samples（已切换）** | `FileLifecycle_Target.txt` | 64 字节，行为间隔 10s | 自带 | 已重跑 |

- 旧样本 MD5 `203EBC81...`（.exe 空文件），新样本 MD5 `3A18DB82...`（.txt 全周期版，8/21 编译产物，modified/v2 的 bin 目录里是同一份）
- 新样本是**全周期模式**：每次投递按 CREATE→OPEN→MODIFY→RENAME→DELETE 顺序跑 5 个 phase，各间隔 10s（避开"同毫秒建删"去重）
- 已用 `audit_hashes.py --update` 同步 5 个 case 的 md5/sha256

## 二、EDR 反哺污染清理（已做）

1. FILE-CREATE 的 match 锚点 `"Child.FileTotalWrite": "0"` —— 这是旧空文件样本的 EDR 产物，已删除
2. FILE-DELETE 的 `target_name: "FileLifecycle_Target.exe"` —— 已改 `.txt`
3. 结论：期望值/锚点只允许来自 L1 事实（样本自报），禁止从 EDR 日志反哺

## 三、行业规范审查结论（重要）

**核心发现：`.txt` 是采集盲区，不是好的测试对象。**

- 同学日志观察：IOA 删除事件不覆盖 .txt/.json（只覆盖 DLL/EXE/PS1/JS/SYS/XML/PNG）
- 我方验证：Sysmon（SwiftOnSecurity 配置）的 FileCreate include 规则也不含 .txt，`FileLifecycle_Target.txt` 的创建无 ID11 记录（ID11 只采到了投递复制的 exe）

**行业规范**（Atomic Red Team T1105 载荷落地 / MITRE 评估惯例）：文件操作遥测的测试对象应是**攻击者真实会动的文件类型**——有内容的可执行类文件（.exe/.ps1/.js/.dll），而非空文件或 .txt。

**建议拍板（影响 baseline 判定）**：
- 方案 A（推荐）：目标文件改为**有内容的 .exe**（如 4KB 随机字节/最小 PE stub）——真实攻击场景，主流采集器都会监控，且能验证 size/hash 字段
- 方案 B：维持 .txt（当前状态）——测出的"未采集"结论会同时被"测试对象是采集盲区"削弱说服力
- 无论选哪个，目标文件内容必须**非空**

## 四、重跑结果（已完成）

5 个 case 全部 PASS，产物落盘 `runs/File/<case>/`：
- `<case>_stdout.txt`（自报 64 字节创建/读取/修改 64→133/重命名/删除，时间戳带 +08:00）
- `sysmon_<case>.evtx`（每个 2.1MB）
- `run_metadata.json`

File 模块 `required` 快照策略生效：每个 case 之间恢复 `IOA_Sysmon`（run_all 的 --no-restore-snapshot 被正确覆盖）。

**导出日志时间窗参考**（北京时区）：
- FILE-CREATE：09:55:46~09:56:28
- FILE-OPEN：约 09:57~09:59
- FILE-DELETE / MODIFY / RENAME：见各 stdout 的 [TIME] 字段

## 五、待同学处理 / 待拍板

1. **stdout_parser 全周期适配**：新样本 stdout 含 5 个 [PHASE-BEGIN]，parser 只取 1 个 phase 且告警
   `missing fields: ['pid','hostname','run_id']`。需要：解析全部 phase，match 时每个 case 取自己
    phase 的时间窗（当前全周期模式下 5 个 case 各自时间窗内都含 5 个行为，需按 case 精确锚定）
2. **Sysmon L2 参照盲区**：SwiftOnSecurity 配置需补 FileCreate/FileDelete 对 `C:\EDRTest\*` 的
   include 规则（否则 L2 对文件操作的参照是不完整的）——需更新 IOA_Sysmon 快照内配置并重打快照
3. **目标文件类型拍板**（第三节方案 A/B）
4. run_all deliver 会连 `.bak` 文件一起复制进 guest（无害，但可考虑 samples 只放正式 EXE）
