# v0.0.1 调查依据

- 日期：2026-10-19（Asia/Shanghai）。
- 方法：本机只读设备枚举、CLI 帮助、宿主机资源查询及 doumen 文档/脚本阅读。
- 未启动、安装、解锁、重启、擦除、创建或删除设备；未运行构建或测试。
- 不提交原始 UDID、CoreDevice identifier、设备个人命名或实际设备授权配置。

## 1. 本机快照

| 观察 | 结果 | 对设计的影响 |
| --- | --- | --- |
| Device Hub 安装位置/标识 | Xcode 内的 DeviceHub.app，bundle 为 com.apple.dt.Devices | 不实现 Device Hub 窗口适配；使用 Xcode 设备 CLI |
| 当前工具链 | Xcode 27.1；simctl JSON、devicectl JSON 可读取 | 实现必须针对实际输出建立解析 fixture，不能照搬旧字段 |
| simctl 设备记录 | 6 台：4 台 runtime 可用且均为 Shutdown；2 台缺少对应 runtime | 关机与不可用分开；不擅自修复/新建 |
| devicectl 设备记录 | 同时包含模拟器和真机；1 台 USB 真机 connected，另 2 台真机仅保留配对记录且未连接 | 两个 provider 要去重；不能把每条 devicectl 记录都当独立 USB 真机 |
| 真机磁盘 | 对当前 USB 真机只读查询 AmountDataAvailable 成功 | 可复用现有轻量采集方式，不需要录制性能轨迹 |
| JSON schema | devicectl jsonVersion=5，旧 hardwareProperties/deviceProperties/connectionProperties 明示废弃，改用 properties | schema 不兼容应报 provider_error；不解析人类表格作为主要协议 |
| 本地开发能力 | Python 3.13、uv、ideviceinfo 已存在；宿主机 32 GiB RAM / 12 个逻辑 CPU | Python + SQLite 有现成运行基础；资源属于共享宿主机，不能逐模拟器累加为独立容量 |
| 历史配置 | 某 doumen worktree 配置的模拟器 ID 不在本次枚举中；文档保留设备也不完全一致 | 配置是期望，实时观察是事实；不能静默选其他设备 |

以上只证明调查时可获得这些元数据，不证明后续连接、安装、运行、USB 传输或性能能力持续可用。未连接真机的系统版本等缓存字段也不能当作现场就绪证据。

## 2. 可复查命令

```sh
xcrun simctl list devices --json
xcrun devicectl list devices --json-output - --omit-deprecated-fields-in-json
xcrun devicectl help device info details
xcrun simctl help list
ideviceinfo -u <已核验的USB设备UDID> -q com.apple.disk_usage -k AmountDataAvailable
```

本次读取 devicectl 的临时 JSON 后归一化统计，不将其原始内容存入公开仓库。设备 detail 命令即使连接失败也可能返回最好可得的旧信息，其 exit code 和元数据存在本身都不等于设备就绪。

## 3. doumen 现有实践

来源为本机 doumen checkout `0ecf92cb1689a29908e23eb699c023b2e7014d6d`，下列文件在读取时没有本地修改。路径相对于该仓库；它们是实施事实与历史规范，不自动升级为 MileSprint 的新产品授权。

| 来源 | 证据 | 设计影响 |
| --- | --- | --- |
| docs/operations/worktree-development-bootstrap.md:276 | worktree.env 只是分配声明，不是跨进程锁 | 需要全机共享的原子占用服务 |
| 同上 :286–306 | 同模拟器同 bundle 混用、真机覆盖污染验收；要求显式 ID、占用人/分支/SHA、不可抢占 | 独占设备，保存上下文和明确 identifiers |
| 同上 :508–515 | 交接记录最后部署信息，停止本任务工作，释放分配 | 释放不能隐含删除 App 或清数据 |
| docs/operations/iphone-simulator-coordinate-click-evidence.md:32–41 | Device Hub 承载模拟器；GUI 窗口枚举不可靠，已有 simctl/XCUITest 路径 | 管理器不依赖视觉、坐标、镜像或窗口控制 |
| docs/operations/real-device-deployment-playbook.md:53–63 | Xcode destination 与 CoreDevice identifier 不同；手填时已有脚本不核验两者同属一机 | typed identifiers 必须带来源并核实映射 |
| 同上 :91–93 | 安装成功但 launch 被 Locked 拒绝 | 不用单一 online/ready 承诺所有操作可行 |
| tools/local_testing/README.md:34–38 | 独立测试 bundle + receipt；普通 App 数据保全；Cloud 测试另有 scope | App 作用域授权；复用原数据门禁，不把设备策略当云数据授权 |
| tools/device_probes/monitor_device_storage.py:57–73 | ideviceinfo 读取可用空间并校验有效整数 | 真机容量只读采集可复用；失败不填 0 |
| 同上 :114–128、219–226 | 测试监控检查新鲜度与进程，现有 1Hz 和容量阈值 | 首版低频库存监测不替代测试期 guard，也不照搬统一阈值 |
| 同上 :145–155 | monitor 锁是 run 目录级，而非设备全局锁 | 不能将既有 monitor lock 视为已解决设备互斥 |
| scripts/install-doumen-on-iphone.sh:193 起 | 现有构建、设备选择、签名与安装链路 | 只提供租约及标识，不重写安装流程 |

## 4. 官方技术依据

- [Apple Xcode command-line tool reference](https://developer.apple.com/documentation/xcode/xcode-command-line-tool-reference)：simctl、devicectl 由完整 Xcode 提供；以本机对应版本的 help 为具体参数依据。
- [MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)：Streamable HTTP 支持独立服务和多个客户端；本地服务应仅监听 localhost，校验 Origin 并配置认证。
- [官方 MCP Python SDK](https://py.sdk.modelcontextprotocol.io/) 与 [运行方式](https://py.sdk.modelcontextprotocol.io/run/)：可提供 stdio 或 Streamable HTTP；实施前锁定当时可用的 SDK 版本，不手写 MCP 协议。

这些依据支持技术可行性，不证明本项目已经实现 MCP 服务、持久租约或故障恢复。
