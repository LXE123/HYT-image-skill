"""Resolve one pinned visual recipe; do not forward a complete design catalog."""

import json
from collections import defaultdict

from quality_rules import digest, file_at
from module_language import resolve_module_language


def adaptive_recipe(system, module, catalog, brief, framework):
    """Resolve input-led choices; catalog layouts are optional starting points."""
    layout_id = brief.get("layout_id")
    template_id = module["generation_template"]["template_id"]
    if template_id == "main_product" and layout_id != "main_clean":
        raise ValueError("main-product images require main_clean")
    layout = next((x for x in catalog["layouts"] if x["layout_id"] == layout_id), None)
    if layout_id != "adaptive" and (layout is None or template_id not in layout["templates"]):
        raise ValueError("choose adaptive or a compatible starting layout")
    composition = module.get("quality_contract", {}).get("layout", {}).get("composition")
    if not isinstance(composition, str) or not composition.strip():
        raise ValueError("adaptive design requires an actual image composition")
    adjustments = brief.get("design_adjustments", {})
    allowed = {"palette", "lighting", "typography", "background", "graphics"}
    if not isinstance(adjustments, dict) or set(adjustments) - allowed:
        raise ValueError("design_adjustments must contain supported visual dimensions")
    if any(not isinstance(v, (str, list)) or not v for v in adjustments.values()):
        raise ValueError("design_adjustments values must be nonempty text or lists")
    influences = brief.get("reference_influences", [])
    if not isinstance(influences, list):
        raise ValueError("reference_influences must be an array")
    for item in influences:
        if not isinstance(item, dict) or item.get("source_id") not in module.get("style_source_ids", []):
            raise ValueError("reference influence must use this image's registered style source")
        if item.get("strength") not in {"low", "medium", "high"} or any(
            not isinstance(item.get(k), str) or not item[k].strip() for k in ("element", "reason")
        ):
            raise ValueError("reference influence needs element, strength and reason")
    return {
        "mode": "adaptive",
        "layout": {"layout_id": layout_id, "composition": composition,
                   "starting_point": ({k: layout[k] for k in ("composition_rules", "copy_guidance")} if layout else None)},
        "style": {"source": "shared visual_system plus current-image decisions", "task_adjustments": adjustments},
        "reference_influences": influences,
        "narrative": {"framework_id": system["narrative_framework_id"], "stage": brief["story_stage"],
                      "current_job": module.get("buyer_question") or framework["stages"][brief["story_stage"]]},
        "priority": "Product facts and explicit requirements first; main-image constraints retain priority. Shared visual_system bounds background lightness/colour, white balance, contrast/shadows and type. Local decisions, references and catalog layouts refine within it; vary composition and scene. References never change product truth; strength labels are planning intent.",
    }


def catalog_at(root, plan):
    ref = plan.get("design_catalog")
    if not isinstance(ref, dict):
        raise ValueError("design_catalog needs a pinned path and sha256")
    path = file_at(root, ref.get("path"))
    if digest(path) != ref.get("sha256"):
        raise ValueError("pinned design catalog changed")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.get("revision") != 1:
        raise ValueError("unsupported design catalog")
    return catalog


def resolve_design(root, plan, module, catalog=None):
    if not plan.get("design_policy_version"):
        return None
    catalog = catalog or catalog_at(root, plan)
    system = plan.get("design_system", {})
    brief = module.get("creative_brief") or {}
    if not isinstance(system, dict) or not isinstance(brief, dict):
        raise ValueError("design_system and creative_brief must be objects")
    layout_id, stage = brief.get("layout_id"), brief.get("story_stage")
    style_id, framework_id = system.get("style_id"), system.get("narrative_framework_id")
    adaptive = system.get("mode", "catalog") == "adaptive"
    if system.get("mode", "catalog") not in {"catalog", "adaptive"}:
        raise ValueError("unknown design mode")
    if not all((layout_id, stage, framework_id)) or (not adaptive and not style_id):
        if plan.get("status") == "DRAFT":
            return None
        raise ValueError("approved image has incomplete design selection")
    layout = next((x for x in catalog["layouts"] if x["layout_id"] == layout_id), None)
    style = next((x for x in catalog["styles"] if x["style_id"] == style_id), None)
    framework = next((x for x in catalog["narratives"] if x["framework_id"] == framework_id), None)
    if adaptive:
        if framework is None or stage not in framework["stages"]:
            raise ValueError("unknown narrative stage")
        return adaptive_recipe(system, module, catalog, brief, framework)
    if layout is None or style is None or framework is None or stage not in framework["stages"]:
        raise ValueError(f"unknown layout/style/story stage for {module.get('module_id')}")
    template_id = module["generation_template"]["template_id"]
    if template_id not in layout["templates"]:
        raise ValueError(f"layout {layout_id} is incompatible with template {template_id}")
    role = layout["image_role"]
    return {
        "layout": {k: layout[k] for k in ("layout_id", "name", "composition_rules", "copy_guidance")},
        "style": {**{k: style[k] for k in ("style_id", "name", "palette_roles", "typography", "lighting")},
                  "task_treatment": style["treatments"][role]},
        "narrative": {"framework_id": framework_id, "stage": stage, "current_job": framework["stages"][stage]},
        "priority": "Facts, evidence, brand and main-image requirements first. Shared visual_system bounds background tone, light and type; local styles refine within it. Keep exact copy and product colours.",
    }


def design_plan_checks(root, plan, modules):
    if not plan.get("design_policy_version"):
        return [], []
    errors, warnings = [], []
    if plan["design_policy_version"] != 1:
        return ["unsupported design_policy_version"], []
    try:
        catalog = catalog_at(root, plan)
    except (OSError, ValueError, KeyError) as error:
        return [str(error)], []
    system = plan.get("design_system", {})
    if not isinstance(system, dict):
        return ["design_system must be an object"], []
    keys = ("narrative_framework_id", "rationale") if system.get("mode") == "adaptive" else ("style_id", "narrative_framework_id", "rationale")
    for key in keys:
        if not isinstance(system.get(key), str) or not system[key].strip():
            errors.append(f"design_system.{key} must be planned before approval")
    by_channel = defaultdict(list)
    for module in modules:
        brief = module.get("creative_brief") or {}
        if not isinstance(brief, dict) or not brief.get("layout_id") or not brief.get("story_stage"):
            errors.append(f"module {module['module_id']} needs layout_id and story_stage")
            continue
        try:
            recipe = resolve_design(root, {**plan, "status": "APPROVED"}, module, catalog)
        except (ValueError, KeyError, TypeError) as error:
            errors.append(str(error))
        else:
            if module["generation_template"]["template_id"] != "main_product" and recipe["layout"]["layout_id"] != "adaptive":
                by_channel[module["channel"]].append((module["sequence"], recipe["layout"]["layout_id"]))
    for channel, rows in by_channel.items():
        layouts = [x[1] for x in sorted(rows)]
        if any(len(set(layouts[i:i + 3])) == 1 for i in range(len(layouts) - 2)):
            warnings.append(f"{channel}: three consecutive images repeat a layout; review the set rhythm or explain the repetition")
    if plan.get("module_language_policy_version") == 1:
        shared_expressions = defaultdict(list)
        for module in modules:
            page = next((p for p in plan.get("a_plus_layout", {}).get("page_modules", []) if module["module_id"] in p["image_ids"]), None)
            brief = module.get("creative_brief") or {}
            signature = tuple(str(x).strip() for x in (brief.get("visual_device", ""), brief.get("graphic_treatment", ""), module.get("quality_contract", {}).get("layout", {}).get("composition", "")))
            if all(signature):
                language = resolve_module_language(module, page)
                shared_expressions[(module.get("channel"), signature)].append((module["module_id"], language["role"]))
        for rows in shared_expressions.values():
            if len({role for _, role in rows}) > 1:
                warnings.append("Different module responsibilities share the exact same device, graphic treatment and composition: " + ", ".join(mid for mid, _ in rows) + "; review role-specific expression, not just palette consistency")
    return errors, warnings
