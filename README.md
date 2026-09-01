# EDR 数据采集能力验证（EDR Telemetry Validation）

验证终端安全 EDR 产品（腾讯 iOA）对 Windows 各类攻击行为的**遥测数据采集能力**：用一套可复用、可复现的方法，逐项验证 EDR 的 53 项数据采集能力，记录缺失与异常采集问题，并沉淀可复用的自动化测试 baseline。

## 目录结构

```
.
├── docs/          # 全部文档（AI 总纲 / 行为链 / 规范 / IOA 实例 / AI 方法论）
├── automation/    # 自动化工具链（Python）
│   ├── runner/    #   命令行入口（telemetry_runner.py）
│   ├── core/      #   核心逻辑（matcher / normalizer / stdout_parser / verdict / deliverer / status）
│   ├── tools/     #   工具脚本（discover_mapping / audit_hashes / check_mapping ...）
│   └── config/    #   配置（test_cases / case_result_map / 字段映射 / baseline / vm_config）
├── samples/       # 测试样本源码（按能力划分，15 模块）
├── frontend/      # Web 监控前端（Flask server.py + summary/index/about.html）
├── results/       # 测试结果（能力矩阵 / 映射产物 / 运行记录）
├── logs/          # IOA 云端导出日志（gitignore，仅留最近）
└── tools/         # 第三方工具（Sysmon）
```

## 核心流程（行为链四步）

**① 样本构建 → ② 跑样本 → ③ 找映射 → ④ 结论分析**（可循环反哺，非单向）

- 样本：C#/.NET 确定性测试样本，遵循「冻结协议 stdout」+ Migration gate 7 条
- 跑样本：VMware + vmrun 投递执行，Sysmon 作独立参照（L2）
- 找映射：正向值扫描 + 反向剖析交替，生成 behavior_fields + observed_fields
- 结论：三态判定（对/疑问/错）+ 行业对比（Sysmon / MDE / CrowdStrike / SentinelOne）

## 关键成果

- 验证 **53 项采集能力**（45 用例 + 8 预留），产出能力矩阵与三态判定
- 构建 46 个 case 的字段映射（值锚点 + 采集完整性清单 + 已知盲区）
- 沉淀 **AI 辅助映射自扩展方法论**（内核/适配层分离、Sysmon 对照防过拟合，可复用到其他 EDR 产品）

## 快速开始

- 跑测试 / 找映射：见 `automation/README.md`
- 方法论 / 行为链：见 `docs/README.md`
