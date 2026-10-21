"""Resolve pinned files in code; expose only a selected image to the model.

Legacy embedded records remain readable. Referenced contracts are envelopes,
not cached copies of templates, prompts, or previous conversation context.
"""

import json
from pathlib import Path

from quality_rules import compile_prompt, digest, file_at
from design_store import resolve_design
from module_language import resolve_module_language

MODULE_KEYS = ("module_id", "channel", "sequence", "required", "sales_task", "target_view")


def read_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def pinned(root, ref):
    if not isinstance(ref, dict):
        raise ValueError("missing pinned file reference")
    path = file_at(root, ref.get("path"))
    if digest(path) != ref.get("sha256"):
        raise ValueError(f"pinned file changed: {ref.get('path')}")
    return read_json(path)


def plan_modules(root, plan, module_id=None):
    rows = plan.get("modules", [])
    if not isinstance(rows, list):
        raise ValueError("plan modules must be an array")
    selected = [x for x in rows if isinstance(x, dict) and (module_id is None or x.get("module_id") == module_id)]
    if module_id and len(selected) != 1:
        raise ValueError(f"module not found or duplicated: {module_id}")
    if plan.get("schema_version", 1) < 2:
        return selected
    catalog = pinned(root, plan.get("template_catalog"))
    templates = {(x["template_id"], x["revision"]): x for x in catalog["templates"]}
    modules = []
    for row in selected:
        path = file_at(root, row.get("spec_path"))
        if plan.get("status") == "APPROVED" and digest(path) != row.get("spec_sha256"):
            raise ValueError(f"approved module spec changed: {row['module_id']}")
        spec = read_json(path)
        if spec.get("module_id") != row.get("module_id"):
            raise ValueError("module spec ID differs from plan row")
        if any(k in spec for k in (*MODULE_KEYS[1:], "generation_template", "template_id", "template_revision")):
            raise ValueError("module spec duplicates fields owned by the plan or template catalog")
        template = templates.get((row.get("template_id"), row.get("template_revision")))
        if template is None:
            raise ValueError(f"template version unavailable for {row.get('module_id')}")
        modules.append({**row, **spec, "generation_template": template})
    return modules


def load_contract(root, path):
    raw = read_json(path)
    if raw.get("storage_mode") != "REFERENCED":
        return raw
    forbidden = {"generation_template", "quality_contract", "generation_prompt", "resolved_identity_locks", "references", "visual_system", "copy"}
    if forbidden.intersection(raw):
        raise ValueError("referenced contract contains duplicated context fields")
    bindings = raw.get("bindings", {})
    plan = pinned(root, bindings.get("plan"))
    snapshot_ref = {"path": plan.get("input_snapshot"), "sha256": plan.get("approved_input_snapshot_sha256")}
    if "snapshot" in bindings and bindings["snapshot"] != snapshot_ref:
        raise ValueError("contract snapshot differs from approved plan")
    snapshot = pinned(root, snapshot_ref)
    link = raw.get("visual_set", {})
    if plan.get("status") != "APPROVED" or plan.get("set_id") != link.get("set_id") or bindings["plan"]["sha256"] != link.get("plan_sha256"):
        raise ValueError("contract binding differs from approved plan")
    module = plan_modules(root, plan, link.get("module_id"))[0]
    if raw.get("sku") != plan.get("sku") or raw.get("target_view") != module.get("target_view"):
        raise ValueError("contract SKU/view differs from module")
    lockset = snapshot.get("identity_lockset", {})
    if raw.get("identity_lockset_version") != lockset.get("version"):
        raise ValueError("contract lockset differs from pinned snapshot")
    locks = {x["lock_id"]: x for x in lockset.get("locks", [])}
    sources = {x["source_id"]: x for x in snapshot.get("commercial_manifest", {}).get("sources", [])}
    candidates = {x["candidate_id"]: x for x in snapshot.get("accepted_outputs", [])}
    scopes = {"STYLE_REFERENCE": "STYLE_ONLY", "COMPETITOR_REFERENCE": "MARKET_STYLE_ONLY", "BRAND_GUIDELINE": "BRAND_SYSTEM_ONLY"}
    style = [{"path": sources[x]["path"], "sha256": sources[x]["sha256"], "role": sources[x]["role"], "usage_scope": scopes[sources[x]["role"]]} for x in module.get("style_source_ids", [])]
    prior = [{k: candidates[x][k] for k in ("candidate_id", "path", "sha256", "status", "source_contract", "usage_scope")} for x in module.get("prior_candidate_ids", [])]
    contract = {
        **raw, "prompt_format": "focused-v1",
        "references": [*module.get("product_references", []), *module.get("pose_references", [])],
        "prior_candidate_references": prior, "style_references": style,
        "visual_system": plan.get("visual_system", {}),
        "sellable_object": snapshot.get("sellable_object", {}),
        "required_lock_ids": module["required_lock_ids"],
        "resolved_identity_locks": [locks[x] for x in module["required_lock_ids"]],
        "generation_template": module["generation_template"],
        "quality_contract": module["quality_contract"],
        "visual_invariants": module.get("visual_invariants", []),
        "forbidden_changes": module.get("forbidden_changes", []),
        "copy": module.get("copy", {}), "claim_ids": module.get("claim_ids", []),
        "claim_decisions": [x for x in plan.get("claims", []) if x.get("claim_id") in module.get("claim_ids", [])],
        "output_requirements": module["output_requirements"],
    }
    if plan.get("quantity_policy"):
        authored = module.get("image_intent") or {}
        intent = {k: authored[k] for k in ("module_role", "must_show", "product_facts") if k in authored}
        intent.update(sales_task=module["sales_task"], buyer_question=module["buyer_question"])
        for page in plan.get("a_plus_layout", {}).get("page_modules", []):
            if module["module_id"] in page["image_ids"]:
                intent["page_responsibility"] = {k: page[k] for k in ("content_role", "sales_task", "buyer_question")}
                intent["content_group_id"] = page["page_module_id"]
                break
        contract["image_intent"] = intent
    if plan.get("creative_policy_version") == 1:
        contract["creative_brief"] = module.get("creative_brief")
    if plan.get("design_policy_version"):
        contract["design_recipe"] = resolve_design(root, plan, module)
    if plan.get("module_language_policy_version") == 1:
        page = next((p for p in plan.get("a_plus_layout", {}).get("page_modules", []) if module["module_id"] in p["image_ids"]), None)
        contract["module_language_policy_version"] = 1
        contract["module_language"] = resolve_module_language(module, page)
    contract["generation_prompt"] = compile_prompt(contract)
    return contract
