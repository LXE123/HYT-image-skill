#!/usr/bin/env python3
"""Small state queries and per-image work packets; no transcript forwarding."""

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from set_common import SAFE_ID, load_contract, load_json, plan_modules, resolve_file, sha256
from quality_rules import focused_prompt, required_checks, review_status, validate_quality
from a_plus_layout import design_handoff, image_membership, layout_summary
from finalize_a_plus_image import export_errors
from structure_state import structure_requirements
from execution_policy import policy_errors
from gallery_review import opening_review_status, require_opening_approval
from project_store import transaction, claim_generation, get_claim, recover_generation
from sync_set_status import synchronize
from record_candidate import record_candidate

SCRIPTS = Path(__file__).resolve().parent
SINGLE = SCRIPTS.parents[1] / "product-single-image-generator" / "scripts"


def command(directory, script, root, *args, allow_failure=False):
    result = subprocess.run([sys.executable, "-B", str(directory / script), str(root), *args], capture_output=True, text=True)
    if result.returncode and not allow_failure:
        raise ValueError((result.stdout + result.stderr)[-3000:].strip())
    return result


def records(root, set_id):
    folder = root / "visual_sets" / set_id
    return load_json(folder / "SET_PLAN.json"), load_json(folder / "SET_STATE.json"), load_json(root / "PRODUCT_STATE.json")


def progress(root, plan, state, product):
    saved = {x["module_id"]: x for x in state.get("modules", [])}
    candidates = {x["candidate_id"]: x for x in product.get("candidates", [])}
    rows = []
    for module in plan["modules"]:
        row = dict(saved.get(module["module_id"], {"module_id": module["module_id"], "status": "PLANNED"}))
        candidate = candidates.get(row.get("candidate_id"))
        if row.get("status") == "BLOCKED":
            rows.append({**row, "required": module.get("required", True)})
            continue
        if candidate:
            if candidate.get("status") in {"PENDING_REVIEW", "HUMAN_STRUCTURE_REVIEW_PASSED"}:
                row["status"] = "REVIEW_REQUIRED"
            elif str(candidate.get("status", "")).startswith("REJECTED"):
                row["status"] = "REJECTED"
                if candidate.get("failure_code"):
                    row["failure_code"] = candidate["failure_code"]
        elif row.get("contract_path"):
            # Crash after image save but before recording: discover it, never regenerate over it.
            contract = load_json(resolve_file(root, row["contract_path"]))
            output = (root / contract["output_path"]).resolve()
            output.relative_to(root)
            if output.is_file():
                row["status"] = "REVIEW_REQUIRED"
        row["required"] = module.get("required", True)
        if row.get("status") == "CONTRACT_CREATED" and row.get("candidate_id"):
            claim = get_claim(root, row["candidate_id"])
            if claim and claim["status"] == "RUNNING":
                row["status"] = "GENERATING"
        rows.append(row)
    return rows


def pick(rows, module_id=None, active_candidate=None):
    if module_id:
        selected = next((x for x in rows if x["module_id"] == module_id), None)
        if selected is None:
            raise ValueError("unknown module-id")
        return selected
    pending = [x for x in rows if x.get("required") and x.get("status") != "ACCEPTED"]
    active = next((x for x in pending if x.get("candidate_id") and x.get("candidate_id") == active_candidate), None)
    return active or next((x for x in pending if x.get("status") == "REVIEW_REQUIRED"), None) or next(iter(pending), None)


def pick_generation(rows, module_id=None):
    """Explicit production selection; pending reviews remain pending, never accepted."""
    available = [x for x in rows if x.get("status") in {"PLANNED", "CONTRACT_CREATED"} and (x.get("required") or module_id)]
    if module_id:
        selected = next((x for x in available if x["module_id"] == module_id), None)
        if selected is None:
            raise ValueError("selected module has no unproduced candidate; review or explicitly retry it")
        return selected
    return next(iter(available), None)


def summary(plan, state, rows, selected):
    result = {"set_id": plan["set_id"], "set_status": state["status"], "counts": dict(Counter(x["status"] for x in rows)), "total": len(rows)}
    if plan.get("generation_mode"):
        result["generation_mode"] = plan["generation_mode"]
    if plan.get("deliverable"):
        result["deliverable"] = plan["deliverable"]
    if "selected_counts" in plan.get("quantity_policy", {}):
        result["target_image_counts"] = plan["quantity_policy"]["selected_counts"]
    if plan.get("a_plus_layout"):
        result["a_plus"] = layout_summary(plan, rows)
    if selected:
        result["current"] = {k: selected[k] for k in ("module_id", "status", "attempt", "candidate_id", "contract_path", "failure_code") if k in selected}
        membership = image_membership(plan, selected["module_id"])
        if membership:
            result["current"]["page"] = membership
        status = selected["status"]
        result["next_action"] = "WAIT_OR_RECOVER_GENERATION" if status == "GENERATING" else "REVIEW_CURRENT_IMAGE" if status == "REVIEW_REQUIRED" else "RETRY_OR_REPLAN_CURRENT_IMAGE" if status == "REJECTED" else "RESOLVE_BLOCKED_MODULE" if status == "BLOCKED" else "PREPARE_CURRENT_IMAGE"
    else:
        result["next_action"] = "NONE" if state["status"] == "COMPLETE" else "SYNCHRONIZE_OR_COMPLETE_PLAN"
    if state.get("block_reason") == "SET_SOURCES_CHANGED":
        result["next_action"] = "RECONCILE_REFERENCE_CHANGE"
    return result


def check_sources(root, plan, state, product):
    if plan.get("status") != "APPROVED":
        raise ValueError("complete and approve the plan before generation")
    plan_path = root / "visual_sets" / plan["set_id"] / "SET_PLAN.json"
    if sha256(plan_path) != state.get("plan_sha256"):
        raise ValueError("approved plan changed")
    snapshot_path = resolve_file(root, plan["input_snapshot"])
    if sha256(snapshot_path) != plan.get("approved_input_snapshot_sha256"):
        raise ValueError("input snapshot changed")
    snapshot = load_json(snapshot_path)
    if sha256(root / "index.json") != snapshot["reference_snapshot"]["index_sha256"]:
        raise ValueError("reference evidence changed; reconcile before continuing")
    if product.get("identity_lockset", {}).get("status") != "READY":
        raise ValueError("product lockset changed")


def packet(root, plan, state, product, row, phase, max_images):
    check_sources(root, plan, state, product)
    if phase == "generation":
        require_opening_approval(root, plan, state, product, row["module_id"])
    path = resolve_file(root, row.get("contract_path"))
    contract = load_contract(root, path)
    index = load_json(root / "index.json")
    locks = {x["lock_id"]: x for x in product["identity_lockset"]["locks"]}
    failures = validate_quality(root, contract, index, locks)
    failures.extend(policy_errors(contract, generation=True))
    if failures:
        raise ValueError("; ".join(failures))
    if contract.get("resolved_identity_locks") != [locks[x] for x in contract["required_lock_ids"]]:
        raise ValueError("contract identity facts differ from current locks")
    refs = []
    selected_refs = contract["references"] if phase == "review" else [*contract["references"], *contract.get("style_references", []), *contract.get("prior_candidate_references", [])]
    for ref in selected_refs:
        ref_path = resolve_file(root, ref["path"])
        if ref.get("sha256") and sha256(ref_path) != ref["sha256"]:
            raise ValueError(f"reference changed: {ref['path']}")
        if ref.get("candidate_id"):
            live = next((x for x in product.get("candidates", []) if x.get("candidate_id") == ref["candidate_id"]), {})
            if live.get("status") not in {"ACCEPTED", "HUMAN_STRUCTURE_REVIEW_PASSED"} or live.get("status") != ref.get("status"):
                raise ValueError("previous candidate is no longer eligible")
        refs.append({"path": str(ref_path), "role": ref.get("role", "REVIEWED_PRIOR_IMAGE"), "usage_scope": ref["usage_scope"], "kind": "image" if ref_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff", ".heic"} else "document"})
    if len(refs) > max_images:
        raise ValueError(f"packet has {len(refs)} reference files (limit {max_images}); narrow optional references or explicitly increase --max-images; none were dropped")
    result = {"module_id": row["module_id"], "phase": phase, "candidate_id": contract["candidate_id"], "contract_path": row["contract_path"], "contract_sha256": sha256(path), "attempt": row.get("attempt", 1), "references": refs}
    if "execution_policy" in contract:
        result["execution_mode"] = contract["execution_policy"]["mode"]
    membership = image_membership(plan, row["module_id"])
    if membership:
        result["page"] = membership
    if phase == "generation":
        if row["status"] in {"ACCEPTED", "REJECTED", "REVIEW_REQUIRED", "BLOCKED"}:
            raise ValueError("current candidate cannot be generated again; review it or prepare an explicit retry")
        result.update({"output_path": str(root / contract["output_path"]), "prompt": focused_prompt(contract)})
        if contract["output_requirements"].get("postprocess") == "CODE_CROP_RESIZE":
            final_path = root / contract["output_path"]
            result["raw_output_path"] = str(final_path.with_name(final_path.stem + ".raw.png"))
            result["postprocess"] = {"script": str(SINGLE / "finalize_a_plus_image.py"),
                                     "instruction": "Save to raw_output_path; code-export to output_path before review: same ratio resizes full frame; otherwise inspect and set --keep-box."}
            if contract["output_requirements"].get("pre_crop_review") == "OBSERVED_LAYOUT_V1":
                result["postprocess"]["source_review_path"] = f"qa/visual/{contract['candidate_id']}-source.json"
                result["postprocess"]["instruction"] = "Inspect source QA, check proposed crop, then export with --package/--contract/--review; inspect the final separately."
            if Path(result["raw_output_path"]).is_file():
                result["phase"] = "postprocess"
                result.pop("prompt")
                result["postprocess"]["instruction"] = "Raw exists; code-export to output_path, no regeneration. Same ratio resizes full frame; otherwise inspect and set --keep-box."
                if contract["output_requirements"].get("pre_crop_review") == "OBSERVED_LAYOUT_V1":
                    result["postprocess"]["instruction"] = "Raw exists; no regeneration. Inspect source QA, check crop, then guarded export with --package/--contract/--review."
        if result["phase"] == "generation" and get_claim(root, contract["candidate_id"]):
            raise ValueError("generation already claimed; wait or recover the current attempt")
    else:
        candidate = next((x for x in product.get("candidates", []) if x.get("candidate_id") == contract["candidate_id"]), {"path": contract["output_path"]})
        image = resolve_file(root, candidate["path"])
        report_path = candidate.get("checks", {}).get("visual", {}).get("report_path")
        if report_path:
            result["review"] = review_status(root, contract, path, candidate, load_json(resolve_file(root, report_path)))
            result["review"]["report_path"] = report_path
            failures = [error for error in result["review"]["errors"] if error.startswith("A+ code export:")]
        else:
            result["review"] = {"execution": "REVIEW", "status": "NOT_REVIEWED", "reason": "NO_LINKED_REPORT", "next_action": "INSPECT_CURRENT_IMAGE"}
            failures = export_errors(root, image, contract.get("output_requirements", {}))
        if failures:
            raise ValueError("; ".join(failures))
        result.update({"candidate_path": str(image), "candidate_sha256": sha256(image), "checks": sorted(required_checks(contract)), "expected": {"product_facts": [x["fact"] for x in contract["resolved_identity_locks"]], "quality": contract["quality_contract"], "copy": contract.get("copy", {}), "output": contract["output_requirements"]}})
        if structure_requirements(contract):
            result["expected"]["structure_relations"] = structure_requirements(contract)
        if contract.get("image_intent"):
            result["expected"]["image_intent"] = contract["image_intent"]
        if contract.get("creative_brief"):
            result["expected"]["creative_brief"] = contract["creative_brief"]
        if contract.get("visual_system"):
            result["expected"]["visual_system"] = contract["visual_system"]
        if contract.get("design_recipe"):
            result["expected"]["design_recipe"] = contract["design_recipe"]
        if contract.get("module_language"):
            result["expected"]["module_language"] = contract["module_language"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--set-id", required=True)
    parser.add_argument("action", choices=("status", "next", "next-generation", "module", "prepare", "packet", "record", "sync", "handoff", "claim", "recover"))
    parser.add_argument("--module-id")
    parser.add_argument("--phase", choices=("generation", "review"), default="generation")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--correction", default="")
    parser.add_argument("--claim-token", help="ownership token returned by claim")
    parser.add_argument("--reason", help="concrete interruption/failure reason for recovery")
    parser.add_argument("--decision", choices=("PENDING_REVIEW", "REJECTED_TOPOLOGY", "REJECTED_VISUAL", "ACCEPTED", "HUMAN_STRUCTURE_REVIEW_PASSED"))
    parser.add_argument("--failure-code", choices=("ANATOMY", "CONTACT", "HARDWARE_STATE", "MECHANISM", "PRODUCT_IDENTITY", "COPY", "LAYOUT"))
    parser.add_argument("--report")
    parser.add_argument("--candidate-path")
    parser.add_argument("--human-reviewer")
    parser.add_argument("--decision-reference", help="reference to the user's/designated reviewer's actual decision")
    parser.add_argument("--max-bytes", type=int, default=12000)
    parser.add_argument("--max-images", type=int, default=8)
    args = parser.parse_args()
    if not SAFE_ID.fullmatch(args.set_id) or (args.module_id and not SAFE_ID.fullmatch(args.module_id)):
        parser.error("unsafe set/module ID")
    if args.max_bytes < 512 or args.max_images < 1:
        parser.error("max-bytes must be >=512 and max-images >=1")
    root = args.package.resolve()
    try:
        if args.action in {"next", "next-generation", "prepare", "sync", "handoff"}:
            command(SCRIPTS, "sync_set_status.py", root, "--set-id", args.set_id)
        plan, state, product = records(root, args.set_id)
        rows = progress(root, plan, state, product)
        gate = opening_review_status(root, plan, state, product)
        selectable = rows
        if gate and not gate['approved']:
            gallery_ids = {m['module_id'] for m in plan['modules'] if m['channel'] == 'AMAZON_GALLERY'}
            selectable = [r for r in rows if r['module_id'] not in gallery_ids or r['module_id'] in gate['image_ids']]
            if args.module_id and args.action in {'prepare', 'next-generation'}:
                require_opening_approval(root, plan, state, product, args.module_id)
        row = pick_generation(selectable, args.module_id) if args.action == "next-generation" else pick(rows if args.module_id else selectable, args.module_id, product.get("workflow", {}).get("active_candidate_id"))
        if args.action in {"status", "next", "next-generation", "sync"}:
            result = summary(plan, state, rows, row)
            if args.action == "next-generation":
                result["selection_mode"] = "UNPRODUCED_IMAGES_ONLY"
                if row is None and state["status"] != "COMPLETE" and result.get("next_action") != "RECONCILE_REFERENCE_CHANGE":
                    result["next_action"] = "REVIEW_OR_RESOLVE_REMAINING_IMAGES"
        elif args.action == "handoff":
            if state.get("block_reason") == "SET_SOURCES_CHANGED":
                raise ValueError("reconcile changed sources before design handoff")
            result = design_handoff(plan, rows)
        elif args.action == "module":
            if row is None:
                raise ValueError("no unfinished module; specify --module-id for an existing module")
            # Planning view has only one task and pointers, never every module's body.
            selected = next(x for x in plan["modules"] if x["module_id"] == row["module_id"])
            module = plan_modules(root, plan, row["module_id"])[0]
            result = {"row": selected, "spec": {k: v for k, v in module.items() if k not in selected and k != "generation_template"}}
            membership = image_membership(plan, row["module_id"])
            if membership:
                result["page"] = membership
        elif args.action == "prepare":
            check_sources(root, plan, state, product)
            if row is None:
                result = summary(plan, state, rows, row)
            else:
                require_opening_approval(root, plan, state, product, row["module_id"])
                attempt = row.get("attempt", 1)
                if args.retry:
                    if row["status"] != "REJECTED":
                        raise ValueError("retry requires a rejected candidate")
                    attempt += 1
                elif row["status"] in {"REJECTED", "BLOCKED", "ACCEPTED"}:
                    raise ValueError("review/replan this module, or use --retry with a concrete correction after rejection")
                elif row["status"] == "GENERATING":
                    raise ValueError("generation is active; wait or recover it before preparing again")
                if not row.get("contract_path") or args.retry:
                    command(SCRIPTS, "materialize_module_contracts.py", root, "--set-id", args.set_id, "--module-id", row["module_id"], "--attempt", str(attempt), "--correction", args.correction)
                    plan, state, product = records(root, args.set_id)
                    row = pick(progress(root, plan, state, product), row["module_id"])
                if row["status"] != "REVIEW_REQUIRED":
                    view = next(x["target_view"] for x in plan["modules"] if x["module_id"] == row["module_id"])
                    command(SINGLE, "init_run_records.py", root, "--run-id", row["run_id"], "--sku", plan["sku"], "--view", view)
                    command(SINGLE, "validate_run_records.py", root, "--contract", row["contract_path"], "--ready-for-generation")
                plan, state, product = records(root, args.set_id)
                result = packet(root, plan, state, product, row, "review" if row["status"] == "REVIEW_REQUIRED" else "generation", args.max_images)
        elif args.action == "claim":
            if not args.module_id:
                raise ValueError("claim requires --module-id from prepare")
            with transaction(root):
                plan, state, product = records(root, args.set_id)
                row = pick(progress(root, plan, state, product), args.module_id)
                result = packet(root, plan, state, product, row, "generation", args.max_images)
                if result["phase"] != "generation":
                    raise ValueError("raw output exists; resume postprocessing instead of claiming generation")
                result["claim_token"] = claim_generation(root, row["contract_path"], result["candidate_id"])
                # The claim already pins this hash in SQLite; keep the tool packet small.
                result.pop("contract_sha256")
                if len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()) > args.max_bytes:
                    raise ValueError("claim packet exceeds max-bytes; no task was claimed")
        elif args.action == "recover":
            if not args.module_id or not args.reason:
                raise ValueError("recover requires --module-id and a concrete --reason")
            with transaction(root):
                plan, state, product = records(root, args.set_id)
                row = pick(progress(root, plan, state, product), args.module_id)
                result = recover_generation(root, row["contract_path"], args.claim_token, args.reason)
                synchronize(root, args.set_id)
        elif args.action == "packet":
            if row is None:
                raise ValueError("no selected module")
            result = packet(root, plan, state, product, row, args.phase, args.max_images)
        else:
            with transaction(root):
                plan, state, product = records(root, args.set_id)
                rows = progress(root, plan, state, product)
                row = pick(rows, args.module_id)
                if not args.module_id or not args.decision or row is None:
                    raise ValueError("record requires --module-id and --decision")
                check_sources(root, plan, state, product)
                record_candidate(root, row["contract_path"], args.decision, candidate_path=args.candidate_path,
                                 failure_code=args.failure_code, report_address=args.report,
                                 human_reviewer=args.human_reviewer, decision_reference=args.decision_reference,
                                 claim_token=args.claim_token)
                synchronize(root, args.set_id)
                plan, state, product = records(root, args.set_id)
                rows = progress(root, plan, state, product)
                result = summary(plan, state, rows, pick(rows))
        if args.action in {'status', 'next', 'next-generation', 'sync', 'record'}:
            gate = opening_review_status(root, plan, state, product)
            if gate:
                result['opening_review'] = gate
                current = result.get('current', {})
                opening_unproduced = any(r['module_id'] in gate['image_ids'] and r.get('status') in
                                         {'PLANNED', 'CONTRACT_CREATED'} for r in rows)
                if (not gate['approved'] and not opening_unproduced
                        and result.get('next_action') != 'RECONCILE_REFERENCE_CHANGE'
                        and (row is None or (current.get('module_id') in gate['image_ids']
                                             and current.get('status') in {'REVIEW_REQUIRED', 'ACCEPTED'}))):
                    result['next_action'] = 'WAIT_FOR_GALLERY_OPENING_APPROVAL'
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > args.max_bytes:
            raise ValueError(f"response exceeds {args.max_bytes} bytes; shorten this module's optional inputs or explicitly increase --max-bytes; no constraints were truncated")
        print(encoded)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
