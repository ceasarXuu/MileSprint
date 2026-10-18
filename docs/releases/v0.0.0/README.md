# MileSprint · v0.0.0 初始概念讨论

> **文档性质**：设计讨论记录 / Concept Draft  
> **日期**：2026-10-18  
> **实现状态**：未开始实现；无可运行产物；未进行性能基准测试  
> **名称**：MileSprint，暂定  
> **版本目录说明**：`v0.0.0` 只是为讨论材料建立的归档编号，并非已发布的软件版本。

## 核心判断

现有许多多 Agent 编排工具主要解决 **Issue 如何依赖、如何派发、如何自动推进**。这能减轻人工管理工作，但不一定能显著缩短一个版本的真实交付时间。对于单机项目，Agent 执行能力往往比**设备、构建环境、共享代码状态、系统负载、人工验收**更容易扩容。

MileSprint 讨论的核心不是“让 Ready Issue 尽量快地被派发”，而是：

> **在任务和依赖关系不断被发现、耗时估计持续变化、开发资源有限的条件下，动态选择 Action 与资源分配，以最小化 Milestone 最终验收通过所需的实际时间。**

## 三块核心

| 模块 | 回答的问题 | 主要输出 |
| --- | --- | --- |
| Issue Scheduler | 当前还有什么事要做，哪些能够推进，什么仍需调查或澄清？ | 动态 Issue/Action Graph 与候选行动 |
| Resource Manager | 现有环境能做什么，什么已占用，怎样安全并发？ | Capability Registry、资源快照、预约、租约 |
| Scheduling Optimizer | 先做什么，用哪种资源组合，是否需要等待或重排，才能最快交付版本？ | 资源可行的短期执行计划、重排决策 |

Execution Controller、持久事件存储与 Worker Adapter 是支撑以上三块的运行机制，**不是第四个独立的决策中枢**。

## 文档目录

1. [01-product-definition.md](01-product-definition.md) — 目标、范围、非目标、成功标准。
2. [02-issue-model.md](02-issue-model.md) — Issue 状态机、Action、关系图、证据与动态发现。
3. [03-resource-registry.md](03-resource-registry.md) — 资源注册、能力与安全分级、排他锁、租约及避免死锁。
4. [04-scheduling-optimizer.md](04-scheduling-optimizer.md) — 最短交付时间、估时校准、RCPSP、滚动优化及稳定性。
5. [05-milestone-verification.md](05-milestone-verification.md) — R1/R2/... 集成回流、人工验收及测试证据失效。
6. [06-runtime-interfaces.md](06-runtime-interfaces.md) — 模块边界、事件、接口与载体候选。
7. [07-hypotheses-and-experiments.md](07-hypotheses-and-experiments.md) — 待验证假设、模拟实验与竞品对照。
8. [08-decisions-and-open-questions.md](08-decisions-and-open-questions.md) — 已收敛原则、暂定方案和待定事项。

## 当前共识与保留问题

**已收敛的设计原则**：单机单项目；Milestone 是冲刺单位；Issue 是最小逻辑事务、Action 是最小可调度工作；Agent 主动发现关系并推进状态；开发资源显式注册与安全分配；Optimizer 持续根据实际耗时与状态变化调整排程；所有 Issue 完成后进入集成验证，发现问题回流，最终人工验收。

**未定**：最终软件形态（Skill/MCP/独立 Runtime）；具体调度求解算法；资源分级体系的默认规则；事件数据结构；是否复用现有开源执行引擎；性能收益的实测范围。

**避免误读**：本文档中的数字、示例 YAML、算法和 Mermaid 图都属于设计示意，不是产品已提供的能力。
