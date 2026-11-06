"""Read-only Apple device observations, separated by provider."""
import json
import os
import plistlib
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import time


def command(*args):
    return subprocess.run(args, capture_output=True, check=True, timeout=7).stdout


def simulators():
    data = json.loads(command("xcrun", "simctl", "list", "devices", "--json"))
    return [{
        "identity": "sim:" + d["udid"].lower(), "kind": "simulator",
        "name": d["name"], "model": d.get("deviceTypeIdentifier"),
        "runtime": runtime, "boot_state": d["state"],
        "reachability": (
            "runtime_unavailable" if not d["isAvailable"] else
            {"Booted": "reachable", "Shutdown": "needs_boot"}.get(d["state"], "unknown")
        ),
        "locators": {"simulator_udid": d["udid"]},
        "data_path": d.get("dataPath"), "data_size": d.get("dataPathSize"),
    } for runtime, devices in data["devices"].items() for d in devices]


def physical():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "devices.json"
        command("xcrun", "devicectl", "list", "devices", "--timeout", "5",
                "--json-output", str(path))
        data = json.loads(path.read_bytes())
    if data["info"]["outcome"] != "success":
        raise ValueError("CoreDevice query failed")
    rows = []
    for d in data["result"]["devices"]:
        p = d.get("properties") or {}
        h, c, s = (p.get(key) or {} for key in ("hardware", "connection", "state"))
        if h.get("platform") not in ("iOS", "iPadOS"):
            continue
        if h.get("reality") in ("simulated", "virtual") or c.get("transportType") == "sameMachine":
            continue
        ecid = normalize_ecid(h.get("ecid"))
        udid = h.get("udid")
        rows.append({
            "identity": "physical:" + ecid if ecid else None,
            "kind": "physical", "reality": h.get("reality"), "name": s.get("name") or h.get("marketingName") or h.get("productType"),
            "model": h.get("marketingName") or h.get("productType"),
            "os_version": s.get("osVersionNumber"),
            "boot_state": s.get("bootState"),
            "connection": c.get("state"), "transport": c.get("transportType"),
            "reachability": "reachable" if c.get("state") == "connected" else
                            "paired_only" if c.get("pairingState") == "paired" else "unknown",
            "locators": {"coredevice_identifier": d["identifier"], "hardware_udid": udid},
        })
    return rows


def normalize_ecid(value):
    try:
        return format(int(str(value), 0), "x")
    except ValueError:
        return None


def usb_device(udid):
    try:
        data = plistlib.loads(command("ideviceinfo", "-u", udid, "-x"))
        return udid, normalize_ecid(data.get("UniqueChipID")), data
    except (OSError, subprocess.SubprocessError, ValueError, plistlib.InvalidFileException):
        return udid, None, {}


def usb():
    udids = list(dict.fromkeys(command("idevice_id", "-l").decode().split()))
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(usb_device, udids))


def collect(provider):
    try:
        return provider(), {"status": "ok", "observed_at": time()}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return [], {"status": "error", "observed_at": time()}


def scan():
    providers = {"simctl": simulators, "devicectl": physical, "usb": usb}
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {name: pool.submit(collect, provider) for name, provider in providers.items()}
        results = {name: future.result() for name, future in pending.items()}
    physical_rows, _ = results["devicectl"]
    usb_rows, usb_health = results["usb"]
    claimed = set()
    core_ecids = {r["identity"] for r in physical_rows if r["identity"]}
    for row in physical_rows:
        hardware = (row["locators"]["hardware_udid"] or "").lower()
        matches = [(u, e, info) for u, e, info in usb_rows if
                   (e and row["identity"] == "physical:" + e) or
                   (u.lower() == hardware and (not e or not row["identity"]))]
        conflicts = [u for u, e, _ in usb_rows if u.lower() == hardware and e
                     and row["identity"] and row["identity"] != "physical:" + e]
        claimed.update(conflicts)
        claimed.update(u for u, _, _ in matches)
        if conflicts or len(matches) > 1:
            row.update(identity=None, reachability="unknown", usb_present=None)
            continue
        match = matches[0] if matches else None
        verified = match and match[1] and match[2].get("ProductType", "").startswith(("iPhone", "iPad"))
        if verified:
            row["identity"] = "physical:" + match[1]
        elif row["reality"] != "physical":
            row.update(identity=None, reachability="unknown")
        row["usb_present"] = (True if match else False
                              if usb_health["status"] == "ok" and all(e for _, e, _ in usb_rows)
                              else None)
        row["locators"]["usb_udid"] = match[0] if match else None
    for udid, ecid, info in usb_rows:
        if udid in claimed or not ecid or "physical:" + ecid in core_ecids:
            continue
        model = info.get("ProductType", "")
        if not model.startswith(("iPhone", "iPad")):
            continue
        physical_rows.append({
            "identity": "physical:" + ecid, "kind": "physical", "name": info.get("DeviceName", model),
            "model": model, "os_version": info.get("ProductVersion"), "boot_state": None,
            "reachability": "unknown", "connection": None, "transport": None, "usb_present": True,
            "locators": {"usb_udid": udid, "hardware_udid": info.get("UniqueDeviceID")},
            "source": "usb",
        })
    sim_rows, _ = results["simctl"]
    rows = sim_rows + physical_rows
    for row in rows:
        source = row.get("source") or ("simctl" if row["kind"] == "simulator" else "devicectl")
        row["source"] = source
        row["observed_at"] = results[source][1]["observed_at"]
    return rows, {name: value[1] for name, value in results.items()}


def resources(row):
    source = "statvfs" if row["kind"] == "simulator" else "ideviceinfo"
    free = total = None
    status = "unknown"
    try:
        if source == "statvfs" and row.get("data_path"):
            disk = os.statvfs(row["data_path"])
            free, total = disk.f_bavail * disk.f_frsize, disk.f_blocks * disk.f_frsize
        elif row["locators"].get("usb_udid"):
            data = plistlib.loads(command("ideviceinfo", "-u", row["locators"]["usb_udid"],
                                          "-q", "com.apple.disk_usage", "-x"))
            free, total = data.get("AmountDataAvailable"), data.get("TotalDiskCapacity")
            status = "error"
    except (OSError, subprocess.SubprocessError, ValueError, plistlib.InvalidFileException):
        status = "error"
    return {key: {
        "value": value if type(value) is int and value >= 0 else None,
        "unit": "bytes", "source": source, "observed_at": time(),
        "status": "ok" if type(value) is int and value >= 0 else status,
    } for key, value in (("disk_free", free), ("disk_total", total))}


def details(identifier):
    def query(name):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "detail.json"
            args = ["xcrun", "devicectl", "device", "info", name, "--device", identifier,
                    "--timeout", "5", "--json-output", str(path)]
            if name == "ddiServices":
                args.append("--no-auto-mount-ddis")
            command(*args)
            data = json.loads(path.read_bytes())
        if data["info"]["outcome"] != "success" or not data["result"]:
            raise ValueError("Invalid CoreDevice details")
        return data["result"]

    def sample(name):
        result, observation = collect(lambda: query(name))
        return name, {**observation, "data": result if observation["status"] == "ok" else None}

    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(sample, ("details", "lockState", "ddiServices")))
