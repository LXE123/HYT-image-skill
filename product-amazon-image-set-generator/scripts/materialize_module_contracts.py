#!/usr/bin/env python3
"""Materialize immutable Run Control contracts from an approved visual-set plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from set_common import SAFE_ID, compile_prompt, load_json, module_quality_errors, plan_modules, resolve_file, sha256, update_product_summary, write_json
from design_store import resolve_design
from structure_state import dependency_errors
from execution_policy import policy_errors


STYLE_SCOPE = {
    "STYLE_REFERENCE": "STYLE_ONLY",
    "COMPETITOR_REFERENCE": "MARKET_STYLE_ONLY",
    "BRAND_GUIDELINE": "BRAND_SYSTEM_ONLY",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--set-id", required=True)
    parser.add_argument("--module-id")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--correction", default="", help="one current corrective instruction, at most 300 characters")
    args = parser.parse_args()
    if not SAFE_ID.fullmatch(args.set_id):
        parser.error("set-id must use letters, digits, dots, underscores, or hyphens")
    if args.module_id and not SAFE_ID.fullmatch(args.module_id):
        parser.error("module-id must use letters, digits, dots, underscores, or hyphens")
    if not 1 <= args.attempt <= 3 or len(args.correction) > 300:
        parser.error("attempt must be 1-3; correction must be <=300 characters")
    if args.attempt > 1 and (not args.module_id or not args.correction.strip()):
        parser.error("a retry requires one module-id and one concrete correction")

    root = args.package.resolve()
    set_root = root / "visual_sets" / args.set_id
    plan_path = set_root / "SET_PLAN.json"
    state_path = set_root / "SET_STATE.json"
    try:
        product_state = load_json(root / "PRODUCT_STATE.json")
        plan = load_json(plan_path)
        set_state = load_json(state_path)
        snapshot_path = resolve_file(root, plan.get("input_snapshot"))
        snapshot = load_json(snapshot_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(f"cannot read set records: {error}")

    if plan.get("status") != "APPROVED":
        parser.error("set plan must be APPROVED")
    if set_state.get("status") not in {"PLAN_APPROVED", "MODULE_CONTRACTS_READY", "MODULES_GENERATING", "SET_REVIEW", "BLOCKED", "COMPLETE"}:
        parser.error(f"set state {set_state.get('status')} cannot materialize contracts")
    current_plan_hash = sha256(plan_path)
    if current_plan_hash != set_state.get("plan_sha256"):
        parser.error("approved set plan changed after approval")
    current_snapshot_hash = sha256(snapshot_path)
    if current_snapshot_hash != set_state.get("input_snapshot_sha256") or current_snapshot_hash != plan.get("approved_input_snapshot_sha256"):
        parser.error("input snapshot changed after approval")
    if sha256(root / "index.json") != snapshot.get("reference_snapshot", {}).get("index_sha256"):
        parser.error("current index.json differs from the approved input snapshot")
    lockset = product_state.get("identity_lockset", {})
    if lockset.get("status") != "READY":
        parser.error("current identity lockset differs from the approved plan")

    modules = plan.get("modules", [])
    try:
        selected = plan_modules(root, plan, args.module_id)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    if not selected:
        parser.error("selected module does not exist in the approved plan")
    package_index = load_json(root / "index.json")
    locks = {x.get("lock_id"): x for x in lockset.get("locks", []) if isinstance(x, dict)}
    pinned_locks = {x["lock_id"]: x for x in snapshot["identity_lockset"]["locks"]}
    for module in selected:
        ids = module["required_lock_ids"]
        failures = dependency_errors(product_state, ids, [pinned_locks[x] for x in ids if x in pinned_locks])
        if failures:
            parser.error("; ".join(failures))
        if plan.get("design_policy_version"):
            try:
                resolve_design(root, plan, module)
            except (OSError, ValueError, KeyError, TypeError) as error:
                parser.error(str(error))
        quality_errors = module_quality_errors(root, module, package_index, locks)
        quality_errors.extend(policy_errors(module, generation=True))
        if quality_errors:
            parser.error(f"module {module['module_id']} needs a revised plan: {'; '.join(quality_errors)}")
    source_map = {
        item.get("source_id"): item
        for item in snapshot.get("commercial_manifest", {}).get("sources", [])
        if isinstance(item, dict)
    }
    candidate_map = {
        item.get("candidate_id"): item
        for item in snapshot.get("accepted_outputs", [])
        if isinstance(item, dict)
    }
    module_states = {
        item.get("module_id"): item
        for item in set_state.get("modules", [])
        if isinstance(item, dict) and item.get("module_id")
    }
    runs = product_state.setdefault("runs", [])
    if not isinstance(runs, list):
        parser.error("PRODUCT_STATE.json runs must be an array")

    for module in selected:
        module_id = module["module_id"]
        previous = module_states.get(module_id, {})
        active_attempt = previous.get("attempt", 1)
        if args.attempt < active_attempt:
            print(f"SKIP  later attempt already active: {module_id}")
            continue
        if args.attempt > active_attempt:
            candidate = next((x for x in product_state.get("candidates", []) if x.get("candidate_id") == previous.get("candidate_id")), {})
            if args.attempt != active_attempt + 1 or not str(candidate.get("status", "")).startswith("REJECTED"):
                parser.error("retry requires the immediately preceding candidate to be recorded as REJECTED")
        run_id = f"{args.set_id}-{module_id}" + (f"-a{args.attempt:02d}" if args.attempt > 1 else "")
        target_view = module["target_view"]
        candidate_id = f"{run_id}-{target_view}"
        if not SAFE_ID.fullmatch(run_id) or not SAFE_ID.fullmatch(candidate_id):
            parser.error(f"derived run or candidate ID is too long or unsafe for module {module_id}")
        output_format = module["output_requirements"]["format"].lower()
        if not SAFE_ID.fullmatch(output_format):
            parser.error(f"module {module_id} output format is unsafe")
        relative_contract = f"runs/{run_id}/{target_view}_generation_contract.json"
        contract_path = root / relative_contract
        output_path = f"candidates/inbox/{run_id}/{candidate_id}.{output_format}"

        style_references = []
        for source_id in module.get("style_source_ids", []):
            source = source_map[source_id]
            source_path = resolve_file(root, source.get("path"))
            style_references.append({
                "source_id": source_id,
                "path": source["path"],
                "sha256": sha256(source_path),
                "role": source["role"],
                "usage_scope": STYLE_SCOPE[source["role"]],
            })
        prior_references = []
        for prior_candidate_id in module.get("prior_candidate_ids", []):
            candidate = candidate_map[prior_candidate_id]
            prior_references.append({
                "candidate_id": prior_candidate_id,
                "path": candidate["path"],
                "sha256": candidate["sha256"],
                "status": candidate["status"],
                "source_contract": candidate["source_contract"],
                "usage_scope": candidate["usage_scope"],
            })
        contract = {
            "schema_version": 2,
            "run_id": run_id,
            "candidate_id": candidate_id,
            "sku": plan["sku"],
            "target_view": target_view,
            "identity_lockset_version": snapshot["identity_lockset"]["version"],
            "required_lock_ids": module["required_lock_ids"],
            "resolved_identity_locks": [locks[x] for x in module["required_lock_ids"]],
            "references": [*module.get("product_references", []), *module.get("pose_references", [])],
            "prior_candidate_references": prior_references,
            "style_references": style_references,
            "visual_system": plan.get("visual_system", {}),
            "visual_invariants": module.get("visual_invariants", []),
            "forbidden_changes": module.get("forbidden_changes", []),
            "copy": module.get("copy", {}),
            "claim_ids": module.get("claim_ids", []),
            "claim_decisions": [x for x in plan.get("claims", []) if x.get("claim_id") in module.get("claim_ids", [])],
            "generation_template": module["generation_template"],
            "quality_contract": module["quality_contract"],
            "output_requirements": module["output_requirements"],
            "output_path": output_path,
            "visual_set": {
                "set_id": args.set_id,
                "module_id": module_id,
                "channel": module["channel"],
                "sequence": module["sequence"],
                "plan_revision": plan["plan_revision"],
                "plan_sha256": current_plan_hash,
            },
        }
        if "execution_policy" in module:
            contract["execution_policy"] = module["execution_policy"]
        if plan.get("creative_policy_version") == 1:
            contract["creative_brief"] = module.get("creative_brief")
        if plan.get("design_policy_version"):
            contract["design_recipe"] = resolve_design(root, plan, module)
        contract["generation_prompt"] = compile_prompt(contract)
        if plan.get("schema_version", 1) >= 2:
            contract = {k: contract[k] for k in ("schema_version", "run_id", "candidate_id", "sku", "target_view", "identity_lockset_version", "output_path", "visual_set")}
            contract.update({
                "storage_mode": "REFERENCED", "attempt": args.attempt,
                "correction": args.correction,
                "bindings": {
                    "plan": {"path": plan_path.relative_to(root).as_posix(), "sha256": current_plan_hash},
                },
            })
        elif args.attempt > 1:
            contract["attempt"] = args.attempt
            contract["correction"] = args.correction
        if contract_path.exists():
            try:
                existing = load_json(contract_path)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                parser.error(f"cannot read existing contract {relative_contract}: {error}")
            linkage = existing.get("visual_set", {})
            if linkage.get("module_id") != module_id or linkage.get("plan_sha256") != current_plan_hash:
                parser.error(f"existing contract conflicts with approved module {module_id}; it was not overwritten")
            if existing.get("correction", "") != args.correction:
                parser.error("existing retry contract has a different correction; it was not overwritten")
            print(f"SKIP  contract already exists: {relative_contract}")
        else:
            write_json(contract_path, contract)
            print(f"CREATE  module contract: {relative_contract}")

        for relative in (
            f"candidates/inbox/{run_id}",
            f"candidates/rejected/{run_id}",
            "candidates/accepted",
            f"outputs/{run_id}",
        ):
            (root / relative).mkdir(parents=True, exist_ok=True)
        run = next((item for item in runs if isinstance(item, dict) and item.get("run_id") == run_id), None)
        if run is None:
            runs.append({
                "run_id": run_id,
                "sku": plan["sku"],
                "views": [target_view],
                "status": "CONTRACT_DRAFT",
                "contracts": [relative_contract],
                "visual_set": {"set_id": args.set_id, "module_id": module_id},
            })
        elif relative_contract not in run.get("contracts", []):
            parser.error(f"existing run {run_id} does not own the expected contract")
        record = module_states.setdefault(module_id, {"module_id": module_id})
        if record.get("contract_path") != relative_contract:
            if record.get("contract_path"):
                record.setdefault("attempt_history", []).append({k: record[k] for k in ("attempt", "candidate_id", "contract_path", "status") if k in record})
            record.pop("accepted_output", None)
            record.pop("block_reason", None)
            record.update({"status": "CONTRACT_CREATED", "run_id": run_id, "candidate_id": candidate_id, "contract_path": relative_contract, "attempt": args.attempt})

    ordered_states = []
    for module in modules:
        module_id = module["module_id"]
        ordered_states.append(module_states.get(module_id, {"module_id": module_id, "status": "PLANNED"}))
    set_state["modules"] = ordered_states
    if set_state.get("status") in {"SET_REVIEW", "COMPLETE", "BLOCKED", "MODULES_GENERATING"}:
        pass  # Synchronization derives actual progress; rematerialization never resets decisions.
    elif all(item.get("contract_path") for item in ordered_states):
        set_state["status"] = "MODULE_CONTRACTS_READY"
    else:
        set_state["status"] = "PLAN_APPROVED"
    set_state["next_action"] = "ACTIVATE_AND_PREFLIGHT_MODULE_CONTRACT"
    write_json(state_path, set_state)
    update_product_summary(product_state, set_state)
    write_json(root / "PRODUCT_STATE.json", product_state)
    print(f"UPDATE  set state: {set_state['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
