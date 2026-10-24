#!/usr/bin/env python3
"""Initialize an Amazon visual set from current product state and reviewed outputs."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from set_common import MAX_CHANNEL_IMAGES, EXPANDED_MIN_IMAGES, NORMAL_TARGET_IMAGES, GALLERY_TARGET_IMAGES, SAFE_ID, SOURCE_ROLES, default_modules, module_stub, load_contract, load_json, resolve_file, sha256, store_module_spec, update_product_summary, write_json
from a_plus_layout import PROFILE_ID, profile_drafts
from module_language import canonical_role


MARKETPLACE = re.compile(r"[A-Z][A-Z0-9_]{1,63}")
ELIGIBLE = {"ACCEPTED", "HUMAN_STRUCTURE_REVIEW_PASSED"}


def brief_drafts(brief, index):
    """Use the decomposed brief's IDs and grouping instead of regenerating a seed."""
    job = brief["job"]
    channel = job["channel"]
    width, height = job["width"], job["height"]
    if any(not isinstance(n, int) or isinstance(n, bool) or n < 1 for n in (width, height)):
        raise ValueError("design brief needs positive pixel dimensions")
    if channel == "PREMIUM_A_PLUS" and (width, height) != (1464, 600):
        raise ValueError("A+ delivery requires only 1464x600")
    facts = {}
    for fact in brief.get("product", {}).get("facts", []):
        fact_id, wording = fact.get("fact_id"), fact.get("text")
        if not isinstance(fact_id, str) or not fact_id.strip() or fact_id in facts or not isinstance(wording, str) or not wording.strip():
            raise ValueError("design brief needs unique fact IDs and non-empty supported fact text")
        facts[fact_id] = wording
    copy_languages = {line["language"] for source in brief["modules"] for line in source.get("copy", [])}
    if len(copy_languages) > 1 or (copy_languages and job.get("language", "source") != "source" and copy_languages != {job["language"]}):
        raise ValueError("select one delivery language before importing; archived translations are not extra image tasks")
    group_rows = brief.get("content_groups", [])
    groups = {x["group_id"]: x for x in group_rows}
    if len(groups) != len(group_rows) or any(not isinstance(k, str) or not SAFE_ID.fullmatch(k) for k in groups):
        raise ValueError("design brief needs unique safe content-group IDs")
    evidence = {x["evidence_id"]: x for x in index.get("product_evidence", [])}
    templates = {"main": "main_product", "material": "material_macro", "detail": "hardware_static",
                 "lifestyle": "lifestyle_simple", "variants": "range_story", "fit": "size_fit", "operation": "mechanism_steps"}
    tasks, pages, seen = [], {}, set()
    for sequence, source in enumerate(brief["modules"], 1):
        image_id = source["image_id"]
        if not isinstance(image_id, str) or not SAFE_ID.fullmatch(image_id) or image_id in seen:
            raise ValueError("design brief needs unique safe image IDs")
        seen.add(image_id)
        role = canonical_role(source["role"])
        question = source["buyer_question"]
        item = module_stub(image_id, channel, sequence, source.get("sales_task", question), question, image_id,
                           f"{width}:{height}", "as_planned", template_id=templates.get(role, "product_overview"))
        if "execution_policy" in source:
            item["execution_policy"] = deepcopy(source["execution_policy"])
        item["image_intent"] = {"module_role": role, "must_show": source["must_show"]}
        required = source.get("required_fact_ids", [])
        dependencies = [*required, *(fact_id for line in source.get("copy", []) for fact_id in line.get("required_fact_ids", []))]
        if any(fact_id not in facts for fact_id in dependencies):
            raise ValueError(f"{image_id} references an unavailable supported fact")
        if required:
            item["image_intent"]["product_facts"] = [{"fact_id": fact_id, "text": facts[fact_id]} for fact_id in dict.fromkeys(required)]
        item["copy"] = {"labels": [line["text"] for line in source.get("copy", [])]}
        item["output_requirements"].update(width_px=width, height_px=height)
        for evidence_id in source.get("product_evidence_ids", []):
            if evidence_id not in evidence:
                raise ValueError(f"unknown product evidence ID in design brief: {evidence_id}")
            item["product_references"].append({"path": evidence[evidence_id]["path"], "role": "PRODUCT_EVIDENCE", "usage_scope": "PRODUCT_IDENTITY_ONLY"})
        if groups:
            group_id = source.get("content_group_id")
            if group_id not in groups:
                raise ValueError(f"{image_id} needs a known content_group_id")
            if group_id not in pages:
                group = groups[group_id]
                pages[group_id] = {"page_module_id": group_id, "sequence": len(pages) + 1,
                                   "content_role": canonical_role(group["role"]), "sales_task": group.get("sales_task", group["buyer_question"]),
                                   "buyer_question": group["buyer_question"], "image_ids": []}
            pages[group_id]["image_ids"].append(image_id)
        tasks.append(item)
    if groups and set(pages) != set(groups):
        raise ValueError("design brief contains groups without child image tasks")
    layout = None
    if channel == "PREMIUM_A_PLUS" and groups:
        for page in pages.values():
            page["display_type"] = "CAROUSEL" if len(page["image_ids"]) > 1 else "FULL_BACKGROUND_IMAGE"
        layout = {"profile_id": "input-led", "reference_scope": "STRUCTURE_ONLY", "delivery": "INDIVIDUAL_IMAGES",
                  "assembly_owner": "DESIGN_TEAM", "canvas": {"width_px": width, "height_px": height}, "page_modules": list(pages.values())}
    return layout, tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--set-id", required=True)
    parser.add_argument("--marketplace", default="AMAZON_US")
    parser.add_argument("--deliverable", choices=("gallery", "a-plus", "both"), help="required scope unless explicit channel counts/profile already identify it")
    parser.add_argument("--mode", choices=("standard", "expanded"), default="standard", help="standard: Gallery defaults to 9, A+ to 13; expanded: explicit large-set request")
    parser.add_argument("--count", type=int, help="count per selected channel, not combined total")
    parser.add_argument("--gallery-count", type=int, help="explicit Gallery count; unselected channels get zero")
    parser.add_argument("--a-plus-count", type=int, help="explicit A+ image-task count, not page-module count")
    parser.add_argument("--a-plus-profile", choices=(PROFILE_ID, "none"), help="A+ grouping seed for 9-15 images; none explicitly selects ungrouped templates")
    parser.add_argument("--design-input", type=Path, help="filtered, fully decomposed DESIGN_INPUT.json for one channel")
    args = parser.parse_args()
    brief = None
    if args.design_input:
        try:
            brief_bytes = args.design_input.read_bytes()
            brief = json.loads(brief_bytes)
            job = brief["job"]
            scope = {"PREMIUM_A_PLUS": "a-plus", "AMAZON_GALLERY": "gallery"}[job["channel"]]
            target = job["target_image_count"]
            if (brief.get("schema_version") != 1 or job.get("scope") == "single"
                    or brief.get("deferred_modules") or brief.get("deferred_content_groups")
                    or not isinstance(target, int) or isinstance(target, bool) or not 1 <= target <= MAX_CHANNEL_IMAGES
                    or len(brief["modules"]) != target):
                raise ValueError("finish image decomposition and resolve deferred facts before importing; single work uses the single-image route")
            if args.deliverable not in (None, scope) or args.a_plus_profile is not None:
                raise ValueError("design-input scope/grouping conflicts with deliverable/profile")
            selected_count = args.a_plus_count if scope == "a-plus" else args.gallery_count
            if any(n is not None and n != target for n in (args.count, selected_count)):
                raise ValueError("explicit count differs from design-input target_image_count")
            args.deliverable = scope
            args.count = target
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(f"invalid design input: {error}")
    if args.deliverable is None:
        gallery = args.gallery_count is not None and args.gallery_count > 0
        a_plus = (args.a_plus_count is not None and args.a_plus_count > 0) or args.a_plus_profile is not None
        args.deliverable = "both" if gallery and a_plus else "gallery" if gallery else "a-plus" if a_plus else None
    if args.deliverable is None:
        parser.error("choose --deliverable gallery, a-plus, or both from the user's instruction; an unqualified set request has no automatic channel")
    selected_gallery = args.deliverable in {"gallery", "both"}
    selected_a_plus = args.deliverable in {"a-plus", "both"}
    if (not selected_gallery and args.gallery_count not in (None, 0)) or (not selected_a_plus and (args.a_plus_count not in (None, 0) or args.a_plus_profile is not None)):
        parser.error("explicit counts/profile conflict with --deliverable")
    fallback = args.count if args.count is not None else 36 if args.mode == "expanded" else NORMAL_TARGET_IMAGES
    if args.gallery_count is None:
        args.gallery_count = (GALLERY_TARGET_IMAGES if args.count is None and args.mode == "standard" else fallback) if selected_gallery else 0
    if args.a_plus_count is None:
        args.a_plus_count = fallback if selected_a_plus else 0
    if selected_gallery and args.gallery_count == 0 or selected_a_plus and args.a_plus_count == 0:
        parser.error("a selected deliverable must have a positive count; select only the requested channels")
    if brief is not None:
        args.a_plus_profile = None
    elif args.a_plus_profile is None:
        args.a_plus_profile = PROFILE_ID if 9 <= args.a_plus_count <= 15 else None
    elif args.a_plus_profile == "none":
        args.a_plus_profile = None
    if not SAFE_ID.fullmatch(args.set_id):
        parser.error("set-id must use letters, digits, dots, underscores, or hyphens")
    if not MARKETPLACE.fullmatch(args.marketplace):
        parser.error("marketplace must be an uppercase identifier such as AMAZON_US")
    if not 0 <= args.gallery_count <= MAX_CHANNEL_IMAGES or not 0 <= args.a_plus_count <= MAX_CHANNEL_IMAGES or args.gallery_count + args.a_plus_count == 0:
        parser.error(f"counts must be non-negative with 1-{MAX_CHANNEL_IMAGES} images in each selected channel")
    if max(args.gallery_count, args.a_plus_count) >= EXPANDED_MIN_IMAGES and args.mode != "expanded":
        parser.error("30-40 images in one channel require explicit --mode expanded")
    if args.a_plus_profile and not 9 <= args.a_plus_count <= 15:
        parser.error("seven-module-desktop seeds 9-15 image tasks; choose that count or extend its draft afterward")

    root = args.package.resolve()
    try:
        product_state = load_json(root / "PRODUCT_STATE.json")
        index = load_json(root / "index.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(f"cannot read product package: {error}")
    if product_state.get("product_id") != index.get("product_id"):
        parser.error("product identity differs between index.json and PRODUCT_STATE.json")
    reference = product_state.get("reference_package", {})
    actual_index_hash = sha256(root / "index.json")
    if reference.get("sha256") != actual_index_hash:
        parser.error("index.json changed after package validation; validate the reference package first")
    workflow_status = product_state.get("workflow", {}).get("status")
    if workflow_status in {"REFERENCE_INTAKE", "REFERENCE_CHANGED"}:
        parser.error(f"product workflow is {workflow_status}; reconcile references first")
    baseline = product_state.get("product_identity_baseline", {})
    lockset = product_state.get("identity_lockset", {})
    if baseline.get("status") != "READY" or lockset.get("status") != "READY":
        parser.error("product identity baseline and identity lockset must both be READY")

    set_root = root / "visual_sets" / args.set_id
    if (set_root / "SET_STATE.json").exists() or (set_root / "SET_PLAN.json").exists():
        parser.error("set-id already exists; resume it or choose a new revision ID")
    imported_drafts = None
    if brief is not None:
        try:
            imported_drafts = brief_drafts(brief, index)
        except (ValueError, KeyError, TypeError) as error:
            parser.error(f"invalid decomposed design input: {error}")

    commercial_dir = root / "commercial"
    manifest_path = commercial_dir / "source_manifest.json"
    if not manifest_path.exists():
        write_json(manifest_path, {"schema_version": 1, "sources": []})
    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(f"invalid commercial source manifest: {error}")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        parser.error("commercial source manifest sources must be an array")
    normalized_sources = []
    seen_source_ids = set()
    for source in sources:
        if not isinstance(source, dict) or not SAFE_ID.fullmatch(str(source.get("source_id", ""))):
            parser.error("every commercial source needs a safe source_id")
        if source["source_id"] in seen_source_ids:
            parser.error(f"duplicate commercial source_id: {source['source_id']}")
        seen_source_ids.add(source["source_id"])
        if source.get("role") not in SOURCE_ROLES:
            parser.error(f"invalid commercial source role: {source.get('role')}")
        try:
            source_file = resolve_file(root, source.get("path"))
        except ValueError as error:
            parser.error(str(error))
        actual_hash = sha256(source_file)
        if source.get("sha256") not in (None, actual_hash):
            parser.error(f"commercial source hash mismatch: {source['source_id']}")
        normalized_sources.append({**source, "sha256": actual_hash})

    accepted_outputs, excluded_outputs = [], []
    for candidate in product_state.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("candidate_id")
        if candidate.get("status") not in ELIGIBLE:
            excluded_outputs.append({"candidate_id": candidate_id, "reason": f"status_{candidate.get('status', 'UNKNOWN')}"})
            continue
        try:
            candidate_file = resolve_file(root, candidate.get("path"))
            contract_file = resolve_file(root, candidate.get("source_contract"))
            contract = load_contract(root, contract_file)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            excluded_outputs.append({"candidate_id": candidate_id, "reason": f"invalid_candidate_record:{error}"})
            continue
        actual_hash = sha256(candidate_file)
        if candidate.get("sha256") != actual_hash:
            excluded_outputs.append({"candidate_id": candidate_id, "reason": "candidate_hash_mismatch"})
            continue
        if contract.get("sku") != product_state.get("sku"):
            excluded_outputs.append({"candidate_id": candidate_id, "reason": "sku_mismatch"})
            continue
        if contract.get("identity_lockset_version") != lockset.get("version"):
            excluded_outputs.append({"candidate_id": candidate_id, "reason": "stale_lockset_version"})
            continue
        usage = ["VISIBLE_CROSS_VIEW_CONSISTENCY"]
        if candidate.get("status") == "ACCEPTED":
            usage.extend(["COLOR_RENDERING_CONSISTENCY", "VISUAL_STYLE_CONSISTENCY"])
        accepted_outputs.append({
            "candidate_id": candidate_id,
            "path": candidate["path"],
            "sha256": actual_hash,
            "status": candidate["status"],
            "source_contract": candidate["source_contract"],
            "run_id": candidate.get("run_id") or contract.get("run_id"),
            "view": contract.get("target_view"),
            "usage_scope": usage,
        })

    now = datetime.now(timezone.utc).isoformat()
    snapshot_path = set_root / "INPUT_SNAPSHOT.json"
    snapshot = {
        "schema_version": 1,
        "set_id": args.set_id,
        "product_id": product_state.get("product_id"),
        "sku": product_state.get("sku"),
        "marketplace": args.marketplace,
        "created_at": now,
        "reference_snapshot": {
            "index_path": "index.json",
            "index_sha256": actual_index_hash,
            "identity_lockset_version": lockset.get("version"),
        },
        "commercial_manifest": {
            "path": manifest_path.relative_to(root).as_posix(),
            "sha256": sha256(manifest_path),
            "sources": normalized_sources,
        },
        "accepted_outputs": accepted_outputs,
        "excluded_outputs": excluded_outputs,
        "evidence_gaps": product_state.get("evidence_gaps", []),
        "identity_lockset": lockset,
        "sellable_object": product_state.get("sellable_object", {}),
    }
    if brief is not None:
        snapshot["design_brief"] = {"source": str(args.design_input.resolve()), "sha256": hashlib.sha256(brief_bytes).hexdigest()}
    write_json(snapshot_path, snapshot)

    layout = None
    drafts = default_modules(args.gallery_count, 0 if args.a_plus_profile else args.a_plus_count) if imported_drafts is None else []
    if imported_drafts is not None:
        layout, drafts = imported_drafts
    if args.a_plus_profile:
        layout, a_plus_drafts = profile_drafts(args.a_plus_count)
        drafts.extend(a_plus_drafts)
    modules = [store_module_spec(root, set_root, item) for item in drafts]
    catalog_path = set_root / "TEMPLATES.json"
    write_json(catalog_path, load_json(Path(__file__).resolve().parents[1] / "assets/generation-templates.json"))
    design_path = set_root / "DESIGN_PATTERNS.json"
    write_json(design_path, load_json(Path(__file__).resolve().parents[1] / "assets/design-patterns.json"))
    plan_path = set_root / "SET_PLAN.json"
    plan = {
        "schema_version": 2,
        "set_id": args.set_id,
        "sku": product_state.get("sku"),
        "marketplace": args.marketplace,
        "status": "DRAFT",
        "generation_mode": args.mode,
        "deliverable": args.deliverable,
        "quantity_policy": {"scope": "PER_CHANNEL", "normal_min": 9, "normal_max": 15, "target": GALLERY_TARGET_IMAGES if args.deliverable == "gallery" else NORMAL_TARGET_IMAGES,
                            "selected_counts": {"AMAZON_GALLERY": args.gallery_count, "PREMIUM_A_PLUS": args.a_plus_count}},
        "creative_policy_version": 1,
        "design_policy_version": 1,
        "module_language_policy_version": 1,
        "design_system": {"mode": "adaptive", "narrative_framework_id": "DIRECT", "rationale": ""},
        "plan_revision": 1,
        "input_snapshot": snapshot_path.relative_to(root).as_posix(),
        "positioning": "",
        "audience": {"primary": "", "secondary": "", "motivation": ""},
        "selling_points": {"s_tier": [], "a_tier": [], "b_tier": []},
        "claims": [],
        "visual_system": {},
        "template_catalog": {"path": catalog_path.relative_to(root).as_posix(), "sha256": sha256(catalog_path)},
        "design_catalog": {"path": design_path.relative_to(root).as_posix(), "sha256": sha256(design_path)},
        "modules": modules,
    }
    if layout:
        plan["a_plus_layout"] = layout
    write_json(plan_path, plan)

    set_state = {
        "schema_version": 1,
        "set_id": args.set_id,
        "marketplace": args.marketplace,
        "status": "SET_PLAN_DRAFT",
        "plan_revision": 1,
        "plan_path": plan_path.relative_to(root).as_posix(),
        "input_snapshot": snapshot_path.relative_to(root).as_posix(),
        "input_snapshot_sha256": sha256(snapshot_path),
        "modules": [{"module_id": item["module_id"], "status": "PLANNED"} for item in modules],
        "next_action": "COMPLETE_COMMERCIAL_INPUTS_AND_PLAN",
    }
    write_json(set_root / "SET_STATE.json", set_state)
    update_product_summary(product_state, set_state)
    write_json(root / "PRODUCT_STATE.json", product_state)
    print(f"CREATE  visual set {args.set_id}: {set_root}")
    print(f"SNAPSHOT  accepted={len(accepted_outputs)} excluded={len(excluded_outputs)} commercial_sources={len(normalized_sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
