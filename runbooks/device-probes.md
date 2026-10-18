# MileSprint 的 Apple 设备只读探测

适用：本机 Xcode 27.1、devicectl 651.13.5、ideviceinfo 1.4.0；其他版本先读本机 help。产品名为 MileSprint，这些只是 v0.0.1 的设备能力。

## 快速目录

```sh
xcrun simctl list devices --json
xcrun devicectl list devices --json-output - --omit-deprecated-fields-in-json --timeout 5
idevice_id -l
```

- devicectl JSON v5 优先读取 properties；已弃用的 hardwareProperties 等不作为主路径。
- 清单包含模拟器和缓存真机。模拟器以 simulator UDID 去重，USB 真机以硬件 UDID 对照 idevice_id；不要按名称合并真机和同名模拟器。
- CoreDevice identifier 与硬件 UDID 不同；对外提供 typed locators，不混成一个 device_id。
- DeviceHub 进程运行不等于模拟器 Booted；以 simctl 的运行状态和 runtime availability 为准。
- 本机 devicectl timeout 最小值为 5，传 3 返回参数错误 64，不是设备故障。

## 按需详情

```sh
xcrun devicectl device info lockState --device <CoreDevice-ID> --json-output - --omit-deprecated-fields-in-json --timeout 5
xcrun devicectl device info details --device <CoreDevice-ID> --json-output - --omit-deprecated-fields-in-json --timeout 5
```

details 曾在 USB connected 的设备上 5 秒超时，lockState 仍成功。不要把 details 放入每轮目录扫描；分项记录 info.outcome、耗时与错误，不抹掉其他新鲜观察。

## 真机资源

```sh
ideviceinfo -u <硬件UDID> -q com.apple.disk_usage -x
ideviceinfo -u <硬件UDID> -q com.apple.mobile.battery -x
```

- 用 plistlib 解析 XML，磁盘读取 AmountDataAvailable / TotalDiskCapacity；电量读取 BatteryCurrentCapacity / BatteryIsCharging / ExternalConnected。
- 本机加 `-s` 两个资源域均可能 exit 0 但返回空字典；不将它作为采集路径，也不只看退出码。
- 设置外层超时并校验字段类型。无值是 unknown/error，不是 0；资源值附来源与观测时间。
- 不运行 Instruments，不读取 App/用户内容，不自动配对未登记设备。

## 跨 worktree 与本机状态

所有 worktree 使用同一 MileSprint 状态目录。MCP/CLI 连接 loopback 时不要把代理环境带入客户端；SDK 2.3.0 可用 httpx2.AsyncClient(trust_env=False)。

同目录实例锁采用 flock 并持有文件描述符；不要 unlink 该锁文件后再创建，否则旧进程与新进程可能锁住不同 inode。租约必须在 SQLite 写事务内处理到期和重授，不能只依靠周期清理。

本手册仅记录已验证操作经验。实际设备上的安装、测试和数据处理仍由原工具执行；MileSprint 管理接口不代执行。
