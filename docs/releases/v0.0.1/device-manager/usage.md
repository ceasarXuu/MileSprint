# MileSprint v0.0.1 本机使用

在仓库根目录执行 `uv sync --locked`。服务使用当前 Xcode 的 `xcrun`，USB 在位和真机磁盘数据由 libimobiledevice 的 `idevice_id`、`ideviceinfo` 补充。

在服务和 CLI 的环境中设置相同的 `MILESPRINT_TOKEN`。可用 `openssl rand -hex 32` 生成本机凭据。默认监听 `http://127.0.0.1:8765/mcp`，MCP 客户端发送 `Authorization: Bearer <token>`。端口可通过 `MILESPRINT_PORT` 修改。SQLite 默认保存在 `~/Library/Application Support/MileSprint`，也可设置 `MILESPRINT_STATE_DIR`。

```sh
uv run milesprint serve
```

在另一个终端操作。将 `identity` 换为发现结果中目标设备的值，将 App ID 换成实际目标。

```sh
uv run milesprint call devices_list '{"refresh_now":true}'
uv run milesprint call device_register '{"identity":"sim:<UDID>","alias":"doumen-sim"}'
uv run milesprint call device_get '{"device":"doumen-sim"}'
uv run milesprint call lease_acquire '{"device":"doumen-sim","holder":"agent-1","task":"doumen-check","ttl_seconds":300,"intent":{"bundle_id":"com.example.doumen","operation":"inspect","data_scope":"app_local"}}'
```

使用返回的 typed locator 调用 doumen 原有脚本。完成后将同一租约的 `id` 和 `token` 作为 JSON 从标准输入传给 `uv run milesprint call lease_release -`。续期使用 `lease_renew`，传 `lease_id`、`token`、`ttl_seconds`。租约从 `held` 转为 `released` 或 `expired`，两者都是终态。启动、可达性和 USB 在位独立于租约。停用使用 `device_set_enabled`，现有租约按原时限继续。

`device_policy_check` 使用与申请相同的 `intent`。App 范围使用 `app_local`，支持 `inspect`、`launch`、`install_preserving`、`write_owned`、`reset_app` 和 `uninstall_app`。目标 App 默认 `resettable`。显式 `owned_only` 的写入声明需附外部 `receipt`。权限判断基于申报范围，实际操作由调用方完成。

`devices_list` 和 `device_get` 的 `refresh_now` 刷新目录。磁盘采集独立轮询。申请可传 `min_free_bytes`，缺失、过期或不满足下限的磁盘观测均拒绝。真机详情通过 `device_get` 的 `include_details` 请求。

在同一台 Mac 打开 `http://127.0.0.1:8765/` 可查看管理界面。「设备」显示目录和当前占用，「占用」只显示有效租约。页面每 15 秒刷新，登记、策略变更和租约操作通过 CLI 或 MCP 完成。
