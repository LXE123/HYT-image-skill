"""Current structure dependencies; semantic facts are authored from evidence, not inferred here."""

import hashlib
import json
from pathlib import Path


def value_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def dependency_errors(state, required_ids, expected, version=None):
    lockset = state.get("identity_lockset", {})
    if lockset.get("status") != "READY":
        return ["structure state is not READY"]
    if not isinstance(required_ids, list) or not required_ids or len(set(required_ids)) != len(required_ids):
        return ["structure dependencies need unique required_lock_ids"]
    current = {x["lock_id"]: x for x in lockset.get("locks", [])}
    if not isinstance(expected, list) or [x.get("lock_id") for x in expected] != required_ids:
        return ["structure dependency binding is missing or incomplete"]
    failures = []
    for old in expected:
        key = old["lock_id"]
        live = current.get(key)
        if not live or live.get("status") != "LOCKED":
            failures.append(f"structure dependency unresolved: {key}")
        elif live != old:
            failures.append(f"structure dependency stale: {key}; revise affected task from current state")
    return failures


def contract_state_errors(root, contract):
    path = Path(root) / "PRODUCT_STATE.json"
    if not path.is_file():
        return ["current PRODUCT_STATE.json is missing"]
    state = json.loads(path.read_text())
    # Legacy contracts without a lock binding retain their previous review path.
    if "identity_lockset_version" not in contract and "resolved_identity_locks" not in contract:
        return []
    return dependency_errors(state, contract.get("required_lock_ids"), contract.get("resolved_identity_locks"), contract.get("identity_lockset_version"))


def structure_requirements(contract):
    result = {}
    for lock in contract.get("resolved_identity_locks", []):
        for relation in lock.get("relations", []):
            if relation.get("views") and contract.get("target_view") not in relation["views"]:
                continue
            result[f"{lock['lock_id']}:{relation['relation_id']}"] = relation
    return result


def observation_errors(contract, report):
    errors = []
    observations = report.get("structure_observations", {})
    for key in structure_requirements(contract):
        item = observations.get(key, {}) if isinstance(observations, dict) else {}
        if item.get("status") != "PASS" or not isinstance(item.get("observation"), str) or not item["observation"].strip():
            errors.append(f"QA structure relation unresolved: {key}")
    return errors
