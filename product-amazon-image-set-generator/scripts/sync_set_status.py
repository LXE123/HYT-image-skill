#!/usr/bin/env python3
"""Synchronize visual-set module status from actual Run Control candidate decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from set_common import SAFE_ID, compile_prompt, load_contract, load_json, plan_modules, qa_errors, resolve_file, sha256, update_product_summary, validate_quality, write_json


from structure_state import dependency_errors
from execution_policy import policy_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--set-id", required=True)
    args = parser.parse_args()
    if not SAFE_ID.fullmatch(args.set_id):
        parser.error("set-id must use letters, digits, dots, underscores, or hyphens")

    root = args.package.resolve()
    set_root = root / "visual_sets" / args.set_id
    try:
        product_state = load_json(root / "PRODUCT_STATE.json")
        plan = load_json(set_root / "SET_PLAN.json")
        set_state = load_json(set_root / "SET_STATE.json")
        package_index = load_json(root / "index.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(f"cannot read set records: {error}")
    if set_state.get("plan_sha256") and sha256(set_root / "SET_PLAN.json") != set_state.get("plan_sha256"):
        parser.error("approved set plan changed; synchronize only after creating a revision")
    sources_changed = False
    if plan.get("status") == "APPROVED":
        try:
            snapshot_path = resolve_file(root, plan.get("input_snapshot"))
            snapshot = load_json(snapshot_path)
            current_locks = product_state.get("identity_lockset", {})
            sources_changed = (
                sha256(snapshot_path) != plan.get("approved_input_snapshot_sha256")
                or sha256(root / "index.json") != snapshot.get("reference_snapshot", {}).get("index_sha256")
                or current_locks.get("status") != "READY"
                or product_state.get("workflow", {}).get("status") == "REFERENCE_CHANGED"
            )
        except (OSError, ValueError, KeyError):
            sources_changed = True

    candidates = {
        item.get("candidate_id"): item
        for item in product_state.get("candidates", [])
        if isinstance(item, dict) and item.get("candidate_id")
    }
    required = {
        item.get("module_id"): item.get("required", True)
        for item in plan.get("modules", [])
        if isinstance(item, dict)
    }
    states = []
    records = {x.get("module_id"): x for x in set_state.get("modules", []) if isinstance(x, dict)}
    # The approved plan, rather than an incomplete status array, defines completeness.
    for module in plan.get("modules", []):
        record = records.get(module["module_id"], {"module_id": module["module_id"]})
        updated = dict(record)
        updated.pop("accepted_output", None)
        updated.pop("block_reason", None)
        candidate = candidates.get(record.get("candidate_id"))
        if candidate is None:
            updated["status"] = "CONTRACT_CREATED" if record.get("contract_path") else "PLANNED"
            updated.pop("accepted_output", None)
        else:
            decision = candidate.get("status")
            if decision == "ACCEPTED":
                try:
                    candidate_file = resolve_file(root, candidate.get("path"))
                except ValueError:
                    updated["status"] = "BLOCKED"
                    updated["block_reason"] = "accepted_candidate_file_missing_or_unsafe"
                else:
                    actual_hash = sha256(candidate_file)
                    if candidate.get("sha256") != actual_hash:
                        updated["status"] = "BLOCKED"
                        updated["block_reason"] = "accepted_candidate_hash_mismatch"
                    else:
                        try:
                            contract_path = resolve_file(root, record.get("contract_path"))
                            contract = load_contract(root, contract_path)
                            if candidate.get("source_contract") != record.get("contract_path") or contract.get("candidate_id") != candidate.get("candidate_id") or contract.get("visual_set", {}).get("plan_sha256") != set_state.get("plan_sha256"):
                                raise ValueError("candidate/contract/approved-plan linkage mismatch")
                            lockset = product_state.get("identity_lockset", {})
                            locks = {x.get("lock_id"): x for x in lockset.get("locks", []) if isinstance(x, dict)}
                            failures = validate_quality(root, contract, package_index, locks)
                            failures.extend(dependency_errors(product_state, contract.get("required_lock_ids"), contract.get("resolved_identity_locks")))
                            resolved_module = plan_modules(root, plan, module["module_id"])[0]
                            for key in ("generation_template", "quality_contract"):
                                if contract.get(key) != resolved_module.get(key):
                                    failures.append(f"contract {key} differs from the approved module")
                            if failures:
                                raise ValueError("; ".join(failures))
                            if contract.get("generation_prompt") != compile_prompt(contract):
                                raise ValueError("compiled generation prompt differs from contract")
                            report_path = resolve_file(root, candidate.get("checks", {}).get("visual", {}).get("report_path"))
                            report = load_json(report_path)
                            failures = qa_errors(root, contract, contract_path, candidate, report)
                            if failures:
                                raise ValueError("; ".join(failures))
                        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                            updated["status"] = "BLOCKED"
                            updated["block_reason"] = f"visual_qa_required:{error}"
                        else:
                            updated["status"] = "ACCEPTED"
                            updated["accepted_output"] = {"path": candidate["path"], "sha256": actual_hash, "qa_report_path": report_path.relative_to(root).as_posix(), "qa_report_sha256": sha256(report_path)}
            elif decision == "HUMAN_STRUCTURE_REVIEW_PASSED":
                updated["status"] = "STRUCTURE_REVIEW_PASSED"
            elif decision == "PENDING_REVIEW":
                updated["status"] = "REVIEW_REQUIRED"
            elif isinstance(decision, str) and decision.startswith("REJECTED"):
                updated["status"] = "REJECTED"
            else:
                updated["status"] = "REVIEW_REQUIRED"
        if not sources_changed and plan.get("status") == "APPROVED":
            try:
                spec = plan_modules(root, plan, module["module_id"])[0]
                ids = spec["required_lock_ids"]
                old = {x["lock_id"]: x for x in snapshot["identity_lockset"]["locks"]}
                failures = dependency_errors(product_state, ids, [old[x] for x in ids if x in old])
                failures.extend(policy_errors(spec, generation=True))
            except (OSError, ValueError, KeyError) as error:
                failures = [str(error)]
            if failures:
                updated["status"] = "BLOCKED"
                updated.pop("accepted_output", None)
                updated["block_reason"] = "; ".join(failures)
        states.append(updated)

    set_state["modules"] = states
    required_states = [item.get("status") for item in states if required.get(item.get("module_id"), True)]
    set_state.pop("block_reason", None)
    if sources_changed:
        set_state["status"] = "BLOCKED"
        set_state["block_reason"] = "SET_SOURCES_CHANGED"
        set_state["next_action"] = "RECONCILE_REFERENCE_CHANGE"
    elif plan.get("status") == "APPROVED" and set_state.get("plan_sha256") and required_states and all(status == "ACCEPTED" for status in required_states):
        set_state["status"] = "COMPLETE"
        set_state["next_action"] = "NONE"
    elif any(status == "BLOCKED" for status in required_states):
        set_state["status"] = "BLOCKED"
        set_state["next_action"] = "RESOLVE_BLOCKED_MODULE"
    elif any(status in {"REVIEW_REQUIRED", "STRUCTURE_REVIEW_PASSED"} for status in required_states):
        set_state["status"] = "SET_REVIEW"
        set_state["next_action"] = "COMPLETE_MODULE_REVIEWS"
    elif any(status == "REJECTED" for status in required_states):
        set_state["status"] = "MODULES_GENERATING"
        set_state["next_action"] = "REGENERATE_REJECTED_MODULES"
    elif any(status == "CONTRACT_CREATED" for status in required_states):
        set_state["status"] = "MODULES_GENERATING"
        set_state["next_action"] = "GENERATE_NEXT_MODULE"
    elif set_state.get("status") not in {"SET_PLAN_DRAFT", "PLAN_APPROVED"}:
        set_state["status"] = "MODULE_CONTRACTS_READY"
        set_state["next_action"] = "MATERIALIZE_OR_ACTIVATE_MODULE_CONTRACT"

    write_json(set_root / "SET_STATE.json", set_state)
    update_product_summary(product_state, set_state)
    write_json(root / "PRODUCT_STATE.json", product_state)
    counts: dict[str, int] = {}
    for item in states:
        counts[item.get("status", "UNKNOWN")] = counts.get(item.get("status", "UNKNOWN"), 0) + 1
    print(f"SYNC  set={args.set_id} status={set_state['status']} modules={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
