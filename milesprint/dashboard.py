"""Local, read-only dashboard for device inventory and current leases."""
import asyncio
from datetime import datetime
from hashlib import sha256
from html import escape
from pathlib import Path

from starlette.responses import HTMLResponse, PlainTextResponse, Response

from .storage import Fault

STATIC = Path(__file__).with_name("static")
ASSETS = {
    "/dashboard.css": ("text/css", (STATIC / "dashboard.css").read_bytes()),
    "/dashboard.js": ("text/javascript", (STATIC / "dashboard.js").read_bytes()),
}


def table_rows(devices):
    return "".join(map(row, devices)) or '<tr><td colspan="11" class="empty">暂无设备</td></tr>'


def etag(rows):
    return '"' + sha256(rows.encode()).hexdigest() + '"'

STATUS = {
    "reachable": "可达", "needs_boot": "待启动", "paired_only": "仅配对",
    "offline": "离线", "unauthorized": "未授权", "booting": "启动中",
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
        + cell(device.get("model"))
        + cell("Android" if device.get("platform") == "android" else "Apple")
        + cell(system)
        + f'<td><span class="dot {status_class}"></span>{status}</td>'
        + cell(usb)
        + cell(free)
        + f'<td><span class="pill {"held" if held else ""}">{allocation}</span></td>'
        + cell(lease.get("holder"))
        + cell(expiry.strftime("%m-%d %H:%M") if expiry else ("超出显示范围" if held else None))
        + "</tr>"
    )


def render(rows):
    columns = ("设备", "类型", "型号", "平台", "系统", "状态", "USB", "可用空间", "占用", "持有者", "到期")
    heading = "".join(f'<th scope="col">{label}</th>' for label in columns)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="/dashboard.js" defer></script>
<title>MileSprint</title><link rel="stylesheet" href="/dashboard.css">
</head><body><main>
<nav aria-label="管理界面"><a href="/" aria-current="page">设备</a></nav>
<div class="table-wrap" tabindex="0" aria-label="设备列表"><table>
<thead><tr>{heading}</tr></thead><tbody id="devices" data-etag='{etag(rows)}'>{rows}</tbody></table></div><small id="refresh-status" role="status"></small></main></body></html>"""


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
        "Content-Security-Policy": "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        "X-Content-Type-Options": "nosniff",
    }
    if scope["path"] in ASSETS:
        media_type, content = ASSETS[scope["path"]]
        return Response(content, media_type=media_type, headers=security)
    try:
        records = await asyncio.to_thread(devices.list)
    except Fault:
        return PlainTextResponse("暂时无法读取设备，请刷新重试。", status_code=503, headers=security)
    rows = table_rows(records)
    if scope["path"] == "/dashboard/rows":
        tag = etag(rows)
        security["ETag"] = tag
        if headers.get(b"if-none-match") == tag.encode():
            return Response(status_code=304, headers=security)
        return HTMLResponse(rows, headers=security)
    return HTMLResponse(render(rows), headers=security)
