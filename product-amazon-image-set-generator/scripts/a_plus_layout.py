"""Optional page grouping over existing one-image tasks; no competitor image input."""

from collections import Counter
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from set_common import SAFE_ID, load_json, module_stub

PROFILE_ID = "seven-module-desktop"


def profile():
    return load_json(Path(__file__).resolve().parents[1] / "assets/a-plus-seven-module-desktop.json")


def profile_drafts(count=9):
    if not 9 <= count <= 15:
        raise ValueError("desktop profile seeds 9-15 independent images")
    source = profile()
    layout = {k: deepcopy(v) for k, v in source.items() if k not in {"image_tasks", "additional_image_tasks"}}
    canvas = layout["canvas"]
    tasks = []
    selected = source["image_tasks"] + source["additional_image_tasks"][:count - 9]
    for task in selected[9:]:
        page = next((p for p in layout["page_modules"] if p["page_module_id"] == task["page_module_id"]), None)
        if page is None:
            page = {"page_module_id": task["page_module_id"], "sequence": len(layout["page_modules"]) + 1,
                    "display_type": "FULL_BACKGROUND_IMAGE", "content_role": "verified_use",
                    "sales_task": task["sales_task"], "buyer_question": task["buyer_question"], "image_ids": []}
            layout["page_modules"].append(page)
        page["image_ids"].append(task["module_id"])
        if len(page["image_ids"]) > 1:
            page["display_type"] = "CAROUSEL"
    for sequence, task in enumerate(selected, 1):
        item = module_stub(task["module_id"], "PREMIUM_A_PLUS", sequence,
                           task["sales_task"], task["buyer_question"], task["target_view"],
                           f"{canvas['width_px']}:{canvas['height_px']}", "as_planned",
                           template_id=task["template_id"])
        item["output_requirements"].update(canvas)
        item["visual_invariants"].append("Deliver one independent image for design-team assembly; depict only the evidenced current product.")
        item["forbidden_changes"].extend(["Do not draw carousel arrows, pagination dots, or Amazon page UI.",
                                          "Do not assemble multiple A+ page modules into one output."])
        tasks.append(item)
    return layout, tasks


def positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def layout_errors(plan, modules):
    errors = []
    for image in modules:
        if image.get("channel") != "PREMIUM_A_PLUS":
            continue
        output = image.get("output_requirements") or {}
        if not isinstance(output, dict) or any(not positive_int(output.get(k)) or output[k] != value for k, value in (("width_px", 1464), ("height_px", 600))):
            errors.append(f"A+ image {image.get('module_id')} requires only 1464x600")
            continue
        try:
            width, height = str(output.get("aspect_ratio", "")).split(":")
            if Fraction(width) / Fraction(height) != Fraction(1464, 600):
                raise ValueError()
        except (ValueError, ZeroDivisionError):
            errors.append(f"A+ image {image.get('module_id')} aspect_ratio must match 1464x600")
    if "a_plus_layout" not in plan:
        return errors
    layout = plan["a_plus_layout"]
    if not isinstance(layout, dict):
        return errors + ["a_plus_layout must be an object"]
    for field, expected in (("reference_scope", "STRUCTURE_ONLY"), ("delivery", "INDIVIDUAL_IMAGES"), ("assembly_owner", "DESIGN_TEAM")):
        if layout.get(field) != expected:
            errors.append(f"a_plus_layout.{field} must be {expected}")
    canvas = layout.get("canvas", {})
    if not isinstance(canvas, dict) or not all(positive_int(canvas.get(k)) for k in ("width_px", "height_px")):
        errors.append("a_plus_layout.canvas needs positive width_px and height_px")
        canvas = None
    elif canvas != {"width_px": 1464, "height_px": 600}:
        errors.append("a_plus_layout.canvas requires only 1464x600")
    pages = layout.get("page_modules")
    if not isinstance(pages, list) or not pages:
        return errors + ["a_plus_layout.page_modules must be a non-empty array"]
    images = {x["module_id"]: x for x in modules if x.get("channel") == "PREMIUM_A_PLUS"}
    seen_pages, seen_sequences, seen_images = set(), set(), set()
    for page in pages:
        if not isinstance(page, dict):
            errors.append("A+ page module must be an object")
            continue
        page_id = page.get("page_module_id")
        if not isinstance(page_id, str) or not SAFE_ID.fullmatch(page_id):
            errors.append("A+ page module needs a safe page_module_id")
            continue
        if page_id in seen_pages:
            errors.append(f"duplicate A+ page module: {page_id}")
        seen_pages.add(page_id)
        sequence = page.get("sequence")
        if not positive_int(sequence) or sequence in seen_sequences:
            errors.append(f"A+ page {page_id} needs a unique positive sequence")
        if positive_int(sequence):
            seen_sequences.add(sequence)
        for key in ("content_role", "sales_task", "buyer_question"):
            if not isinstance(page.get(key), str) or not page[key].strip():
                errors.append(f"A+ page {page_id} needs {key}")
        members = page.get("image_ids")
        if not isinstance(members, list) or not members:
            errors.append(f"A+ page {page_id} needs image_ids")
            continue
        kind = page.get("display_type")
        if kind not in {"FULL_BACKGROUND_IMAGE", "CAROUSEL"}:
            errors.append(f"A+ page {page_id} has an unsupported display_type")
        elif kind == "FULL_BACKGROUND_IMAGE" and len(members) != 1:
            errors.append(f"A+ page {page_id}: full background needs exactly one image")
        elif kind == "CAROUSEL" and len(members) < 2:
            errors.append(f"A+ page {page_id}: carousel needs at least two images")
        for image_id in members:
            if not isinstance(image_id, str) or image_id not in images:
                errors.append(f"A+ page {page_id} references unknown/non-A+ image {image_id!r}")
                continue
            if image_id in seen_images:
                errors.append(f"A+ image {image_id} belongs to multiple page positions")
            seen_images.add(image_id)
    missing = set(images) - seen_images
    if missing:
        errors.append(f"A+ images missing page membership: {', '.join(sorted(missing))}")
    if canvas:
        for image_id, image in images.items():
            output = image.get("output_requirements", {})
            if not isinstance(output, dict):
                errors.append(f"A+ image {image_id} needs output_requirements")
                continue
            if any(not positive_int(output.get(k)) or output[k] != canvas[k] for k in ("width_px", "height_px")):
                errors.append(f"A+ image {image_id} dimensions differ from the layout canvas")
            try:
                width, height = str(output.get("aspect_ratio", "")).split(":")
                ratio = Fraction(width) / Fraction(height)
                if ratio <= 0 or ratio != Fraction(canvas["width_px"], canvas["height_px"]):
                    raise ValueError()
            except (ValueError, ZeroDivisionError):
                errors.append(f"A+ image {image_id} aspect_ratio differs from the layout canvas")
    return errors


def image_membership(plan, image_id):
    for page in plan.get("a_plus_layout", {}).get("page_modules", []):
        if image_id in page["image_ids"]:
            return {k: page[k] for k in ("page_module_id", "display_type", "content_role")} | {
                "image_position": page["image_ids"].index(image_id) + 1,
                "image_count": len(page["image_ids"]),
            }
    return None


def layout_progress(plan, rows):
    """Derived status; it never creates an acceptance or changes image decisions."""
    by_id = {x["module_id"]: x for x in rows}
    result = []
    for page in sorted(plan.get("a_plus_layout", {}).get("page_modules", []), key=lambda x: x["sequence"]):
        required = [by_id.get(x, {"status": "PLANNED", "required": True}) for x in page["image_ids"]
                    if by_id.get(x, {}).get("required", True)]
        status = "OPTIONAL" if not required else "ACCEPTED" if all(x["status"] == "ACCEPTED" for x in required) else "PENDING"
        if any(x["status"] == "BLOCKED" for x in required):
            status = "BLOCKED"
        result.append({"page_module_id": page["page_module_id"], "status": status, "image_count": len(page["image_ids"])})
    return result


def layout_summary(plan, rows):
    pages = layout_progress(plan, rows)
    return {"page_modules": len(pages), "image_tasks": sum(x["image_count"] for x in pages),
            "page_status_counts": dict(Counter(x["status"] for x in pages))}


def design_handoff(plan, rows):
    """Small grouping manifest; designers receive separate files, never a stitched page."""
    layout = plan.get("a_plus_layout")
    by_id = {x["module_id"]: x for x in rows}
    def image_record(image_id):
        row = by_id.get(image_id, {})
        image = {"image_task_id": image_id, "status": row.get("status", "PLANNED")}
        if row.get("accepted_output"):
            image["accepted_output"] = row["accepted_output"]
        elif row.get("contract_path"):
            image["contract_path"] = row["contract_path"]
        return image
    pages = []
    for page in sorted((layout or {}).get("page_modules", []), key=lambda x: x["sequence"]):
        item = deepcopy(page)
        item["images"] = []
        for image_id in item.pop("image_ids"):
            item["images"].append(image_record(image_id))
        pages.append(item)
    result = {"set_id": plan["set_id"], "deliverable": plan.get("deliverable"), "delivery": "INDIVIDUAL_IMAGES", "page_modules": pages}
    if layout:
        result.update({"assembly_owner": layout["assembly_owner"], "canvas": layout["canvas"]})
    for channel, key in (("AMAZON_GALLERY", "gallery_images"), ("PREMIUM_A_PLUS", "a_plus_images")):
        if channel == "PREMIUM_A_PLUS" and layout:
            continue
        images = [image_record(x["module_id"]) for x in sorted(plan.get("modules", []), key=lambda x: x["sequence"]) if x["channel"] == channel]
        if images:
            result[key] = images
    return result
