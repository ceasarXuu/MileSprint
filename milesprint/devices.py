import json
from time import time
from uuid import UUID, uuid4

from . import discovery, leases, policies
from .storage import Fault, audit, now_ms


class Devices:
    def __init__(self, store):
        self.store = store
        self.rows = {}
        self.unverified = []
        self.health = {}
        self.metrics = {}

    def publish(self, rows, health):
        changes = {provider: sample["status"] for provider, sample in health.items()
                   if self.health.get(provider, {}).get("status") != sample["status"]
                   and (sample["status"] != "ok" or provider in self.health)}
        if changes:
            with self.store.transaction() as db:
                for provider, status in changes.items():
                    audit(db, "provider_status_changed", provider, status=status)
        self.health = health
        grouped = {}
        self.unverified = []
        for row in rows:
            identity = row["identity"]
            if identity:
                grouped.setdefault(identity, []).append(row)
            else:
                self.unverified.append(row)
        self.rows = {key: items[0] for key, items in grouped.items() if len(items) == 1}
        for items in grouped.values():
            if len(items) > 1:
                self.unverified.extend({**row, "identity": None, "reachability": "unknown"}
                                       for row in items)

    @staticmethod
    def resource_locator(row):
        locators = row["locators"]
        if row.get("platform") == "android":
            return (locators.get("adb_serial"), locators.get("adb_transport_id"))
        return locators.get("usb_udid")

    def publish_resources(self, samples):
        self.metrics = {key: (self.resource_locator(row), metrics)
                        for key, row, metrics in samples}

    def device_metrics(self, observation):
        locator, metrics = self.metrics.get(observation["identity"], (None, {}))
        if locator != self.resource_locator(observation) or (
            observation["kind"] == "physical" and not observation.get("usb_present")
        ):
            return {}
        return {key: ({**metric, "status": "stale"} if metric["status"] == "ok" and
                      (time() - metric["observed_at"] > 120 or observation["reachability"] == "unknown")
                      else metric) for key, metric in metrics.items()}

    def observation(self, device, max_age=45):
        current = self.rows.get(device["identity"])
        if current and time() - current["observed_at"] <= max_age:
            return current
        saved = current or json.loads(device["observation"])
        return {**saved, "platform": saved.get("platform", "ios"), "reachability": "unknown", "boot_state": None,
                "connection": None, "transport": None, "usb_present": None,
                "locators": {key: value for key, value in saved["locators"].items()
                             if key not in {"usb_udid", "adb_serial", "adb_transport_id"}}}

    def view(self, db, device, at_ms=None):
        observation = self.observation(device)
        metrics = self.device_metrics(observation)
        held = db.execute("""SELECT id, holder, task, expires_at_ms FROM leases
                            WHERE device_id = ? AND state = 'held' AND expires_at_ms > ?""",
                          (device["id"], now_ms() if at_ms is None else at_ms)).fetchone()
        return {**observation, "id": device["id"], "alias": device["alias"],
                "enabled": bool(device["enabled"]), "metrics": metrics, "allocation": {"state": "held", **dict(held)} if held else
                {"state": "free"}, "policy": {"device_ceiling": device["ceiling"],
                "default_app_policy": "resettable", "app_overrides": json.loads(device["overrides"]),
                "revision": device["revision"]}}

    def list(self, kind=None, registered=None, platform=None):
        with self.store.transaction(read_only=True) as db:
            at_ms = now_ms()
            saved = {row["identity"]: row for row in db.execute("SELECT * FROM devices ORDER BY alias")}
            rows = []
            if registered is not False:
                rows.extend(self.view(db, row, at_ms) for row in saved.values())
            if registered is not True:
                rows.extend({**row, "id": None} for row in [*self.rows.values(), *self.unverified]
                            if row["identity"] not in saved)
            return [row for row in rows if (not kind or row["kind"] == kind)
                    and (not platform or row.get("platform", "ios") == platform)]

    def get(self, target):
        with self.store.transaction() as db:
            leases.expire(db, now_ms())
            return self.view(db, self.store.device(db, target))

    def register(self, identity, alias, ceiling):
        current = self.rows.get(identity)
        if not current or time() - current["observed_at"] > 45:
            raise Fault("IDENTITY_UNVERIFIED", "Refresh the device list and use a verified identity")
        if not alias.strip():
            raise Fault("INVALID_ALIAS", "Provide a non-empty alias")
        try:
            uuid_alias = str(UUID(alias))
        except ValueError:
            uuid_alias = None
        if uuid_alias:
            raise Fault("INVALID_ALIAS", "UUID aliases are reserved for internal IDs")
        policies.validate(ceiling, current["kind"])
        with self.store.transaction() as db:
            if db.execute("SELECT 1 FROM devices WHERE identity = ? OR alias = ?",
                          (identity, alias)).fetchone():
                raise Fault("DEVICE_ALREADY_REGISTERED", "Identity or alias is already registered")
            device_id = str(uuid4())
            db.execute("""INSERT INTO devices (id, alias, identity, observation, ceiling, overrides)
                          VALUES (?, ?, ?, ?, ?, '{}')""",
                       (device_id, alias, identity, json.dumps(current), ceiling))
            audit(db, "device_registered", device_id, alias=alias)
            return self.view(db, self.store.device(db, device_id))

    def set_policy(self, target, ceiling, bundle_id, app_policy):
        with self.store.transaction() as db:
            leases.expire(db, now_ms())
            row = self.store.device(db, target)
            if db.execute("SELECT 1 FROM leases WHERE device_id = ? AND state = 'held'",
                          (row["id"],)).fetchone():
                raise Fault("DEVICE_BUSY", "Release the active lease before editing policy")
            policies.validate(ceiling, json.loads(row["observation"])["kind"], bundle_id, app_policy)
            overrides = json.loads(row["overrides"])
            if bundle_id is not None:
                overrides[bundle_id] = app_policy
            db.execute("UPDATE devices SET ceiling = ?, overrides = ?, revision = revision + 1 WHERE id = ?",
                       (ceiling, json.dumps(overrides), row["id"]))
            audit(db, "policy_changed", row["id"], revision=row["revision"] + 1)
            return self.view(db, self.store.device(db, row["id"]))

    def check_policy(self, target, **intent):
        with self.store.transaction() as db:
            return policies.check(self.store.device(db, target), **intent)

    def set_enabled(self, target, enabled):
        with self.store.transaction() as db:
            leases.expire(db, now_ms())
            row = self.store.device(db, target)
            db.execute("UPDATE devices SET enabled = ? WHERE id = ?", (enabled, row["id"]))
            audit(db, "device_enabled" if enabled else "device_disabled", row["id"])
            return self.view(db, self.store.device(db, row["id"]))
