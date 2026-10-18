# MileSprint · v0.0.1（设备管理能力）

- 状态：产品边界与关键规则已确认，尚未实现；技术方案与阶段实施见计划。
- Milestone：[v0.0.1](https://github.com/ceasarXuu/MileSprint/milestone/1)。
- 目标：围绕本机 doumen 的现有 Apple 模拟器和 USB 真机，提供无界面的设备登记、状态监测、数据策略与占用管理。
- 名称：产品与服务始终为 MileSprint，设备管理是本版暴露的能力，不是另一个产品。
- 已确认边界：只做约束性管理，不代理实际设备操作；设备设置保护上限，App 数据可单独授权。
- 已确认规则：租约到期自动释放；App 三档默认使用保护最少的 resettable；Agent 可调用全部管理入口。需要保护现场时显式收紧策略或维持租约。

## 文档

1. [产品需求与已确认决策](device-manager/prd.md)：版本边界、使用流程、策略和验收标准。
2. [技术设计与实施计划](device-manager/plan.md)：最小运行形态、数据模型、工具接口、分阶段工作。
3. [本机与 doumen 调查依据](device-manager/evidence.md)：只读观察、现有流程缺口和官方技术资料。
4. [工程接口细化](device-manager/contracts.md)：身份、观察、工具输入输出、错误与租约事务草案。

实施前复核已完成：两台 USB 真机和 DeviceHub 只读探测、官方 MCP 双客户端/CLI 小样、SQLite 租约并发小样均有证据；这些不等于正式实现或 doumen 产品测试。

v0.0.0 保留为完整产品的早期概念记录。本版本只切出设备管理器，不继承其调度器、执行控制器或资源优化算法的实施范围。
