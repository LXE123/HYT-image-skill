"""Shared helpers for Amazon visual-set records."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

# Candidate QA belongs to the sibling production skill. Keep one rule implementation.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "product-single-image-generator" / "scripts"))
from quality_rules import compile_prompt, file_at, qa_errors, validate_quality
from context_store import MODULE_KEYS, load_contract, plan_modules


def generation_templates() -> dict:
    catalog = load_json(Path(__file__).resolve().parents[1] / "assets/generation-templates.json")
    return {item["template_id"]: item for item in catalog["templates"]}


def module_quality_errors(root: Path, module: dict, index: dict, locks: dict) -> list[str]:
    template = module.get("generation_template", {})
    if not isinstance(template, dict) or (not module.get("spec_path") and template != generation_templates().get(template.get("template_id"))):
        return ["generation_template must match a versioned catalog entry; put custom composition in quality_contract.layout"]
    return validate_quality(root, module, index, locks)


def store_module_spec(root: Path, set_root: Path, module: dict) -> dict:
    """Split a draft once; subsequent planning edits just this image's spec."""
    path = set_root / "modules" / f"{module['module_id']}.json"
    if path.exists():
        raise ValueError(f"module spec exists; edit its draft explicitly: {path}")
    template = module["generation_template"]
    spec = {k: v for k, v in module.items() if k not in {*MODULE_KEYS[1:], "generation_template"}}
    write_json(path, spec)
    return {**{k: module[k] for k in MODULE_KEYS}, "template_id": template["template_id"], "template_revision": template["revision"], "spec_path": path.relative_to(root).as_posix()}


SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
SOURCE_ROLES = {
    "LISTING_COPY",
    "PRODUCT_SPEC",
    "CLAIM_EVIDENCE",
    "BRAND_GUIDELINE",
    "MARKETPLACE_RULE",
    "STYLE_REFERENCE",
    "POSE_REFERENCE",
    "COMPETITOR_REFERENCE",
}

MAX_CHANNEL_IMAGES = 40
MAX_SET_IMAGES = 80
EXPANDED_MIN_IMAGES = 30
NORMAL_MIN_IMAGES = 9
NORMAL_MAX_IMAGES = 15
NORMAL_TARGET_IMAGES = 13


def generation_mode_errors(plan: dict) -> list[str]:
    """New plans explicitly opt into large sets; legacy plans keep their scope."""
    if "generation_mode" not in plan:
        return []
    mode = plan["generation_mode"]
    if mode not in {"standard", "expanded"}:
        return ["generation_mode must be standard or expanded"]
    modules = plan.get("modules", [])
    if not isinstance(modules, list):
        return ["modules must be an array"]
    count = len(modules)
    counts = {channel: sum(isinstance(x, dict) and x.get("channel") == channel for x in modules)
              for channel in ("AMAZON_GALLERY", "PREMIUM_A_PLUS")}
    selected_counts = plan.get("quantity_policy", {}).get("selected_counts")
    if selected_counts is not None:
        if (not isinstance(selected_counts, dict) or set(selected_counts) != set(counts)
                or any(not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= MAX_CHANNEL_IMAGES
                       for n in selected_counts.values())):
            return ["quantity_policy.selected_counts needs valid per-channel image counts"]
        if selected_counts != counts:
            return [f"image-task counts {counts} differ from selected image counts {selected_counts}; page groups are not output files"]
    if "deliverable" in plan:
        selected = {"gallery": {"AMAZON_GALLERY"}, "a-plus": {"PREMIUM_A_PLUS"},
                    "both": {"AMAZON_GALLERY", "PREMIUM_A_PLUS"}}.get(plan["deliverable"])
        if selected is None or {channel for channel, value in counts.items() if value} != selected:
            return ["image channels differ from the selected deliverable"]
    if count > MAX_SET_IMAGES or any(value > MAX_CHANNEL_IMAGES for value in counts.values()):
        return [f"new sets support at most {MAX_CHANNEL_IMAGES} images per channel"]
    if any(value >= EXPANDED_MIN_IMAGES for value in counts.values()) and mode != "expanded":
        return ["30-40 images in one channel require explicit expanded mode"]
    return []


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def safe_relative(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not PurePosixPath(value).is_absolute() and ".." not in PurePosixPath(value).parts


def resolve_file(root: Path, value: object) -> Path:
    if not safe_relative(value):
        raise ValueError(f"unsafe root-relative path: {value!r}")
    result = (root / str(value)).resolve()
    result.relative_to(root)
    if not result.is_file():
        raise ValueError(f"file does not exist: {value}")
    return result


def update_product_summary(product_state: dict, set_state: dict) -> None:
    summaries = product_state.setdefault("visual_sets", [])
    if not isinstance(summaries, list):
        raise ValueError("PRODUCT_STATE.json visual_sets must be an array")
    summary = {
        "set_id": set_state["set_id"],
        "marketplace": set_state["marketplace"],
        "status": set_state["status"],
        "plan_revision": set_state["plan_revision"],
        "plan_path": set_state["plan_path"],
        "state_path": f"visual_sets/{set_state['set_id']}/SET_STATE.json",
        "next_action": set_state["next_action"],
    }
    current = next((item for item in summaries if isinstance(item, dict) and item.get("set_id") == set_state["set_id"]), None)
    if current is None:
        summaries.append(summary)
    else:
        current.clear()
        current.update(summary)


def default_modules(gallery_count: int, a_plus_count: int) -> list[dict]:
    gallery_tasks = [
        ("Main image", "What exactly is being sold?", "front_3q", "white"),
        ("Product overview", "What does the complete product look like?", "alternate_full", "as_planned"),
        ("Material proof", "What does the material and surface look like?", "material_macro", "as_planned"),
        ("Signature detail", "What makes this product distinctive?", "detail", "as_planned"),
        ("Construction", "How are the hardware and edges finished?", "construction_detail", "as_planned"),
        ("Installation or adjustment", "How is it installed or adjusted?", "use_detail", "as_planned"),
        ("Compatibility and fit", "Will it fit the intended device or use?", "compatibility", "as_planned"),
        ("Primary lifestyle", "How does it fit the primary customer's life?", "lifestyle_primary", "as_planned"),
        ("Secondary lifestyle or range", "What additional style or gifting value does it offer?", "lifestyle_secondary", "as_planned"),
    ]
    a_plus_tasks = [
        ("Brand and product hero", "What is the product's overall promise?", "brand_hero"),
        ("Material story", "Why does the material matter?", "material_story"),
        ("Signature detail", "Which detail best expresses differentiation?", "signature_detail"),
        ("Craftsmanship", "How is the product constructed and finished?", "craftsmanship"),
        ("Comfort or use experience", "How does it feel or behave in use?", "use_experience"),
        ("Installation or adjustment", "How does the mechanism work?", "installation"),
        ("Compatibility or size", "Which version or size is right?", "size_guidance"),
        ("Lifestyle integration", "Where does the product naturally belong?", "lifestyle"),
        ("Range, gift, or closing", "Why is this the right final choice?", "closing"),
    ]
    gallery_extras = [
        ("Supported functional detail", "Which evidenced functional detail matters in use?", "functional_detail", "material_macro"),
        ("Additional construction proof", "Which second construction detail supports the product's value?", "construction_alternate", "hardware_static"),
        ("Active lifestyle", "How does the product fit a relevant active situation?", "lifestyle_active", "lifestyle_simple"),
        ("Everyday lifestyle", "How does the product fit a distinct everyday situation?", "lifestyle_everyday", "lifestyle_simple"),
        ("Work or study context", "How is the product used in an evidenced work or study context?", "lifestyle_work", "lifestyle_simple"),
        ("Alternate signature detail", "What additional non-repeating detail helps the buyer decide?", "detail_alternate", "hardware_static"),
    ]
    modules: list[dict] = []
    for sequence in range(1, gallery_count + 1):
        if 10 <= sequence <= 15:
            task, question, view, template_id = gallery_extras[sequence - 10]
            modules.append(module_stub(f"gallery-{sequence:02d}", "AMAZON_GALLERY", sequence, task, question, view, "1:1", "as_planned", template_id=template_id))
            continue
        task, question, view, background = gallery_tasks[min(sequence - 1, len(gallery_tasks) - 1)]
        modules.append(module_stub(f"gallery-{sequence:02d}", "AMAZON_GALLERY", sequence, task, question, view, "1:1", background))
    for sequence in range(1, a_plus_count + 1):
        task, question, view = a_plus_tasks[min(sequence - 1, len(a_plus_tasks) - 1)]
        item = module_stub(f"a-plus-{sequence:02d}", "PREMIUM_A_PLUS", sequence, task, question, view, "1464:600", "as_planned")
        item["output_requirements"].update(width_px=1464, height_px=600)
        modules.append(item)
    return modules


def module_stub(module_id: str, channel: str, sequence: int, task: str, question: str, view: str, ratio: str, background: str, template_id: str | None = None) -> dict:
    gallery = ["main_product", "product_overview", "material_macro", "hardware_static", "hardware_static", "mechanism_steps", "size_fit", "lifestyle_simple", "range_story"]
    a_plus = ["product_overview", "material_macro", "hardware_static", "hardware_static", "lifestyle_simple", "mechanism_steps", "size_fit", "lifestyle_simple", "range_story"]
    template_id = template_id or (gallery if channel == "AMAZON_GALLERY" else a_plus)[min(sequence - 1, 8)]
    template = generation_templates()[template_id]
    main = template_id == "main_product"
    return {
        "module_id": module_id,
        "channel": channel,
        "sequence": sequence,
        "required": True,
        "sales_task": task,
        "buyer_question": question,
        "target_view": view,
        "product_references": [],
        "pose_references": [],
        "style_source_ids": [],
        "prior_candidate_ids": [],
        "required_lock_ids": [],
        "claim_ids": [],
        "creative_brief": {
            "layout_id": "main_clean" if main else "adaptive",
            "story_stage": "single_message",
            "visual_concept": "",
            "visual_device": "",
            "information_hierarchy": [],
            "graphic_treatment": "",
            "set_role": "",
            "success_criteria": [],
        },
        "generation_template": template,
        "quality_contract": {
            "version": 1,
            "layout": {
                "product_box": [0.06, 0.06, 0.94, 0.94] if main else [0.0, 0.0, 1.0, 1.0],
                "copy_box": None,
                "composition": "Complete product centered on white; no copy" if main else "",
            },
            "human": {"present": template["requires_human"], "pose_description": "", "visible_limbs": [], "contact_points": [], "occlusion_order": []},
            "structure_checks": [],
            "visible_hardware": [],
            "mechanism": {"depicted": template["requires_mechanism"], "action": "", "structure_id": "", "start_state": "", "end_state": "", "evidence_paths": [], "verified_claim_ids": []},
        },
        "visual_invariants": [],
        "forbidden_changes": [],
        "copy": {"title": "", "subtitle": "", "labels": []},
        "output_requirements": {"format": "PNG", "aspect_ratio": ratio, "background": background},
    }
