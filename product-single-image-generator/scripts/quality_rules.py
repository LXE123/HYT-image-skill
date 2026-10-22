"""Shared preflight and recorded visual-QA rules; these do not inspect pixels."""

import hashlib
import json
from pathlib import PurePosixPath
from finalize_a_plus_image import export_errors


BASE_CHECKS = {"product_identity", "structure_topology", "human_presence", "copy_claims", "layout_output"}

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
        "Locks/invariants: " + json.dumps({k: contract.get(k, []) for k in ("resolved_identity_locks", "required_lock_ids", "visual_invariants", "forbidden_changes")}, ensure_ascii=False),
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
    errors = []
    try:
        actual = digest(file_at(root, candidate.get("path")))
    except ValueError as exc:
        return [str(exc)]
    errors.extend(export_errors(root, file_at(root, candidate.get("path")), contract.get("output_requirements", {})))
    for key, expected in (("candidate_id", contract.get("candidate_id")), ("candidate_sha256", actual), ("contract_sha256", digest(contract_path))):
        if report.get(key) != expected:
            errors.append(f"QA {key} is stale or mismatched")
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
