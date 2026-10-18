# MileSprint v0.0.1 调查依据

- 日期：2026-10-19（Asia/Shanghai）。
- 方法：本机只读设备枚举、CLI 帮助、宿主机资源查询及 doumen 文档/脚本阅读。
- 未启动、安装、解锁、重启、擦除、创建或删除设备；未运行构建或测试。
- 不提交原始 UDID、CoreDevice identifier、设备个人命名或实际设备授权配置。

## 1. 首轮本机快照（两台 USB 复核前）

| 观察 | 结果 | 对设计的影响 |
| --- | --- | --- |
| Device Hub 安装位置/标识 | Xcode 内的 DeviceHub.app，bundle 为 com.apple.dt.Devices | 不实现 Device Hub 窗口适配；使用 Xcode 设备 CLI |
| 当前工具链 | Xcode 27.1；simctl JSON、devicectl JSON 可读取 | 实现必须针对实际输出建立解析 fixture，不能照搬旧字段 |
| simctl 的 CoreSimulator 清单 | 6 条记录：4 条 runtime 可用且均为 Shutdown；另 2 条报告 runtime 不可用 | 此计数不包含 USB 真机，也不是 DeviceHub 展示设备的分类结论；具体条目见第 7 节 |
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

## 5. 实施前现场复核：两台 USB 与 DeviceHub

用户在本轮明确产品/服务始终名为 MileSprint，版本仅暴露设备管理能力，并提供两台 USB 真机与已打开的 DeviceHub 供调研。以下新快照替代首轮的当前连接数量；首轮记录作为历史观察保留。

| 项目 | 本轮实测 | 设计影响 |
| --- | --- | --- |
| 两台 USB | iPhone 11 Pro Max / iOS 27.2；iPad mini (A17 Pro) / iPadOS 26.6.1，均 wired + connected；idevice_id USB 清单与两台硬件 UDID 对应 | 快速枚举可以与 USB 主源交叉核对，不按名称推断连接 |
| DeviceHub / CoreSimulator 分开观察 | DeviceHub 进程运行；另由 simctl 查询到 6 条 Shutdown 的 CoreSimulator 记录，其中 2 条关联不可用的 iOS 18.5 runtime | DeviceHub 可同时展示真机与模拟器；不能以展示位置判类型，也不能把这两条记录套到 USB 真机 |
| 标识 | 两台的硬件 UDID 与 CoreDevice identifier 均不同 | typed locators 必须区分，不能向部署脚本传同一通用字符串 |
| 锁状态 | 两台 passcodeRequired=true、unlockedSinceBoot=true；只读取状态，没有解锁 | 连接、锁状态和具体操作能力独立表达 |
| 详情查询 | iPad 约 131ms 成功；iPhone 5054ms 返回 exit 2 / info.outcome=timeout；其 lockState 仍成功 | details 按需查询，不进入每轮目录扫描；单项失败不覆盖连接观察 |
| 声明能力 | 两台均声明 installapp/getlockstate；只有 iPad 当前列表包含 applicationcontrol | 只记录 provider 声明，不把该列表或 preparedness 数值当统一 ready |
| 存储 | iPhone 可用约 164.4GiB，总盘 256GB；iPad 可用约 57.3GiB，总盘 128GB；查询分别约 66/60ms | 可用空间可轻量获取，但这是时点值，不是可承诺配额 |
| 电量 | iPhone 85%、充电；iPad 100%、外接电源且充满；查询约 33/31ms | 可附带展示，首版不设为申请成功硬条件 |
| 数据卷 | 6 个模拟器数据目录共用同一文件系统 | 宿主资源不能按设备重复累计 |
| 快速路径 | simctl 三次约 66–116ms；devicectl 约 63–70ms；USB 枚举约 5–12ms | 15 秒目录轮询具有可行性；这些是小样本，不是 SLA |

两个易误用点已通过现场命令确认：

- devicectl 651.13.5 的 `--timeout 3` 返回 exit 64，要求至少 5 秒；不能将参数错误当设备掉线。
- ideviceinfo 1.4.0 加 `-s` 读取磁盘/电量域时，两台均 exit 0 但返回空 plist；不加 `-s` 的现有查询方式两台均取得字段。探测必须校验内容。

本轮未拔插 USB、未关闭 DeviceHub、未启停模拟器、未查看屏幕镜像或 App 内容。也未以读取成功证明安装、运行或测试可行。

## 6. SDK、CLI 与租约隔离小样

小样均在独立临时目录中使用合成设备或临时数据库，未修改真实设备、doumen 或 Agent 配置；MCP 临时服务已停止，端口已关闭。结构化结果保存在 [preflight-2026-10-19.json](evidence/preflight-2026-10-19.json)，临时原始脚本不作为正式源码合入。

| 假设 | 实测结果 | 尚未证明 |
| --- | --- | --- |
| 官方 SDK 可保持 MileSprint 身份、单进程服务多个调用者 | 固定 mcp==2.3.0，两个客户端同时 list_tools/call_tool，并看到同一组合成设备；身份为 MileSprint | 与本项目 SQLite/真实目录的成品集成 |
| 兼容 MCP 客户端 | auto 协商 2026-07-28；legacy 2025-11-25，均完成合成调用 | 所有特定 Agent 宿主的配置和行为 |
| CLI 可复用 SDK | argparse + asyncio + Client 的新进程 CLI 登记/查询成功；无需 mcp[cli] 或 Typer | 完整命令树与实际错误呈现 |
| 本地入口保护不需要角色系统 | 正确 token 200；缺/错 token 401；非法 Host 421、Origin 403；允许的本地 Origin 200 | 对同 macOS 用户进程的强隔离，本版不承诺 |
| 结构化业务错误 | 同一合成登记工具，首次成功，再次同名返回 is_error=true 及 code/retryable/details；成功 schema 保持 | 全部实际设备/租约错误路径 |
| 单设备并发互斥 | 20 轮双独立进程争用，均 1 held / 1 conflict | 断电、损坏与真实 HTTP/SQLite 联动 |
| 到期/旧 token/重启语义 | 同事务到期重授；旧凭据不改新 lease；终态 release 重试；故障回滚；关库重开保持原期限；同目录 flock 均通过 | 成品进程重启；到期小样使用可控时间，不是长时间现场运行 |

MCP 单次缓存已热的合成成本：TCP 就绪约 191ms，空闲 RSS 约 66.8MiB，新进程 CLI 查询约 273ms，28 个依赖包，venv 分配空间约 33.2MiB。RSS 由 macOS ps 采集，venv 大小不包含外置 Python 解释器/标准库；不含真实探测和 SQLite，不作为性能承诺。

新增一手依据：

- [mcp 2.3.0 发布包](https://pypi.org/project/mcp/2.3.0/) 与 [官方版本发布](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)：以固定版本 API 为准，不照搬旧 FastMCP 示例。
- [SDK 客户端 transport](https://py.sdk.modelcontextprotocol.io/client/transports/)：自定义 header 通过 httpx2 客户端传入；本机连接使用 trust_env=False，避免代理环境改变 loopback 请求路径。
- [SDK 错误处理](https://py.sdk.modelcontextprotocol.io/servers/handling-errors/) 与 [固定版返回转换源码](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/src/mcp/server/mcpserver/utilities/func_metadata.py)：结构化结果与业务错误契约已有小样支持。
- [SQLite 事务](https://www.sqlite.org/lang_transaction.html)、[部分索引](https://www.sqlite.org/partialindex.html)：使用写事务和 held 唯一约束，无需额外锁服务。
- [Python 时钟](https://docs.python.org/3/library/time.html)、[文件锁](https://docs.python.org/3/library/fcntl.html)：跨重启期限用 UTC 毫秒，同目录单实例用 flock，不删除仍在使用的锁文件。

## 7. 设备分类澄清

用户指出 DeviceHub 中两台 USB 设备是真机。此前摘要把两份清单放在一起叙述，未点名区分，容易误读。只读复核结论：

| 独立对象 | 来源与复核结果 | 分类 |
| --- | --- | --- |
| iPhone 11 Pro Max、iPad mini (A17 Pro) | devicectl 的 hardware.reality=physical、transportType=wired；硬件 UDID 与 USB 清单吻合 | 本次目标 USB 真机，两台都不是模拟器，不适用 CoreSimulator runtime 诊断 |
| iPhone 15 的 iOS 18.5 历史条目 | simctl 返回 runtime profile not found；对应 device.plist 的 deviceType 为 CoreSimulator.SimDeviceType.iPhone-15，runtime 为 iOS-18-5 | 另一条 CoreSimulator 记录，其 ID 不匹配两台 USB 真机 |
| iPad Air 13-inch (M3) 的 iOS 18.5 历史条目 | simctl 返回同类错误；device.plist 的 deviceType 为 CoreSimulator.SimDeviceType.iPad-Air-13-inch-M3，runtime 为 iOS-18-5 | 另一条 CoreSimulator 记录，其 ID 不匹配两台 USB 真机 |

DeviceHub 是展示/管理入口，不是设备类型。真机的 DDI（developer disk image）支持状态与模拟器 runtime 分开记录，不将真机的开发支持问题标成缺少模拟器 runtime。

本机 `devicectl help device info ddiServices` 还说明默认会检查并更新/挂载 DDI。以后如只读查询该信息必须显式使用 `--no-auto-mount-ddis`；本次仅阅读 help，未执行该查询或挂载。
