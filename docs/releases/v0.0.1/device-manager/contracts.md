# MileSprint v0.0.1 工程接口草案

- 状态：实施前细化，尚无正式实现。
- Product Authority：[PRD 的 PD1–PD9](prd.md#confirmed-product-decisions)。本页只细化工程契约，不建立第二套产品权威。
- 证据：[调研记录](evidence.md)、[结构化小样结果](evidence/preflight-2026-10-19.json)。

## 1. 身份与运行形态

| 对象 | 约定 |
| --- | --- |
| 产品、常驻服务、MCP server name | `MileSprint` |
| 版本 | 正式实现 `0.0.1`；本轮临时小样使用 `0.0.1-preflight` |
| 本版业务能力 | 设备目录、只读观测、策略和租约；不暴露 Issue/Agent 调度、优化或设备执行工具 |
| CLI / Python 包 | `milesprint`；这是技术标识，产品名不改变 |
| 接口 | 单个 localhost Streamable HTTP `/mcp`，CLI 复用同一 SDK 客户端，不另写 REST 业务接口 |
| 运行环境 | 本机 Python 3.13、Xcode 27.1；候选依赖锁定 `mcp==2.3.0`，不承诺未验证平台 |
| 本机状态目录 | 建议 `~/Library/Application Support/MileSprint`，可用 `MILESPRINT_STATE_DIR` 指定；跨 worktree 共享同一目录 |
| 连接与入口凭据 | 启动参数/config 提供 endpoint；CLI 与 Agent 使用同一入口凭据，无角色分层 |

服务使用 `MCPServer("MileSprint", version="0.0.1")`，配合 `streamable_http_app(json_response=True, stateless_http=True)`。传输无会话不等于设备/租约无状态，业务状态仍在同一 SQLite。

首版手动运行 `milesprint serve`，不自动安装登录启动项。MCP 配置依具体宿主提供，本次未修改任何 Agent 配置。只配置本机静态 token、Host/Origin 校验，不虚构 OAuth issuer。

## 2. 发现与稳定身份

1. `simctl` 是模拟器清单主源；`devicectl` 补充 CoreDevice 元数据，不把两边同一模拟器登记两次。
2. 物理 USB 设备以硬件 UDID 作为归一化依据，结合 `idevice_id -l` 核对当前 USB 存在性；CoreDevice identifier 是可更新的 typed locator，不用作唯一物理身份。
3. 模拟器以 simulator UDID 作为归一化依据；设备名称仅展示。当前真机 iPad mini 和同型号模拟器可以同时存在，不能按名字合并。
4. 注册生成不可变内部 UUID，alias 唯一且可由用户/Agent设定；`identity_key` 唯一，避免同一设备以不同 alias 多次注册。
5. 无法确认类型或标识映射的缓存记录显示 unknown；不按名称猜 ID，不静默替换目标。

建议 Device 视图字段：

```json
{
  "id": "device-example-id",
  "alias": "doumen-phone",
  "kind": "physical",
  "platform": "ios",
  "model": "iPhone 11 Pro Max",
  "os_version": "27.2",
  "locators": {
    "hardware_udid": "synthetic-hardware-id",
    "coredevice_identifier": "synthetic-coredevice-id"
  },
  "identity_verified_at": "2026-10-19T04:00:00+08:00",
  "enabled": true,
  "connection": {"transport": "usb", "state": "connected"},
  "boot_state": "booted",
  "allocation": {"state": "free"},
  "policy": {"device_ceiling": "app_scoped", "default_app_policy": "resettable"}
}
```

ID 与时间是示意，真实标识保留在本机台账。`locators` 为有类型字段，不提供一个含义不明的通用 device_id 给外部安装脚本。

## 3. 观察、资源与刷新

| 观察 | 获取方法 | 解释 |
| --- | --- | --- |
| 快速目录 | simctl JSON + devicectl JSON + idevice_id USB 清单 | 可在后台采集，不触发启动/安装 |
| OS、机型、developer mode、声明能力 | devicectl `properties`、`capabilities` | 保留来源；不解释未公开的 preparedness 数值为统一 ready |
| 锁状态 | 按需 `device info lockState` | 单独返回 passcodeRequired/unlockedSinceBoot；不以“已连接”推导已解锁 |
| 详情 | 按需 `device info details` | 可能超时；失败不能抹掉成功的 USB 连接观察 |
| 可用/总磁盘 | ideviceinfo `com.apple.disk_usage` XML plist | 读取 AmountDataAvailable、TotalDiskCapacity；总容量不等于 App 可无限使用的容量 |
| 电量/充电 | 可选读取 `com.apple.mobile.battery` | 本次两台均可读，但不设为 acquire 必须成功的条件 |
| 模拟器 dataPathSize | simctl 报告值 | 不是可用空间、内存或实时 App footprint |
| 模拟器所在磁盘余量 | 对数据路径做 statvfs，按文件系统去重 | 本机 6 个目录共用同一数据卷，不能重复累计容量 |

资源值统一携带 `value / unit / status / observed_at / source`。status 为 ok、unknown、unsupported、stale 或 error；无值为 null，不用 0 替代。observed_at 表示本服务取得报告的时间，不冒充 Apple 缓存值的实际测量时间。

建议初始轮询：目录 15 秒，磁盘 60 秒；两台设备的资源探测可独立进行，同设备探测不重叠。手动 refresh 合并到正在进行的同类探测，不积压新的轮询任务。

devicectl 的 `--timeout` 本机要求至少 5 秒，建议用 5 秒并加外层约 6 秒截止；不能传 3 秒。simctl/idevice_id/ideviceinfo 分别设置外层有界超时。details 与 lockState 不进入每轮目录扫描；需要时单独查询，返回每项自己的错误。

不使用 `ideviceinfo -s` 查询磁盘/电量：本机它返回 exit 0 却给出空字典。必须检查业务字段和类型，devicectl 还需检查 `info.outcome`；不能仅依据退出码判成功。

## 4. 策略输入

- `device_policy_set` 设置设备上限和 App override，目标 App 缺省始终是 resettable（PD7）。
- `device_policy_check` 输入明确设备、bundle_id、operation、data_scope 和必要的外部 receipt 引用；结果表示声明用途是否符合配置，不验证实际设备行为。
- preserve/owned_only 是显式例外；owned_only 才要求任务登记范围引用，默认 resettable 不引入这些保护现场成本。
- Agent 可登记和改策略（PD8）；有效 lease 期间仍拒绝更改对应设备身份/策略，以保证同一租约的 policy revision 一致。
- `device_ceiling` 的登记值仍生效；resettable 的默认作用域是目标 App 本地数据，不自动扩大为云/系统/整机权限。

## 5. 工具与最少参数

下表是正式实现的候选契约，小样中的 device_list/device_register 仅验证 SDK，不构成 API 已实现承诺。

| Tool | 输入要点 | 结果要点 |
| --- | --- | --- |
| `milesprint_status` | 无 | MileSprint 身份、版本、devices 能力、provider 健康与样本时间 |
| `devices_list` | kind/注册状态筛选，refresh | 候选与已登记目录，各项错误独立 |
| `device_get` | 内部 ID 或 alias，refresh，是否查详情 | typed locators、观测、策略、占用；不返回他人租约 token |
| `device_register` | 已观察身份、alias、设备上限、用途 | 唯一台账对象；App 默认 resettable |
| `device_policy_set` | device、上限、App override | 新 policy revision，或有效占用冲突 |
| `device_policy_check` | device、bundle、operation/data_scope | allow/deny、依据、未覆盖的外部授权范围 |
| `leases_list` | device/状态筛选 | 当前和历史占用，不返回 token |
| `lease_acquire` | 明确 device、holder、task、worktree/repo、intent、ttl_seconds | lease、一次性返回的 token、到期时间、typed locators 或冲突 |
| `lease_renew` | lease ID、token、ttl_seconds | 新到期时间，仅有效 lease 可续 |
| `lease_release` | lease ID、token、交接摘要 | released/expired 终态；不执行设备操作 |

TTL 由调用者显式传正整数秒，内部保存 UTC epoch 毫秒；本版不引入按任务优先级决定 TTL 的策略。所有 Agent 可调用上述全部入口；租约 token 用来匹配某次持有关系，不是操作者角色。

## 6. 租约事务

```sql
CREATE UNIQUE INDEX one_held_per_device
ON leases(device_id) WHERE state = 'held';
```

acquire 的顺序固定为：`BEGIN IMMEDIATE → 取得当前时间 → 结束该设备到期 lease → 检查有效占用/策略 → 插入新 held → COMMIT`。时间在拿到写锁后取得，避免锁等待提前消耗新 TTL；上述任何失败整体回滚。

- 到期边界：`expires_at_ms <= now_ms`；同一事务可以结束旧 lease 并发出新 lease，不依赖后台轮询。
- renew：仅当前有效凭据可续；建议使用 `max(原到期时间, now + ttl)`，不因较短 TTL 意外缩短期限。
- release：同一凭据重复释放只返回原终态；不得更新设备的另一份新 lease。
- 重启：保留原绝对到期时间，不以启动时刻重新加 TTL。墙钟调整会影响实际持有时长，首版不引入时钟异常恢复门槛；monotonic 仅用于超时/轮询调度。
- 单实例：同状态目录用 flock 持有文件描述符至进程结束，不删除锁文件，避免 inode 变化形成两把锁。
- SQLite 等待超时是 STORE_BUSY，不是 LEASE_CONFLICT；存储失败不能返回设备空闲。

## 7. 成功与错误

成功输出采用明确 Pydantic 模型，以生成 output schema 和 structured_content。普通 dict 注解在本次 SDK 小样中未提供期望的结构化结果。

可预期业务失败使用 SDK 的 CallToolResult，令 is_error=true，structured_content 为：

```json
{
  "error": {
    "code": "LEASE_CONFLICT",
    "message": "Device already has an active lease",
    "retryable": true,
    "details": {"lease_id": "example", "expires_at": "example"}
  }
}
```

2.3.0 已实测 `Annotated[CallToolResult, 成功模型]` 保持成功 schema，并允许结构化失败；不使用“成功模型 | CallToolResult”注解。ToolError 仅有文本，不用于需要 code/details 的预期业务分支。

| 错误码 | 含义/处理 |
| --- | --- |
| DEVICE_NOT_FOUND / IDENTITY_UNVERIFIED | 不猜选目标；检查目录或重新登记映射 |
| DEVICE_UNAVAILABLE / PROBE_TIMEOUT / PROBE_INVALID_RESULT | 区分环境不可用、单项超时和无效返回；保留其余有效观察 |
| POLICY_DENIED / DEVICE_BUSY | 用途超出策略，或有效租约期间试图更改策略/身份 |
| LEASE_CONFLICT | 有有效持有者，带 holder 和到期时间，不带 token |
| LEASE_NOT_ACTIVE / INVALID_LEASE_CREDENTIAL | 旧租约或凭据不匹配，不影响新持有者 |
| STORE_BUSY / STORE_ERROR | 分别为可重试写锁等待与存储故障，不冒充空闲 |

CLI 先区分连接/协议失败与工具失败，再读取结构化 code；参数校验和未知异常仍保留通用失败分支，不能假定所有 SDK 错误都有 structured_content。

## 8. 尚未证明的部分

真实 USB 拔插和睡眠唤醒后的观察时延、MCP 与 SQLite 租约的成品集成、异常断电/数据库损坏均未验证。本轮没有占用真实设备租约，没有启动/安装/运行/清理 App，也没有验证任何 doumen 产品测试。实施阶段只围绕这些与当前主题相关的路径补齐。
