# Android 设备探测

用 `adb devices -l` 查看当前 ADB 目标，用 `emulator -list-avds` 查看已配置的 AVD。两份清单有重叠。MileSprint 用 `adb -s <serial> emu avd name` 关联运行实例和 AVD，ADB serial 随端口变化。

本机实测 `emulator-5556` 一度显示 offline，随后才变成 device。读取 `adb -s emulator-5556 shell getprop sys.boot_completed` 返回 1 后，才可确认系统已启动。LaunchAgent 的 PATH 可能与终端不同，默认还能从 `~/Library/Android/sdk` 找到工具。

若 macOS 的 `ioreg` 能看到 Android ADB 接口，但默认 `adb devices -l` 只列出模拟器，先检查 ADB 日志和接口的 `IOUserClientCreator`。本机实测 Redmi K60 Ultra 的 USB 接口由监听 5038 的另一个 ADB server 持有，默认 5037 的 server 报 `usb_osx.cpp:425 Could not open interface: e00002c5`（IOKit exclusive access）。`adb -P 5038 devices -l` 能看到真机。LaunchAgent 可配置 `MILESPRINT_ADB_PORTS=5037,5038` 并重新载入。ADB transport ID 仅在所属 server 内有效，后续命令须同时指定端口。
