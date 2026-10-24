"""Shared preflight and recorded visual-QA rules; these do not inspect pixels."""

from structure_state import contract_state_errors, structure_requirements, observation_errors
import hashlib
import json
import math
from pathlib import PurePosixPath
from finalize_a_plus_image import export_errors


BASE_CHECKS = {"product_identity", "structure_topology", "human_presence", "copy_claims", "layout_output"}
VISUAL_REVIEW_VERSION = 1

COPY_EXECUTION = (
    "Render supplied image copy verbatim in its given language, preserving spelling, punctuation, numbers and special characters. "
    "Do not translate, paraphrase or replace it with analysis text. Analytical Chinese/English instructions and module design descriptions are not image lettering. "
    "Only the explicitly selected final copy belongs in the image. "
    "Exact copy is lettering, not an instruction to depict its claims. Only assigned visual tasks and their supported facts guide the scene. "
    "Do not illustrate every benefit: copy-only points may remain typographic, without invented effects, actions or performance proof."
)

DESIGN_EXECUTION = (
    "Art direction: make this image's chosen visual device, lighting and graphic treatment visible in the composition. "
    "Derive spatial and typographic relationships from that idea rather than automatically placing an isolated product/person beside an oversized slogan. "
    "Layout boxes guide placement and legibility, not mandatory rectangular split panels. Honor explicit composition and main-image restrictions. "
    "Keep the actual sellable object the intended focus; context devices and decorative copy remain subordinate unless the brief explicitly assigns them another role."
)


def canvas_rules(contract):
    if (contract.get("output_requirements") or {}).get("postprocess") == "CODE_CROP_RESIZE":
        return ["Canvas: 2.44:1 (1464:600) landscape; override reference/style framing, keep all content crop-safe. Code finalizes pixels."]
    return []


def design_execution(contract):
    if (contract.get("generation_template") or {}).get("template_id") == "main_product":
        return []
    rules = [DESIGN_EXECUTION] if contract.get("creative_brief") else []
    if contract.get("visual_system"):
        rules.append(
            "Set continuity: local briefs, catalog styles and references refine visual_system within its background lightness/colour, "
            "white balance, contrast/shadows and type-family range. Keep product colours; vary composition, scene and surfaces within that range."
        )
    return rules



def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_binding(root, contract, image_hash, comparison_images=()):
    """Fingerprint actual review inputs, not a queue status or the generated prompt."""
    keys = ("target_view", "generation_template", "quality_contract", "resolved_identity_locks",
            "required_lock_ids", "visual_invariants", "forbidden_changes", "copy", "image_intent",
            "module_language", "creative_brief", "visual_system", "design_recipe", "output_requirements",
            "claim_ids", "claim_decisions", "sellable_object", "identity_lockset_version")
    refs = [*contract.get("references", []), *contract.get("style_references", []),
            *contract.get("prior_candidate_references", []), *comparison_images]
    paths = {ref["path"] for ref in refs}
    quality = contract.get("quality_contract") or {}
    for detail in [*quality.get("structure_checks", []), quality.get("mechanism") or {}]:
        paths.update(detail.get("evidence_paths", []))
    payload = {"rules_version": VISUAL_REVIEW_VERSION, "candidate_sha256": image_hash,
               "contract": {key: contract.get(key) for key in keys}, "reference_roles": refs,
               "reference_bytes": {p: digest(file_at(root, p)) for p in sorted(paths)}}
    fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"rules_version": VISUAL_REVIEW_VERSION, "input_fingerprint": fingerprint}


def normalized_box(box):
    return (isinstance(box, list) and len(box) == 4
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in box)
            and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)


def composition_result(contract, observed, image_hash, *, coordinate_space="FINAL_IMAGE"):
    """Check annotations and explicit geometry constraints; never detect objects or grade aesthetics."""
    uncertain = []
    failures = []
    if not isinstance(observed, dict):
        return {"status": "REVIEW_REQUIRED", "reasons": ["actual composition observations are missing"], "metrics": {}}
    if observed.get("coordinate_space") != coordinate_space or observed.get("image_sha256") != image_hash:
        uncertain.append(f"composition must refer to the current image hash and {coordinate_space} coordinates")
    if observed.get("annotation_method") not in {"ASSISTANT_VISUAL_ESTIMATE", "HUMAN_ANNOTATION"}:
        uncertain.append("identify who annotated actual image regions")
    if observed.get("boundary_certainty") != "CLEAR":
        uncertain.append("region boundaries are uncertain; visual/human review is required")
    if observed.get("required_content") == "INCOMPLETE":
        failures.append("content required by this image task is cut off or missing")
    elif observed.get("required_content") != "COMPLETE":
        uncertain.append("inspect completeness of the assigned full product, wearing area or detail")
    regions = {}
    for key in ("product_regions", "copy_regions", "protected_regions"):
        entries = observed.get(key)
        if not isinstance(entries, list) or any(not isinstance(x, dict) or not isinstance(x.get("label"), str) or not x["label"].strip() or not normalized_box(x.get("box")) for x in entries):
            uncertain.append(f"{key} needs labelled normalized boxes from the actual image")
        else:
            regions[key] = entries
    if not regions.get("product_regions"):
        uncertain.append("annotate the product or the assigned product detail, not its target box")
    def has_text(value):
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            return any(has_text(x) for x in value.values())
        return isinstance(value, list) and any(has_text(x) for x in value)
    if has_text(contract.get("copy")) and not regions.get("copy_regions"):
        uncertain.append("assigned copy needs actual lettering regions")
    layout = (contract.get("quality_contract") or {}).get("layout") or {}
    constraints = layout.get("review_constraints") or {}
    if not isinstance(constraints, dict) or set(constraints) - {"product_within_target", "copy_within_target", "product_clear_of_copy"} or any(not isinstance(v, bool) for v in constraints.values()):
        uncertain.append("unsupported composition constraints; do not invent universal thresholds")
        constraints = {}
    def inside(box, target):
        return target[0] <= box[0] and target[1] <= box[1] and target[2] >= box[2] and target[3] >= box[3]
    def overlap(a, b):
        return max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    metrics = {"product_box_areas": [(r["box"][2]-r["box"][0])*(r["box"][3]-r["box"][1]) for r in regions.get("product_regions", [])]}
    for name, region_key, target_key in (("product_within_target", "product_regions", "product_box"), ("copy_within_target", "copy_regions", "copy_box")):
        if constraints.get(name):
            target = layout.get(target_key)
            if not normalized_box(target):
                uncertain.append(f"{name} requires an explicit normalized {target_key}")
            elif any(not inside(r["box"], target) for r in regions.get(region_key, [])):
                failures.append(f"{region_key} extend outside the explicitly required {target_key}")
    copy_target = layout.get("copy_box")
    if normalized_box(copy_target):
        metrics["product_overlap_with_copy_target"] = [overlap(r["box"], copy_target) for r in regions.get("product_regions", [])]
    if constraints.get("product_clear_of_copy"):
        if not normalized_box(copy_target):
            uncertain.append("product_clear_of_copy requires an explicit copy_box")
        elif any(metrics["product_overlap_with_copy_target"]):
            failures.append("product intrudes into the explicitly exclusive copy target")
    # An uncertain annotation cannot support a deterministic geometric conclusion.
    return {"status": "REVIEW_REQUIRED" if uncertain else "FAIL" if failures else "PASS",
            "reasons": uncertain + failures, "metrics": metrics}


def file_at(root, value):
    if not isinstance(value, str) or not value or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
        raise ValueError(f"unsafe package path: {value!r}")
    path = (root / value).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError(f"missing file: {value}")
    return path


def texts(value):
    return isinstance(value, list) and bool(value) and all(isinstance(x, str) and x.strip() for x in value)


def creative_brief_errors(brief):
    if not isinstance(brief, dict):
        return ["creative_brief must state this image's visual idea and design criteria"]
    errors = []
    for key in ("visual_concept", "visual_device", "graphic_treatment", "set_role"):
        if not isinstance(brief.get(key), str) or not brief[key].strip():
            errors.append(f"creative_brief.{key} needs a concrete image-specific decision")
    for key in ("information_hierarchy", "success_criteria"):
        if not texts(brief.get(key)):
            errors.append(f"creative_brief.{key} needs explicit ordered items")
    return errors


def required_checks(contract):
    checks = set(BASE_CHECKS)
    if contract.get("image_intent") or contract.get("creative_policy_version") == 1:
        checks.add("content_coverage")
    if (contract.get("creative_brief") or {}).get("visual_concept") or contract.get("creative_policy_version") == 1:
        checks.add("design_quality")
    if contract.get("module_language_policy_version") == 1:
        checks.add("module_role_fit")
    quality = contract.get("quality_contract") or {}
    human = quality.get("human") or {}
    if isinstance(human, dict) and human.get("present"):
        checks.update({"human_anatomy", "human_product_contact"})
    if quality.get("structure_checks"):
        checks.add("hardware_state")
    mechanism = quality.get("mechanism") or {}
    if isinstance(mechanism, dict) and mechanism.get("depicted"):
        checks.add("mechanism_motion")
    template = contract.get("generation_template") or {}
    extra = template.get("required_checks", [])
    if isinstance(extra, list):
        checks.update(x for x in extra if isinstance(x, str))
    return checks


def validate_quality(root, contract, index, locks):
    errors = []
    output = contract.get("output_requirements", {})
    if isinstance(output, dict) and output.get("pre_crop_review") not in (None, "OBSERVED_LAYOUT_V1"):
        errors.append("unsupported pre_crop_review method")
    if isinstance(output, dict) and output.get("postprocess") == "CODE_CROP_RESIZE" and (output.get("width_px"), output.get("height_px"), output.get("format")) != (1464, 600, "PNG"):
        errors.append("code-cropped A+ output requires PNG at exactly 1464x600")
    if contract.get("module_language_policy_version") == 1:
        language = contract.get("module_language")
        if not isinstance(language, dict) or any(not isinstance(language.get(k), str) or not language[k].strip() for k in ("image_task_id", "role", "sales_task", "buyer_question", "visual_language")) or not texts(language.get("must_show")) or not texts(language.get("not_a_substitute")):
            errors.append("module_language must carry the current image responsibility, visual expression and required content")
    if "creative_brief" in contract or contract.get("creative_policy_version") == 1:
        errors.extend(creative_brief_errors(contract.get("creative_brief")))
    if contract.get("creative_policy_version") == 1:
        intent = contract.get("image_intent")
        if not isinstance(intent, dict) or any(not isinstance(intent.get(k), str) or not intent[k].strip() for k in ("sales_task", "buyer_question")):
            errors.append("image_intent needs this image's sales_task and buyer_question")
        system = contract.get("visual_system")
        if not isinstance(system, dict) or any(not isinstance(system.get(k), str) or not system[k].strip() for k in ("direction", "lighting", "typography")):
            errors.append("visual_system needs task-specific direction, lighting and typography (or an explicit no-lettering treatment)")
    template = contract.get("generation_template")
    quality = contract.get("quality_contract")
    if not isinstance(template, dict) or not isinstance(quality, dict):
        return ["generation_template and quality_contract are required; revise legacy drafts before generation"]
    if not template.get("template_id") or template.get("revision") != 1 or not texts(template.get("prompt_rules")):
        errors.append("generation_template needs template_id, revision 1, and concrete prompt_rules")
    if not texts(template.get("required_checks")):
        errors.append("generation_template needs required_checks")
    for key in ("requires_human", "requires_structure", "requires_mechanism"):
        if not isinstance(template.get(key), bool):
            errors.append(f"generation_template.{key} must be boolean")
    if quality.get("version") != 1:
        errors.append("quality_contract.version must be 1")
    layout = quality.get("layout", {})
    if not isinstance(layout, dict):
        layout = {}
    for key in ("product_box", "copy_box"):
        box = layout.get(key)
        if key == "copy_box" and box is None:
            continue
        if not isinstance(box, list) or len(box) != 4 or not all(isinstance(x, (float, int)) and not isinstance(x, bool) and 0 <= x <= 1 for x in box) or not (box[0] < box[2] and box[1] < box[3]):
            errors.append(f"layout.{key} must be normalized [left, top, right, bottom]")
    if not isinstance(layout.get("composition"), str) or not layout["composition"].strip():
        errors.append("layout.composition needs camera, product placement, and copy placement")
    human = quality.get("human", {})
    if not isinstance(human, dict):
        human = {}
    if not isinstance(human.get("present"), bool):
        errors.append("human.present must be explicitly true or false")
    if template.get("requires_human") and human.get("present") is not True:
        errors.append("this template requires a human pose contract")
    if human.get("present"):
        if not isinstance(human.get("pose_description"), str) or not human["pose_description"].strip():
            errors.append("human.pose_description must trace visible shoulder/elbow/wrist/hand ownership")
        for key in ("visible_limbs", "contact_points", "occlusion_order"):
            if not texts(human.get(key)):
                errors.append(f"human.{key} needs explicit observations or an explicit no-contact statement")
    evidence = {x.get("path"): x for x in index.get("product_evidence", []) if isinstance(x, dict)}
    refs = contract.get("references", contract.get("product_references", []))
    reference_paths = {x.get("path") for x in refs if isinstance(x, dict) and x.get("role") == "PRODUCT_EVIDENCE"}
    if not reference_paths:
        errors.append("at least one registered PRODUCT_EVIDENCE reference is required")
    for path in reference_paths:
        item = evidence.get(path)
        if not item:
            errors.append(f"unregistered product reference: {path}")
            continue
        try:
            if digest(file_at(root, path)) != item.get("sha256"):
                errors.append(f"product reference hash changed: {path}")
        except ValueError as exc:
            errors.append(str(exc))

    def sources(paths, label, structure=None, state=None):
        if not texts(paths):
            errors.append(f"{label} needs registered product evidence_paths")
            return
        observed = set()
        for path in paths:
            item = evidence.get(path)
            if item is None or path not in reference_paths:
                errors.append(f"{label}: evidence is not registered and included as PRODUCT_EVIDENCE: {path}")
                continue
            try:
                if digest(file_at(root, path)) != item.get("sha256"):
                    errors.append(f"{label}: evidence hash changed: {path}")
            except ValueError as exc:
                errors.append(str(exc))
            if structure and structure not in item.get("structures", []):
                errors.append(f"{label}: {path} does not cover structure {structure}")
            observed.update(item.get("observed_states", []))
        if state and state not in observed:
            errors.append(f"{label}: state {state!r} has no observed-state evidence")
        return observed

    for relation in structure_requirements(contract).values():
        sources(relation.get("evidence_paths"), "structure relation")
    structures = quality.get("structure_checks")
    if not isinstance(structures, list):
        errors.append("structure_checks must be an array")
        structures = []
    if template.get("requires_structure") and not structures:
        errors.append("this template needs a hardware/connector structure check")
    visible_hardware = quality.get("visible_hardware")
    if not isinstance(visible_hardware, list) or not all(isinstance(x, str) and x.strip() for x in visible_hardware):
        errors.append("visible_hardware must explicitly list every visible connector/clasp or be []")
        visible_hardware = []
    checked_structures = {x.get("structure_id") for x in structures if isinstance(x, dict)}
    if set(visible_hardware) - checked_structures:
        errors.append("every visible_hardware entry needs its own structure check, including lifestyle/main images")
    for check in structures:
        if not isinstance(check, dict):
            errors.append("structure_checks entries must be objects")
            continue
        structure = check.get("structure_id")
        if not isinstance(structure, str) or not structure.strip() or not texts(check.get("visible_checks")):
            errors.append("structure check needs structure_id and concrete visible_checks")
        ids = check.get("lock_ids")
        if not texts(ids) or any(x not in contract.get("required_lock_ids", []) or locks.get(x, {}).get("status") != "LOCKED" for x in ids):
            errors.append("structure check needs current required lock_ids")
        if not isinstance(check.get("expected_state"), str) or not check["expected_state"].strip():
            errors.append("structure check needs expected_state")
        sources(check.get("evidence_paths"), "structure check", structure, check.get("expected_state"))
    mechanism = quality.get("mechanism", {})
    if not isinstance(mechanism, dict):
        mechanism = {}
    if not isinstance(mechanism.get("depicted"), bool):
        errors.append("mechanism.depicted must be explicitly true or false (arrows and operating copy count)")
    if template.get("requires_mechanism") and mechanism.get("depicted") is not True:
        errors.append("mechanism template requires state-transition evidence; choose static detail if unavailable")
    if mechanism.get("depicted"):
        for key in ("action", "start_state", "end_state", "structure_id"):
            if not isinstance(mechanism.get(key), str) or not mechanism[key].strip():
                errors.append(f"mechanism.{key} is required")
        if not structures:
            errors.append("mechanism requires structure_checks")
        observed = sources(mechanism.get("evidence_paths"), "mechanism", mechanism.get("structure_id")) or set()
        for key in ("start_state", "end_state"):
            if mechanism.get(key) not in observed:
                errors.append(f"mechanism.{key} is not established by observed_states")
        if not texts(mechanism.get("verified_claim_ids")) or any(x not in contract.get("claim_ids", []) for x in mechanism.get("verified_claim_ids", [])):
            errors.append("mechanism requires linked verified operating claim IDs")
        if "visual_set" in contract:
            decisions = {x.get("claim_id"): x for x in contract.get("claim_decisions", []) if isinstance(x, dict)}
            if any(decisions.get(x, {}).get("status") != "VERIFIED" for x in mechanism.get("verified_claim_ids", [])):
                errors.append("operating claims must retain their VERIFIED claim decisions")
    return errors


def compile_prompt(contract):
    """Keep the exact instructions and evidence roles reviewable beside the contract."""
    if contract.get("prompt_format") == "focused-v1":
        return focused_prompt(contract)
    return "\n\n".join([
        *canvas_rules(contract),
        "Generate one independent product image. Never invent unseen parts or a mechanism.",
        COPY_EXECUTION,
        "Template rules: " + json.dumps(contract["generation_template"], ensure_ascii=False),
        "View: " + contract["target_view"],
        *(["Image purpose: " + json.dumps(contract["image_intent"], ensure_ascii=False)] if contract.get("image_intent") else []),
        *(["Module responsibility and design language: " + json.dumps(contract["module_language"], ensure_ascii=False)] if contract.get("module_language") else []),
        *(["Creative direction: " + json.dumps(contract["creative_brief"], ensure_ascii=False)] if contract.get("creative_brief") else []),
        *(["Selected design recipe: " + json.dumps(contract["design_recipe"], ensure_ascii=False)] if contract.get("design_recipe") else []),
        *design_execution(contract),
        "Evidence roles (product truth overrides style/pose): " + json.dumps(contract["references"], ensure_ascii=False),
        "Style/previous-image guidance (never product truth): " + json.dumps({k: contract.get(k, []) for k in ("style_references", "prior_candidate_references", "visual_system")}, ensure_ascii=False),
        "Locks/invariants: " + json.dumps({k: ([{field: value for field, value in lock.items() if field != "relations"} for lock in contract.get(k, [])] if k == "resolved_identity_locks" else contract.get(k, [])) for k in ("resolved_identity_locks", "required_lock_ids", "visual_invariants", "forbidden_changes")}, ensure_ascii=False),
        *(["Current-view structure relations: " + json.dumps(structure_requirements(contract), ensure_ascii=False)] if structure_requirements(contract) else []),
        "Pose, layout, hardware state and operation: " + json.dumps(contract["quality_contract"], ensure_ascii=False),
        "Approved copy only: " + json.dumps(contract.get("copy", {}), ensure_ascii=False),
        "Output: " + json.dumps(contract["output_requirements"], ensure_ascii=False),
        "Before delivery visually inspect: " + ", ".join(sorted(required_checks(contract))),
    ])


def focused_prompt(contract):
    """Generation facts only. Review history, QA bookkeeping and hashes stay on disk."""
    quality = contract["quality_contract"]
    sections = [
        *canvas_rules(contract),
        "Create one independent product image. Follow product evidence for identity; style and pose references cannot change structure.",
        "Added lettering may contain only Exact copy; actual product markings follow source. Never print catalog IDs, style names or instruction labels.",
        COPY_EXECUTION,
        "View: " + contract["target_view"],
        "Template: " + " ".join(contract["generation_template"]["prompt_rules"]),
        *design_execution(contract),
    ]
    payloads = {
        "Image purpose": contract.get("image_intent"),
        "Module responsibility and design language": contract.get("module_language"),
        "Creative direction": contract.get("creative_brief"),
        "Selected design recipe": contract.get("design_recipe"),
        "Sellable object": contract.get("sellable_object"),
        "Product facts": [x["fact"] for x in contract.get("resolved_identity_locks", []) if x.get("fact")],
        "Current-view structure relations": structure_requirements(contract),
        "Invariants": contract.get("visual_invariants"),
        "Forbidden changes": contract.get("forbidden_changes"),
        "Visual direction": contract.get("visual_system"),
        "Layout": quality.get("layout"),
        "People or hands permitted": quality.get("human", {}).get("present"),
        "Human pose": quality.get("human") if quality.get("human", {}).get("present") else None,
        "Visible hardware": [{"structure": x["structure_id"], "state": x["expected_state"], "visible_checks": x["visible_checks"]} for x in quality.get("structure_checks", [])],
        "Operation": {k: v for k, v in quality.get("mechanism", {}).items() if k not in {"evidence_paths", "verified_claim_ids"}} if quality.get("mechanism", {}).get("depicted") else None,
        "Exact copy": contract.get("copy"),
        "Output": contract.get("output_requirements"),
        "Current correction": contract.get("correction"),
    }
    for label, value in payloads.items():
        if value not in (None, "", [], {}):
            sections.append(label + ": " + json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(sections)


def qa_errors(root, contract, contract_path, candidate, report):
    errors = contract_state_errors(root, contract)
    errors.extend(observation_errors(contract, report))
    try:
        actual = digest(file_at(root, candidate.get("path")))
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors.extend(export_errors(root, file_at(root, candidate.get("path")), contract.get("output_requirements", {})))
    for key, expected in (("candidate_id", contract.get("candidate_id")), ("candidate_sha256", actual), ("contract_sha256", digest(contract_path))):
        if report.get(key) != expected:
            errors.append(f"QA {key} is stale or mismatched")
    if report.get("schema_version", 1) not in {1, 2}:
        errors.append("QA schema_version must be 1 or 2")
    if report.get("schema_version") == 2:
        try:
            expected = review_binding(root, contract, actual, report.get("comparison_images", []))
            if report.get("review_binding") != expected:
                errors.append("QA review_binding is stale: image, evidence, review context or rules changed")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"QA review_binding is invalid: {exc}")
        composition = composition_result(contract, report.get("composition"), actual)
        if composition["status"] != "PASS":
            errors.append(f"QA composition {composition['status']}: " + "; ".join(composition["reasons"]))
    if report.get("inspection_method") != "VISUAL_INSPECTION" or not report.get("reviewer"):
        errors.append("QA needs a named visual reviewer and VISUAL_INSPECTION method")
    checks = report.get("checks", {})
    if not isinstance(checks, dict):
        checks = {}
    for key in required_checks(contract):
        check = checks.get(key, {})
        if not isinstance(check, dict) or check.get("status") != "PASS" or not isinstance(check.get("observation"), str) or not check["observation"].strip():
            errors.append(f"QA {key} is not visually passed with an observation")
    for key, check in checks.items():
        if isinstance(check, dict) and check.get("status") in {"FAIL", "REVIEW_REQUIRED", "NOT_REVIEWED"}:
            errors.append(f"QA has unresolved check: {key}")
    if report.get("unresolved_items") != []:
        errors.append("QA has unresolved items or lacks unresolved_items")
    return errors


def review_status(root, contract, contract_path, candidate, report):
    """Read-only disposition of a saved review. No model call or acceptance write."""
    errors = qa_errors(root, contract, contract_path, candidate, report)
    invalid = (report.get("schema_version") != 2 or any(
        error.startswith(("A+ code export:", "missing file:", "unsafe package path:")) or "stale" in error or error.startswith("structure ") or "review_binding is invalid" in error for error in errors))
    result = {"execution": "INVALIDATED" if invalid else "REUSE", "status": "REVIEW_REQUIRED",
              "reason": "REVIEW_INPUTS_CHANGED" if invalid else "UNCHANGED_INPUT",
              "next_action": "REVIEW_CURRENT_IMAGE", "errors": errors}
    try:
        result["composition"] = composition_result(contract, report.get("composition"), digest(file_at(root, candidate.get("path"))))
    except (OSError, ValueError) as exc:
        result.update(execution="INVALIDATED", reason="FINAL_FILE_UNAVAILABLE", next_action="RECOVER_EXISTING_OUTPUT")
        result["errors"] = errors + [str(exc)]
        return result
    if invalid:
        if report.get("schema_version") != 2:
            result["reason"] = "LEGACY_REPORT_WITHOUT_REVIEW_BINDING"
        return result
    checks = report.get("checks", {})
    if not isinstance(checks, dict):
        checks = {}
    complete = all(isinstance(checks.get(key), dict) and checks[key].get("status") in {"PASS", "FAIL", "REVIEW_REQUIRED"}
                   and isinstance(checks[key].get("observation"), str) and checks[key]["observation"].strip()
                   for key in required_checks(contract))
    relation_observations = report.get("structure_observations", {})
    for key in structure_requirements(contract):
        item = relation_observations.get(key, {}) if isinstance(relation_observations, dict) else {}
        complete = complete and item.get("status") in {"PASS", "FAIL", "REVIEW_REQUIRED"} and bool(str(item.get("observation", "")).strip())
    if not complete:
        result.update(execution="REVIEW", reason="INCOMPLETE_REPORT", next_action="COMPLETE_CURRENT_REVIEW")
    elif any(isinstance(check, dict) and check.get("status") == "FAIL" for check in checks.values()) or any(error.startswith("QA composition FAIL:") for error in errors):
        result.update(status="FAIL", next_action="CORRECT_OR_REPLAN_CURRENT_IMAGE")
    elif any(isinstance(x, dict) and x.get("status") == "FAIL" for x in (relation_observations.values() if isinstance(relation_observations, dict) else [])):
        result.update(status="FAIL", next_action="CORRECT_OR_REPLAN_CURRENT_IMAGE")
    elif errors:
        result.update(next_action="RESOLVE_REVIEW_OR_REQUEST_HUMAN")
    else:
        result.update(status="PASS", next_action="AWAIT_REAL_HUMAN_DECISION")
    return result
