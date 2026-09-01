# 重测待办清单（RETEST_BACKLOG）

> 维护规则：**解决后从对应 P 级表删除，移到末尾「已解决归档」**（主表干净 + 留痕，符合"做过的事不删"原则）。
> P 级定义：
> - **P0** = 影响 baseline 结论（导师原则：能采即采）→ 优先处理
> - **P1** = 字段映射相关 → 次级
> - **P2** = IOA 拦截原理相关 → 最后（属 AI 自扩展领域，可延后）

## P0 — 影响 baseline 结论（7 条）

| # | 行为编号 | 行为 | 我 | 同学 | 待办 | 状态 |
|---|---|---|---|---|---|---|
| 1 | FILE-DELETE-001 | 文件删除 | 对 | ❓ | sleep5s 复测（验证建删去重）| ⏳待重测 |
| 2 | REG-MODIFY-001 | 键/值修改 | 疑问 | ✅ | 启动项路径 + RegOldValData/RegValData 比对，重测确认 | ⏳待重测 |
| 3 | FILE-OPEN-001 | 文件打开 | 疑问 | ✅ | JSON 文件重测（TXT 不采）| ⏳待重测 |
| 4 | NET-UDP-001 | UDP 连接 | 疑问 | ✅ | NetBind 监听方式重测（单播不采）| ⏳待重测 |
| 5 | DRIVER-MODIFY-001 | 驱动修改 | 对 | ❌ | 对齐"驱动修改"定义后改判"错"（用户未就绪）| ⏸️暂缓 |
| 6 | NET-URL-001 | URL 访问 | 对 | ❓ | 改判"疑问"（Host 有 / Url 空），无需重测 | 🔧待改判 |
| 7 | TASK-CREATE/MODIFY/DELETE-001 | 计划任务 3 case | 零采集 | ✅需XML / ✅需XML / ❌ | 已用 schtasks+XML 复测仍零采集，待定稿 TASK=错 | ✅已复测零采集 |

## P1 — 字段映射相关（5 条）

| # | 行为编号 | 差异 | 待办 |
|---|---|---|---|
| 1 | NET-TCP-001 | 我记 HttpRequest(DstIp) vs 同学 NetBind(监听) | 核对事件/字段映射 |
| 2 | NET-DOWNLOAD-001 | 我记 Host vs 同学 tcp+新建文件联合判断 | 核对判定方式 |
| 3 | FILE-OPEN-001 | 我找 FileRead vs 同学 FileWriteClose 子事件 | 核对字段映射 |
| 4 | REG-MODIFY-001 | 补充 Child.RegOldValData / Child.RegValData 映射 | 补字段映射 |
| 5 | NET-URL-001 | Child.Url 为空、靠 Host 区分 | 补映射说明 |

## P2 — IOA 拦截原理相关（6 条，AI 自扩展领域）

| # | 主题 | 现象 |
|---|---|---|
| 1 | REG 路径筛选原理 | 启动项路径能采、自定义路径不采 |
| 2 | FILE 文件类型过滤原理 | JSON 能采、TXT 不采 |
| 3 | NET 协议监控点原理 | 监听能采、单播不采 |
| 4 | PROC-IMAGE-LOAD | 有字段但"换了四种方法测不出" |
| 5 | NET-TCP/UDP 稳定性 | "碰巧撞上测试集"，采集不稳定 |
| 6 | PROC-IMAGE-LOAD 时间戳偏移 | 同学(张顺钦)实测 image_load 事件时间戳偏很久（远超正常 15ms），疑似异步上报/轮询采集，待研究采集周期 |

## 已解决归档

（解决后从上方表格删除，移到这里留痕）

