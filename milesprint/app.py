import asyncio
import fcntl
import logging
import os
from pathlib import Path

import uvicorn

from . import discovery, leases
from .devices import Devices
from .interfaces import build_mcp
from .storage import Store, now_ms


def settings():
    root = Path(os.environ.get("MILESPRINT_STATE_DIR", "~/Library/Application Support/MileSprint")).expanduser()
    token = os.environ.get("MILESPRINT_TOKEN", "")
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError("Set MILESPRINT_TOKEN to at least 32 ASCII characters without spaces")
    port = int(os.environ.get("MILESPRINT_PORT", "8765"))
    if not 1 <= port <= 65535:
        raise ValueError("MILESPRINT_PORT must be between 1 and 65535")
    return root, token, port


async def run(devices, token, port):
    scan_job = None

    async def scan():
        rows, health = await asyncio.to_thread(discovery.scan)
        devices.publish(rows, health)

    async def refresh():
        nonlocal scan_job
        if scan_job is None or scan_job.done():
            scan_job = asyncio.create_task(scan())
        await asyncio.shield(scan_job)

    async def poll(interval, operation):
        failed = False
        while True:
            try:
                await operation()
            except Exception:
                if not failed:
                    logging.getLogger("milesprint").exception("Polling failed: %s", operation.__name__)
                failed = True
            else:
                failed = False
            await asyncio.sleep(interval)

    async def resources():
        snapshot = list(devices.rows.items())
        semaphore = asyncio.Semaphore(4)

        async def sample(key, row):
            async with semaphore:
                return key, row, await asyncio.to_thread(discovery.resources, row)

        devices.publish_resources(await asyncio.gather(*(sample(key, row) for key, row in snapshot)))

    async def expire():
        def sweep():
            with devices.store.transaction() as db:
                leases.expire(db, now_ms())
        await asyncio.to_thread(sweep)

    server = uvicorn.Server(uvicorn.Config(build_mcp(devices, token, port, refresh),
                                         host="127.0.0.1", port=port, access_log=False))
    await refresh()
    jobs = [asyncio.create_task(poll(interval, operation))
            for interval, operation in ((15, refresh), (60, resources), (15, expire))]
    try:
        await server.serve()
    finally:
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)


def serve(root, token, port):
    os.umask(0o077)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "service.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run(Devices(Store(root / "milesprint.sqlite3")), token, port))
