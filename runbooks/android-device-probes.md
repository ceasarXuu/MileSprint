# Android 设备探测

用 `adb devices -l` 查看当前 ADB 目标，用 `emulator -list-avds` 查看已配置的 AVD。两份清单有重叠。MileSprint 用 `adb -s <serial> emu avd name` 关联运行实例和 AVD，ADB serial 随端口变化。

本机实测 `emulator-5556` 一度显示 offline，随后才变成 device。读取 `adb -s emulator-5556 shell getprop sys.boot_completed` 返回 1 后，才可确认系统已启动。LaunchAgent 的 PATH 可能与终端不同，默认还能从 `~/Library/Android/sdk` 找到工具。
