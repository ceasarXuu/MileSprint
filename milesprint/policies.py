"""Policy decisions on declared scope. Receipts are external references."""
import json
import re

from .storage import Fault

LEVELS = ("preserve", "owned_only", "resettable")
BUNDLE_ID = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*")


def valid_bundle(value):
    return bool(value and BUNDLE_ID.fullmatch(value))


def validate(ceiling, kind, bundle_id=None, app_policy=None):
    if ceiling not in ("app_scoped", "device_resettable"):
        raise Fault("INVALID_POLICY", "Unknown device ceiling")
    if ceiling == "device_resettable" and kind != "simulator":
        raise Fault("INVALID_POLICY", "Only existing simulators can have a device reset ceiling")
    if (bundle_id is None) != (app_policy is None) or (
        app_policy is not None and (app_policy not in LEVELS or not valid_bundle(bundle_id))
    ):
        raise Fault("INVALID_POLICY", "Provide both a bundle ID and a valid app policy")


def check(device, bundle_id, operation, data_scope, receipt=None):
    overrides = json.loads(device["overrides"])
    policy = overrides.get(bundle_id, "resettable")
    if data_scope == "device" and operation == "reset_device":
        allowed = (device["ceiling"] == "device_resettable" and bundle_id is None
                   and all(level == "resettable" for level in overrides.values()))
    elif data_scope == "app_local" and valid_bundle(bundle_id):
        allowed = (
            operation in {"inspect", "launch", "install_preserving"} or
            (operation == "write_owned" and
             (policy == "resettable" or policy == "owned_only" and bool(receipt and receipt.strip()))) or
            (operation in {"reset_app", "uninstall_app"} and policy == "resettable")
        )
    else:
        allowed = False
    reason = "declared_scope_allowed" if allowed else "scope_or_operation_not_allowed"
    if data_scope in {"cloud", "photos", "system", "other_app"}:
        reason = "external_authorization_required"
    return {"allowed": allowed, "app_policy": policy, "device_ceiling": device["ceiling"],
            "revision": device["revision"],
            "reason": reason}
