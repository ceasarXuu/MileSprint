"""Local, read-only dashboard for device inventory and current leases."""
import asyncio
from datetime import datetime
from html import escape
from pathlib import Path

from starlette.responses import HTMLResponse, PlainTextResponse

from .storage import Fault

CSS = Path(__file__).with_name("static") / "dashboard.css"
STATUS = {
    "reachable": "可达", "needs_boot": "待启动", "paired_only": "仅配对",
    "runtime_unavailable": "运行时不可用", "unknown": "未知",
}


def cell(value):
    return f"<td>{escape(str(value) if value is not None and value != '' else '—')}</td>"


def row(device):
    lease = device.get("allocation", {})
    held = lease.get("state") == "held"
    expiry = datetime.fromtimestamp(lease["expires_at_ms"] // 1000).astimezone() if (
        held and lease["expires_at_ms"] // 1000 < 253402214400
    ) else None
    status = STATUS.get(device["reachability"], "未知")
    status_class = "online" if device["reachability"] == "reachable" else "neutral"
    usb = {True: "已连接", False: "未连接"}.get(device.get("usb_present"), "—")
    allocation = "占用中" if held else "空闲" if device.get("id") else "未登记"
    if not held and device.get("enabled") is False:
        allocation = "已停用"
    system = device.get("os_version") or (device.get("runtime") or "").rsplit(".", 1)[-1]
    metric = device.get("metrics", {}).get("disk_free", {})
    free = f'{metric["value"] / 2**30:.1f} GiB' if metric.get("status") == "ok" else None
    title = escape(device.get("alias") or device.get("name") or "未命名")
    subtitle = escape(device.get("name") or "") if device.get("alias") else ""
    return (
        f'<tr><th scope="row">{title}<small>{subtitle}</small></th>'
        + cell("真机" if device["kind"] == "physical" else "模拟器")
        + cell(system)
        + f'<td><span class="dot {status_class}"></span>{status}</td>'
        + cell(usb)
        + cell(free)
        + f'<td><span class="pill {"held" if held else ""}">{allocation}</span></td>'
        + cell(lease.get("holder"))
        + cell(expiry.strftime("%m-%d %H:%M") if expiry else ("超出显示范围" if held else None))
        + "</tr>"
    )


def render(devices, occupied):
    nav = "".join(
        f'<a href="{url}"{chr(32) + "aria-current=page" if active else ""}>{label}</a>'
        for url, active, label in (("/", not occupied, "设备"), ("/leases", occupied, "占用"))
    )
    records = [device for device in devices
               if not occupied or device.get("allocation", {}).get("state") == "held"]
    columns = ("设备", "类型", "系统", "状态", "USB", "可用空间", "占用", "持有者", "到期")
    heading = "".join(f'<th scope="col">{label}</th>' for label in columns)
    rows = "".join(row(device) for device in records)
    empty = "暂无占用中的设备" if occupied else "暂无设备"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>MileSprint</title><link rel="stylesheet" href="/dashboard.css">
</head><body><main>
<nav aria-label="管理界面">{nav}</nav>
<div class="table-wrap" tabindex="0" aria-label="设备列表"><table>
<thead><tr>{heading}</tr></thead><tbody>
{rows or f'<tr><td colspan="9" class="empty">{empty}</td></tr>'}
</tbody></table></div></main></body></html>"""


async def dashboard(scope, devices, port):
    headers = dict(scope["headers"])
    allowed_hosts = {f"127.0.0.1:{port}".encode(), f"localhost:{port}".encode()}
    origins = {b"http://" + host for host in allowed_hosts}
    if (headers.get(b"host") not in allowed_hosts
            or headers.get(b"sec-fetch-site") == b"cross-site"
            or headers.get(b"origin") not in origins | {None}):
        return PlainTextResponse("Forbidden", status_code=403)
    if scope["method"] not in {"GET", "HEAD"}:
        return PlainTextResponse("Method not allowed", status_code=405, headers={"Allow": "GET, HEAD"})
    security = {
        "Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'none'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        "X-Content-Type-Options": "nosniff",
    }
    if scope["path"] == "/dashboard.css":
        return PlainTextResponse(CSS.read_text(encoding="utf-8"), media_type="text/css", headers=security)
    try:
        records = await asyncio.to_thread(devices.list)
    except Fault:
        return PlainTextResponse("暂时无法读取设备，请刷新重试。", status_code=503, headers=security)
    return HTMLResponse(render(records, scope["path"] == "/leases"), headers=security)
