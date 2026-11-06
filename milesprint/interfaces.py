import argparse
import asyncio
import hmac
import json
import sys
from functools import wraps
from typing import Annotated, Literal

from httpx2 import AsyncClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from . import discovery, leases
from .storage import Fault, audit, now_ms

Ceiling = Literal["app_scoped", "device_resettable"]
AppPolicy = Literal["preserve", "owned_only", "resettable"]
Kind = Literal["physical", "simulator"]
TTL = Annotated[int, Field(strict=True, gt=0)]
Capacity = Annotated[int, Field(strict=True, ge=0)]
LeaseState = Literal["held", "released", "expired"]


class Intent(BaseModel):
    bundle_id: str | None = None
    operation: str
    data_scope: str
    receipt: str | None = None


class Result(BaseModel):
    data: dict | list


Output = Annotated[CallToolResult, Result]


def build_mcp(devices, token, port, refresh):
    server = MCPServer("MileSprint", version="0.0.1")

    def tool(fn):
        @wraps(fn)
        async def invoke(*args, **kwargs):
            try:
                value = await fn(*args, **kwargs)
                return Result(data=value)
            except Fault as exc:
                if exc.code not in {"STORE_BUSY", "STORE_ERROR"}:
                    try:
                        with devices.store.transaction() as db:
                            audit(db, "tool_rejected", fn.__name__, code=exc.code)
                    except Fault:
                        pass
                error = {"code": exc.code, "message": str(exc), "details": exc.details,
                         "retryable": exc.code in {"LEASE_CONFLICT", "STORE_BUSY", "DEVICE_UNAVAILABLE"}}
                return CallToolResult(is_error=True, structured_content={"error": error},
                                      content=[TextContent(type="text", text=str(exc))])
        server.tool()(invoke)
        return invoke

    @tool
    async def milesprint_status() -> Output:
        return {"name": "MileSprint", "version": "0.0.1", "providers": devices.health}

    @tool
    async def devices_list(kind: Kind | None = None, registered: bool | None = None,
                           refresh_now: bool = False) -> Output:
        if refresh_now:
            await refresh()
        return devices.list(kind, registered)

    @tool
    async def device_get(device: str, refresh_now: bool = False, include_details: bool = False) -> Output:
        if refresh_now:
            await refresh()
        result = devices.get(device)
        if include_details:
            identifier = result["locators"].get("coredevice_identifier")
            result["details"] = (
                await asyncio.to_thread(discovery.details, identifier)
                if identifier and result["reachability"] == "reachable" else None
            )
        return result

    @tool
    async def device_register(identity: str, alias: str, ceiling: Ceiling = "app_scoped") -> Output:
        return devices.register(identity, alias, ceiling)

    @tool
    async def device_set_enabled(device: str, enabled: bool) -> Output:
        return devices.set_enabled(device, enabled)

    @tool
    async def device_policy_set(device: str, ceiling: Ceiling, bundle_id: str | None = None,
                                app_policy: AppPolicy | None = None) -> Output:
        return devices.set_policy(device, ceiling, bundle_id, app_policy)

    @tool
    async def device_policy_check(device: str, intent: Intent) -> Output:
        return devices.check_policy(device, **intent.model_dump())

    @tool
    async def leases_list(device: str | None = None, state: LeaseState | None = None) -> Output:
        with devices.store.transaction() as db:
            leases.expire(db, now_ms())
            device_id = devices.store.device(db, device)["id"] if device is not None else None
            return [leases.public(row) for row in db.execute("""
                SELECT * FROM leases WHERE (? IS NULL OR device_id = ?) AND (? IS NULL OR state = ?)
                ORDER BY expires_at_ms DESC
                """, (device_id, device_id, state, state))]

    @tool
    async def lease_acquire(device: str, holder: str, task: str, ttl_seconds: TTL,
                            intent: Intent, worktree: str | None = None,
                            min_free_bytes: Capacity | None = None) -> Output:
        await refresh()
        return leases.acquire(devices, device, holder, task, ttl_seconds, intent.model_dump(),
                              worktree, min_free_bytes)

    @tool
    async def lease_renew(lease_id: str, token: str, ttl_seconds: TTL) -> Output:
        return leases.change(devices.store, lease_id, token, "renew", ttl_seconds=ttl_seconds)

    @tool
    async def lease_release(lease_id: str, token: str, handoff: str | None = None) -> Output:
        return leases.change(devices.store, lease_id, token, "release", handoff=handoff)

    app = server.streamable_http_app(
        json_response=True, stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                                      allowed_hosts=[f"127.0.0.1:{port}"],
                                                      allowed_origins=[]))
    expected = b"Bearer " + token.encode()

    async def authenticate(scope, receive, send):
        if scope["type"] == "http":
            supplied = [value for key, value in scope["headers"] if key == b"authorization"]
            if len(supplied) != 1 or not hmac.compare_digest(supplied[0], expected):
                await JSONResponse({"error": "Unauthorized"}, status_code=401)(scope, receive, send)
                return
        await app(scope, receive, send)

    return authenticate


async def call(port, token, name, arguments):
    async with AsyncClient(headers={"Authorization": "Bearer " + token}, trust_env=False) as http:
        transport = streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=http)
        async with Client(transport) as client:
            result = await client.call_tool(name, arguments)
            print(json.dumps(result.structured_content or result.model_dump(mode="json"),
                             ensure_ascii=False, indent=2))
            return int(bool(result.is_error))


def main():
    from .app import serve, settings

    parser = argparse.ArgumentParser(prog="milesprint")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    invoke = sub.add_parser("call", help="Call a MileSprint MCP tool")
    invoke.add_argument("tool")
    invoke.add_argument("arguments", nargs="?", default="{}",
                        help="JSON object, or - to read JSON from standard input")
    args = parser.parse_args()
    try:
        root, token, port = settings()
        if args.command == "serve":
            serve(root, token, port)
            return 0
        arguments = json.loads(sys.stdin.read() if args.arguments == "-" else args.arguments)
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
        return asyncio.run(call(port, token, args.tool, arguments))
    except Exception as exc:
        print(f"MileSprint: {exc}", file=sys.stderr)
        return 1
