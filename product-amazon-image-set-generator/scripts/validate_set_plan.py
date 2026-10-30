#!/usr/bin/env python3
"""Validate an Amazon visual-set plan and optionally approve its exact snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from set_common import SAFE_ID, generation_mode_errors, load_json, module_quality_errors, plan_modules, resolve_file, sha256, write_json
from project_store import transaction
from gallery_review import review_policy_errors
from a_plus_layout import layout_errors
from quality_rules import creative_brief_errors
from design_store import design_plan_checks


CHANNELS = {"AMAZON_GALLERY", "PREMIUM_A_PLUS"}
CLAIM_STATUSES = {"VERIFIED", "SUPPORTED_WITH_CAUTION", "NEEDS_PROOF", "DO_NOT_USE"}
STYLE_ROLES = {"STYLE_REFERENCE", "COMPETITOR_REFERENCE", "BRAND_GUIDELINE"}
REFERENCE_SCOPES = {
    "PRODUCT_EVIDENCE": "PRODUCT_IDENTITY_ONLY",
    "POSE_ONLY": "POSE_CAMERA_COMPOSITION_LIGHTING_BACKGROUND_ONLY",
}


def append_reference_errors(root: Path, refs: object, expected_role: str, label: str, errors: list[str]) -> None:
    if not isinstance(refs, list):
        errors.append(f"{label} must be an array")
        return
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        if ref.get("role") != expected_role or ref.get("usage_scope") != REFERENCE_SCOPES[expected_role]:
            errors.append(f"{label}[{index}] has an invalid role or usage_scope")
        try:
            resolve_file(root, ref.get("path"))
        except ValueError as error:
            errors.append(f"{label}[{index}]: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--set-id", required=True)
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    with transaction(args.package):
        return execute(args, parser)


def execute(args, parser):
    if not SAFE_ID.fullmatch(args.set_id):
        parser.error("set-id must use letters, digits, dots, underscores, or hyphens")

    root = args.package.resolve()
    set_root = root / "visual_sets" / args.set_id
    plan_path = set_root / "SET_PLAN.json"
    state_path = set_root / "SET_STATE.json"
    errors: list[str] = []
    warnings: list[str] = []
    try:
        product_state = load_json(root / "PRODUCT_STATE.json")
        plan = load_json(plan_path)
        set_state = load_json(state_path)
        snapshot_path = resolve_file(root, plan.get("input_snapshot"))
        snapshot = load_json(snapshot_path)
        package_index = load_json(root / "index.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(f"cannot read set records: {error}")

    if plan.get("set_id") != args.set_id or set_state.get("set_id") != args.set_id or snapshot.get("set_id") != args.set_id:
        errors.append("set_id differs across plan, state, or input snapshot")
    if plan.get("sku") != product_state.get("sku") or snapshot.get("sku") != product_state.get("sku"):
        errors.append("SKU differs from current PRODUCT_STATE.json")
    if plan.get("marketplace") != set_state.get("marketplace") or plan.get("marketplace") != snapshot.get("marketplace"):
        errors.append("marketplace differs across plan, state, or input snapshot")
    if plan.get("status") not in {"DRAFT", "APPROVED"}:
        errors.append("plan status must be DRAFT or APPROVED")
    if args.approve and plan.get("status") != "DRAFT":
        errors.append("only a DRAFT plan can be approved; create a revision instead")
    errors.extend(generation_mode_errors(plan))
    errors.extend(review_policy_errors(plan))
    if not isinstance(plan.get("positioning"), str) or not plan["positioning"].strip():
        errors.append("positioning must be completed before approval")
    audience = plan.get("audience")
    if not isinstance(audience, dict):
        errors.append("audience must be an object")
    else:
        for key in ("primary", "motivation"):
            if not isinstance(audience.get(key), str) or not audience[key].strip():
                errors.append(f"audience.{key} must be completed before approval")
    selling_points = plan.get("selling_points")
    if not isinstance(selling_points, dict):
        errors.append("selling_points must be an object")
    else:
        for tier in ("s_tier", "a_tier", "b_tier"):
            if not isinstance(selling_points.get(tier), list):
                errors.append(f"selling_points.{tier} must be an array")
        if not selling_points.get("s_tier"):
            errors.append("selling_points.s_tier needs at least one supported priority")
    visual_system = plan.get("visual_system")
    if not isinstance(visual_system, dict):
        errors.append("visual_system must be an object")
    else:
        for key in ("direction", "palette", "lighting", "composition", "retouching", "forbidden_cues"):
            value = visual_system.get(key)
            if value in (None, "", []):
                errors.append(f"visual_system.{key} must be completed before approval")

    actual_snapshot_hash = sha256(snapshot_path)
    if set_state.get("input_snapshot_sha256") != actual_snapshot_hash:
        errors.append("input snapshot changed after set initialization")
    if "path" in snapshot.get("design_brief", {}):
        # Older sets copied the brief; preserve their integrity check on resume.
        try:
            brief_ref = snapshot["design_brief"]
            if sha256(resolve_file(root, brief_ref.get("path"))) != brief_ref.get("sha256"):
                errors.append("imported design brief changed after initialization")
        except (ValueError, TypeError, AttributeError) as error:
            errors.append(f"invalid design brief snapshot: {error}")
    reference = snapshot.get("reference_snapshot", {})
    index_path = root / "index.json"
    if not index_path.is_file():
        errors.append("index.json is missing")
    else:
        current_index_hash = sha256(index_path)
        if reference.get("index_sha256") != current_index_hash:
            errors.append("input snapshot no longer matches current index.json")
        if product_state.get("reference_package", {}).get("sha256") != current_index_hash:
            errors.append("current index.json has not been validated into PRODUCT_STATE.json")
    lockset = product_state.get("identity_lockset", {})
    if lockset.get("status") != "READY":
        errors.append("current identity lockset is not READY")
    if reference.get("identity_lockset_version") != lockset.get("version"):
        errors.append("input snapshot lockset version is stale")
    locks = {item.get("lock_id"): item for item in lockset.get("locks", []) if isinstance(item, dict)}

    claims = plan.get("claims")
    claim_map: dict[str, dict] = {}
    if not isinstance(claims, list):
        errors.append("claims must be an array")
        claims = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict) or not SAFE_ID.fullmatch(str(claim.get("claim_id", ""))):
            errors.append(f"claims[{index}] needs a safe claim_id")
            continue
        claim_id = claim["claim_id"]
        if claim_id in claim_map:
            errors.append(f"duplicate claim_id: {claim_id}")
            continue
        claim_map[claim_id] = claim
        if not isinstance(claim.get("claim"), str) or not claim["claim"].strip():
            errors.append(f"claim {claim_id} needs claim text")
        if claim.get("status") not in CLAIM_STATUSES:
            errors.append(f"claim {claim_id} has an invalid status")
        evidence_paths = claim.get("evidence_paths")
        if not isinstance(evidence_paths, list):
            errors.append(f"claim {claim_id} evidence_paths must be an array")
        else:
            if claim.get("status") == "VERIFIED" and not evidence_paths:
                errors.append(f"VERIFIED claim {claim_id} needs evidence_paths")
            for evidence_path in evidence_paths:
                try:
                    resolve_file(root, evidence_path)
                except ValueError as error:
                    errors.append(f"claim {claim_id}: {error}")
        if not isinstance(claim.get("allowed_wording"), str):
            errors.append(f"claim {claim_id} allowed_wording must be a string")
        elif claim.get("status") in {"VERIFIED", "SUPPORTED_WITH_CAUTION"} and not claim["allowed_wording"].strip():
            errors.append(f"usable claim {claim_id} needs allowed_wording")

    commercial_sources = snapshot.get("commercial_manifest", {}).get("sources", [])
    source_map = {item.get("source_id"): item for item in commercial_sources if isinstance(item, dict)}
    accepted_outputs = snapshot.get("accepted_outputs", [])
    candidate_map = {item.get("candidate_id"): item for item in accepted_outputs if isinstance(item, dict)}

    try:
        modules = plan_modules(root, plan)
    except (OSError, ValueError, KeyError) as error:
        errors.append(str(error))
        modules = []
    module_ids: set[str] = set()
    sequence_keys: set[tuple[str, int]] = set()
    previous_views: dict[str, list[str]] = {}
    if not isinstance(modules, list) or not modules:
        errors.append("modules must be a non-empty array")
        modules = []
    for index, module in enumerate(modules):
        label = f"modules[{index}]"
        if not isinstance(module, dict) or not SAFE_ID.fullmatch(str(module.get("module_id", ""))):
            errors.append(f"{label} needs a safe module_id")
            continue
        module_id = module["module_id"]
        if module_id in module_ids:
            errors.append(f"duplicate module_id: {module_id}")
        module_ids.add(module_id)
        channel = module.get("channel")
        sequence = module.get("sequence")
        if channel not in CHANNELS:
            errors.append(f"module {module_id} has an invalid channel")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            errors.append(f"module {module_id} sequence must be a positive integer")
        elif channel in CHANNELS:
            key = (channel, sequence)
            if key in sequence_keys:
                errors.append(f"duplicate sequence {sequence} in {channel}")
            sequence_keys.add(key)
        if not isinstance(module.get("required"), bool):
            errors.append(f"module {module_id} required must be boolean")
        if module.get("required"):
            for key in ("sales_task", "buyer_question"):
                if not isinstance(module.get(key), str) or not module[key].strip():
                    errors.append(f"required module {module_id} needs {key}")
        target_view = module.get("target_view")
        if not isinstance(target_view, str) or not SAFE_ID.fullmatch(target_view):
            errors.append(f"module {module_id} needs a safe target_view")
        elif channel in CHANNELS:
            previous_views.setdefault(channel, []).append(target_view)

        append_reference_errors(root, module.get("product_references"), "PRODUCT_EVIDENCE", f"module {module_id} product_references", errors)
        append_reference_errors(root, module.get("pose_references"), "POSE_ONLY", f"module {module_id} pose_references", errors)
        if module.get("required") and not module.get("product_references"):
            errors.append(f"required module {module_id} needs at least one product reference")

        required_lock_ids = module.get("required_lock_ids")
        if not isinstance(required_lock_ids, list) or (module.get("required") and not required_lock_ids):
            errors.append(f"required module {module_id} needs required_lock_ids")
        else:
            for lock_id in required_lock_ids:
                lock = locks.get(lock_id)
                if not isinstance(lock, dict) or lock.get("status") != "LOCKED":
                    errors.append(f"module {module_id} references unavailable lock {lock_id}")

        claim_ids = module.get("claim_ids")
        if not isinstance(claim_ids, list):
            errors.append(f"module {module_id} claim_ids must be an array")
        else:
            for claim_id in claim_ids:
                claim = claim_map.get(claim_id)
                if claim is None:
                    errors.append(f"module {module_id} references unknown claim {claim_id}")
                elif claim.get("status") in {"NEEDS_PROOF", "DO_NOT_USE"}:
                    errors.append(f"module {module_id} uses blocked claim {claim_id}")
        copy_text = json.dumps(module.get("copy", {}), ensure_ascii=False).casefold()
        for claim_id, claim in claim_map.items():
            blocked_text = claim.get("claim")
            if claim.get("status") in {"NEEDS_PROOF", "DO_NOT_USE"} and isinstance(blocked_text, str) and blocked_text.strip() and blocked_text.strip().casefold() in copy_text:
                errors.append(f"module {module_id} copy contains blocked claim text from {claim_id}")

        style_source_ids = module.get("style_source_ids")
        if not isinstance(style_source_ids, list):
            errors.append(f"module {module_id} style_source_ids must be an array")
        else:
            for source_id in style_source_ids:
                source = source_map.get(source_id)
                if source is None:
                    errors.append(f"module {module_id} references unknown style source {source_id}")
                elif source.get("role") not in STYLE_ROLES:
                    errors.append(f"module {module_id} uses non-style source {source_id} as style guidance")

        prior_candidate_ids = module.get("prior_candidate_ids")
        if not isinstance(prior_candidate_ids, list):
            errors.append(f"module {module_id} prior_candidate_ids must be an array")
        else:
            for candidate_id in prior_candidate_ids:
                if candidate_id not in candidate_map:
                    errors.append(f"module {module_id} references ineligible prior candidate {candidate_id}")

        for key in ("visual_invariants", "forbidden_changes"):
            if not isinstance(module.get(key), list):
                errors.append(f"module {module_id} {key} must be an array")
        output = module.get("output_requirements")
        if not isinstance(output, dict):
            errors.append(f"module {module_id} output_requirements must be an object")
        else:
            for key in ("format", "aspect_ratio", "background"):
                if not isinstance(output.get(key), str) or not output[key].strip():
                    errors.append(f"module {module_id} output_requirements needs {key}")

        if plan.get("creative_policy_version") == 1 and "creative_brief" not in module:
            errors.extend(f"module {module_id}: {error}" for error in creative_brief_errors(None))
        for error in module_quality_errors(root, module, package_index, locks):
            errors.append(f"module {module_id}: {error}")
        mechanism = module.get("quality_contract", {}).get("mechanism", {})
        if mechanism.get("depicted"):
            for claim_id in mechanism.get("verified_claim_ids", []):
                if claim_map.get(claim_id, {}).get("status") != "VERIFIED":
                    errors.append(f"module {module_id}: operating claim {claim_id} must be VERIFIED")
        if module.get("generation_template", {}).get("template_id") == "main_product":
            copy = module.get("copy", {})
            if any(copy.get(key) for key in ("title", "subtitle", "labels")) or module.get("quality_contract", {}).get("human", {}).get("present"):
                errors.append(f"module {module_id}: main_product cannot contain copy or a human")

    errors.extend(layout_errors(plan, modules))
    design_errors, design_warnings = design_plan_checks(root, plan, modules)
    errors.extend(design_errors)
    warnings.extend(design_warnings)
    for channel, views in previous_views.items():
        for index in range(len(views) - 2):
            if len(set(views[index:index + 3])) == 1:
                warnings.append(f"{channel} has three consecutive modules with target_view {views[index]}")
                break

    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        return 1
    if args.approve:
        now = datetime.now(timezone.utc).isoformat()
        plan["status"] = "APPROVED"
        plan["approved_at"] = now
        plan["approved_input_snapshot_sha256"] = actual_snapshot_hash
        plan["approved_lockset_version"] = lockset.get("version")
        if plan.get("schema_version", 1) >= 2:
            for row in plan["modules"]:
                spec_path = resolve_file(root, row["spec_path"])
                spec = load_json(spec_path)
                for ref in [*spec.get("product_references", []), *spec.get("pose_references", [])]:
                    ref["sha256"] = sha256(resolve_file(root, ref["path"]))
                write_json(spec_path, spec)
                row["spec_sha256"] = sha256(spec_path)
        write_json(plan_path, plan)
        plan_hash = sha256(plan_path)
        previous = {
            item.get("module_id"): item
            for item in set_state.get("modules", [])
            if isinstance(item, dict) and item.get("module_id")
        }
        module_states = []
        for module in modules:
            record = previous.get(module["module_id"], {"module_id": module["module_id"], "status": "PLANNED"})
            module_states.append(record)
        set_state.update({
            "status": "PLAN_APPROVED",
            "plan_revision": plan.get("plan_revision"),
            "plan_sha256": plan_hash,
            "approved_at": now,
            "modules": module_states,
            "next_action": "MATERIALIZE_MODULE_CONTRACTS",
        })
        write_json(state_path, set_state)
        print(f"APPROVE  set plan {args.set_id}: sha256={plan_hash}")
    else:
        print(f"PASS  set plan {args.set_id} is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
