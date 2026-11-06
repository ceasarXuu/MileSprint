"""Explicit lease transitions: held → expired or released. Terminal rows stay terminal."""
import hashlib
import hmac
import json
import secrets
from uuid import uuid4

from . import policies
from .storage import Fault, audit, now_ms


def expire(db, now):
    rows = db.execute("""UPDATE leases SET state = 'expired'
        WHERE state = 'held' AND expires_at_ms <= ? RETURNING id, holder""", (now,)).fetchall()
    for row in rows:
        audit(db, "lease_expired", row["id"], holder=row["holder"])


def public(row):
    result = {key: value for key, value in dict(row).items() if key != "credential"}
    result["intent"] = json.loads(result["intent"])
    return result


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def deadline(now, ttl_seconds):
    if type(ttl_seconds) is not int or not 0 < ttl_seconds <= ((2**63 - 1 - now) // 1000):
        raise Fault("INVALID_TTL", "Provide a positive TTL in seconds")
    return now + ttl_seconds * 1000


def acquire(devices, target, holder, task, ttl_seconds, intent, worktree=None, min_free_bytes=None):
    store = devices.store
    if not holder.strip() or not task.strip():
        raise Fault("INVALID_LEASE", "Holder and task are required")
    with store.transaction() as db:
        now = now_ms()
        end = deadline(now, ttl_seconds)
        device = store.device(db, target)
        expire(db, now)
        existing = db.execute("SELECT * FROM leases WHERE device_id = ? AND state = 'held'",
                              (device["id"],)).fetchone()
        if existing:
            raise Fault("LEASE_CONFLICT", "Device already held", lease_id=existing["id"],
                        holder=existing["holder"], expires_at_ms=existing["expires_at_ms"])
        if not device["enabled"]:
            raise Fault("DEVICE_DISABLED", "Device is disabled")
        current = devices.observation(device, max_age=15)
        if current["kind"] == "physical" and intent["operation"] != "inspect" and (
            current.get("transport") != "wired" or current.get("usb_present") is not True
        ):
            raise Fault("DEVICE_UNAVAILABLE", "Physical device requires a verified wired connection")
        if min_free_bytes is not None:
            metric = devices.device_metrics(current).get("disk_free", {})
            if metric.get("status") != "ok" or metric["value"] < min_free_bytes:
                raise Fault("CAPACITY_UNAVAILABLE", "Fresh free space does not meet the requested minimum")
        if current["reachability"] not in ("reachable", "needs_boot"):
            raise Fault("DEVICE_UNAVAILABLE", "Device is not currently usable",
                        reachability=current["reachability"])
        if not policies.check(device, **intent)["allowed"]:
            raise Fault("POLICY_DENIED", "Declared intent is outside policy")
        token, lease_id = secrets.token_urlsafe(32), str(uuid4())
        db.execute("""INSERT INTO leases
            (id, device_id, holder, task, worktree, intent, policy_revision, credential, expires_at_ms, state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'held')""",
                   (lease_id, device["id"], holder, task, worktree, json.dumps(intent),
                    device["revision"], digest(token), end))
        audit(db, "lease_acquired", lease_id, device_id=device["id"], holder=holder)
        return {**public(db.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()),
                "token": token, "locators": current["locators"]}


def change(store, lease_id, token, action, ttl_seconds=None, handoff=None):
    with store.transaction() as db:
        now = now_ms()
        row = db.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if not row or not hmac.compare_digest(row["credential"], digest(token)):
            raise Fault("INVALID_LEASE_CREDENTIAL", "Lease ID or token is invalid")
        expire(db, now)
        row = db.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if action == "renew":
            if row["state"] != "held":
                raise Fault("LEASE_NOT_ACTIVE", "Lease has ended", state=row["state"])
            db.execute("UPDATE leases SET expires_at_ms = ? WHERE id = ?",
                       (max(row["expires_at_ms"], deadline(now, ttl_seconds)), lease_id))
            audit(db, "lease_renewed", lease_id)
        elif action == "release" and row["state"] == "held":
            db.execute("UPDATE leases SET state = 'released', handoff = ? WHERE id = ?",
                       (handoff, lease_id))
            audit(db, "lease_released", lease_id)
        return public(db.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone())
