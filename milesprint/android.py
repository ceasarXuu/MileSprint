"""Read-only discovery of local Android SDK devices."""
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import time


def sdk_tool(name, directory):
    root = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
    candidate = (Path(root) if root else Path.home() / "Library/Android/sdk") / directory / name
    return shutil.which(name) or (str(candidate) if os.access(candidate, os.X_OK) else None)


def run(tool, *args):
    return subprocess.run([tool, *args], check=True, capture_output=True,
                          timeout=3, text=True, errors="replace").stdout


def avds(tool):
    return [{"identity": f"android:avd:{name}", "platform": "android", "kind": "simulator",
             "name": name, "reachability": "needs_boot", "boot_state": "not_observed",
             "locators": {"avd_name": name}}
            for name in run(tool, "-list-avds").splitlines()
            if re.fullmatch(r"[\w.-]+", name)]


def attached(tool):
    lines = run(tool, "devices", "-l").splitlines()
    if not lines or lines[0].strip() != "List of devices attached":
        raise ValueError("Unexpected adb device list")
    entries = [line.split() for line in lines[1:] if line.strip()]

    def describe(entry):
        serial, state, *fields = entry
        attrs = dict(field.split(":", 1) for field in fields if ":" in field)
        emulator = bool(re.fullmatch(r"emulator-\d+", serial))
        usb = bool(attrs.get("usb"))
        # Network endpoints are transport addresses, not stable hardware identities.
        if not emulator and not usb:
            return None
        name = None
        version = None
        booted = False
        transport_id = attrs.get("transport_id", "")
        if state == "device" and transport_id.isdecimal():
            if emulator:
                try:
                    output = run(tool, "-s", serial, "emu", "avd", "name").splitlines()
                    if len(output) == 2 and output[1] == "OK" and re.fullmatch(r"[\w.-]+", output[0]):
                        name = output[0]
                except (OSError, subprocess.SubprocessError):
                    pass
            try:
                props = run(tool, "-t", transport_id, "shell", "getprop")
                properties = dict(re.findall(r"^\[([^\]]+)\]: \[(.*)\]$", props, re.MULTILINE))
                version = properties.get("ro.build.version.release")
                booted = properties.get("sys.boot_completed") == "1"
            except (OSError, subprocess.SubprocessError):
                pass
        identity = (f"android:avd:{name}" if name else None) if emulator else f"android:usb:{serial}"
        return {
            "identity": identity, "platform": "android",
            "kind": "simulator" if emulator else "physical",
            "name": name or attrs.get("model", serial), "model": attrs.get("model"),
            "os_version": version, "connection": state,
            "transport": "emulator" if emulator else "wired",
            "usb_present": None if emulator else True,
            "boot_state": "booted" if booted else None,
            "reachability": "reachable" if booted else
                            {"device": "booting", "offline": "offline",
                             "unauthorized": "unauthorized"}.get(state, "unknown"),
            "locators": {"adb_serial": serial, "adb_transport_id": transport_id or None,
                         **({"avd_name": name} if name else {})},
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        return [row for row in pool.map(describe, entries) if row is not None]


def resources(row):
    free = total = None
    status = "unknown"
    tool = sdk_tool("adb", "platform-tools")
    target = row["locators"].get("adb_transport_id")
    if tool and target and row["reachability"] == "reachable":
        try:
            output = run(tool, "-t", target, "shell", "df", "-k", "/data").splitlines()
            fields = output[-1].split()
            if fields[-1] != "/data":
                raise ValueError("Unexpected mount")
            total, free = int(fields[1]) * 1024, int(fields[3]) * 1024
            status = "ok" if 0 <= free <= total else "error"
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            status = "error"
    return {key: {"value": value if status == "ok" else None, "status": status,
                  "unit": "bytes", "source": "adb", "observed_at": time()}
            for key, value in (("disk_free", free), ("disk_total", total))}
