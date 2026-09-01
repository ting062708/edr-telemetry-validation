# docs 目录结构（分层导航）

> 原则：**越上层越通用，越底层越实例（IOA 专属）**。AI 阅读按层递进：先读总纲 → 再读行为链 → 再查规范 → 遇问题查存档 → 实例细节查 `ioa/`。

```
docs/
├── README.md              ← 本文件（目录索引）
├── AI_ENGINE.md           ← ① 总纲（目标 + 约束 + 提示词 + 行为链总览）
├── PROJECT_LAYOUT.md      ← 项目目录地图（每个目录/文件是干什么的）
├── chain/                 ← ② 行为链（怎么做，4 步）
│   ├── 01_sample_build.md    样本构建
│   ├── 02_run_sample.md      跑样本
│   ├── 03_find_mapping.md    找映射
│   └── 04_conclusion.md      结论分析
├── spec/                  ← ③ 规范层（通用协议/工作流）
│   ├── STDOUT_SPEC.md        stdout 冻结协议 + 补值三原则
│   ├── MAPPING_GUIDE.md      字段映射工作流
│   └── E2E_VALIDATION_METHOD.md  端到端方法 + 判定矩阵 + 匹配流水线
├── archive/               ← ④ 存档层
│   ├── ARCHIVE.md            决策/问题存档（ARC-XXX）
│   └── MAPPING_CHANGELOG.md  映射修改记录（MAP-XXX）
├── ioa/                   ← ⑤ 实例层（IOA 专属，最底层）
│   ├── README.md             实例索引
│   ├── MODULES.md            各模块采集结论
│   ├── BEHAVIOR_LEDGER.md    行为编号台账
│   ├── FILE_SAMPLE_AUDIT.md  File 样本审计
│   └── EDR_TELEMETRY_BASELINE.md  行业基准
├── handoff/               ← ⑥ 交接层
│   ├── BASELINE_HANDOFF_V2.md   baseline 交接
│   ├── FRONTEND_HANDOFF.md      前端接口交接
│   ├── AI_MAPPING_HANDOFF.md    AI 映射交接
│   └── ABOUT.md                 关于页内容
└── ai/                    ← ⑦ AI 工程过程稿
    ├── AI_MAPPING_METHODOLOGY.md  映射方法论
    ├── AI_SUMMARY_SPEC.md         总结规范
    ├── AI_CHAIN_LOG.md            链路台账
    └── RETEST_BACKLOG.md          重测清单
```

## 换目标 EDR 产品时

替换 `ioa/`（实例层）+ `config/` 里的实例数据（`ioa_field_mapping.json` / `test_cases.json` / `case_result_map.json`），上层 `AI_ENGINE.md` / `chain/` / `spec/` 通用不变。
