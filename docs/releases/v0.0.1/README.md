# MileSprint · v0.0.1 设备管理器

- 状态：设计草案，尚未实现。
- Milestone：[v0.0.1](https://github.com/ceasarXuu/MileSprint/milestone/1)。
- 目标：围绕本机 doumen 的现有 Apple 模拟器和 USB 真机，提供无界面的设备登记、状态监测、数据策略与占用管理。
- 已确认边界：只做约束性管理，不代理实际设备操作；设备设置保护上限，App 数据可单独授权。

## 文档

1. [产品需求与已确认决策](device-manager/prd.md)：版本边界、使用流程、策略和验收草案。
2. [技术设计与实施计划](device-manager/plan.md)：最小运行形态、数据模型、工具接口、分阶段工作。
3. [本机与 doumen 调查依据](device-manager/evidence.md)：只读观察、现有流程缺口和官方技术资料。

v0.0.0 保留为完整产品的早期概念记录。本版本只切出设备管理器，不继承其调度器、执行控制器或资源优化算法的实施范围。
