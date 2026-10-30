#!/usr/bin/env python3
"""Add an independent image to a draft A+ group without renaming existing tasks."""

import argparse
from copy import deepcopy
from pathlib import Path

from a_plus_layout import layout_errors
from set_common import MAX_CHANNEL_IMAGES, EXPANDED_MIN_IMAGES, SAFE_ID, generation_templates, load_json, module_stub, plan_modules, store_module_spec, write_json
from project_store import transaction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--set-id", required=True)
    parser.add_argument("--page-module-id", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--template-id", required=True, choices=tuple(generation_templates()))
    parser.add_argument("--target-view", required=True)
    parser.add_argument("--sales-task", required=True)
    parser.add_argument("--buyer-question", required=True)
    parser.add_argument("--after-image-id", help="insert after this image in an existing group; otherwise append")
    parser.add_argument("--new-page", action="store_true")
    parser.add_argument("--content-role", help="required for a new page")
    parser.add_argument("--after-page-id", help="insert a new page after this page; otherwise append")
    parser.add_argument("--activate-expanded", action="store_true", help="explicitly opt this draft into 30-40 image production")
    args = parser.parse_args()
    with transaction(args.package):
        return execute(args, parser)


def execute(args, parser):
    for value in (args.set_id, args.page_module_id, args.image_id, args.target_view):
        if not SAFE_ID.fullmatch(value):
            parser.error("unsafe set/page/image/view ID")
    if not args.sales_task.strip() or not args.buyer_question.strip():
        parser.error("sales-task and buyer-question must be non-empty")
    root = args.package.resolve()
    folder = root / "visual_sets" / args.set_id
    try:
        plan = load_json(folder / "SET_PLAN.json")
        state = load_json(folder / "SET_STATE.json")
        if plan.get("status") != "DRAFT" or state.get("plan_sha256") or any(x.get("contract_path") for x in state.get("modules", [])):
            raise ValueError("only an unproduced draft can be extended; create a new revision for an approved set")
        if plan.get("schema_version", 1) < 2 or not plan.get("a_plus_layout"):
            raise ValueError("requires a schema-2 draft with a_plus_layout")
        modules = plan_modules(root, plan)
        failures = layout_errors(plan, modules)
        if failures:
            raise ValueError("; ".join(failures))
        if any(x["module_id"] == args.image_id for x in plan["modules"]):
            raise ValueError("image-id already exists; existing task was not overwritten")
        a_plus_count = sum(x["channel"] == "PREMIUM_A_PLUS" for x in modules)
        if a_plus_count >= MAX_CHANNEL_IMAGES:
            raise ValueError(f"this workflow supports at most {MAX_CHANNEL_IMAGES} A+ images")
        if args.activate_expanded:
            plan["generation_mode"] = "expanded"
        if a_plus_count + 1 >= EXPANDED_MIN_IMAGES and plan.get("generation_mode", "standard") != "expanded":
            raise ValueError("30-40 A+ images require explicit --activate-expanded or a new expanded-mode set")
        layout = plan["a_plus_layout"]
        pages = sorted(layout["page_modules"], key=lambda x: x["sequence"])
        page = next((x for x in pages if x["page_module_id"] == args.page_module_id), None)
        if args.new_page:
            if page or not args.content_role or not args.content_role.strip() or args.after_image_id:
                raise ValueError("new-page requires a new page ID, content-role and no after-image-id")
            page = {"page_module_id": args.page_module_id, "display_type": "FULL_BACKGROUND_IMAGE",
                    "content_role": args.content_role, "sales_task": args.sales_task,
                    "buyer_question": args.buyer_question, "image_ids": [args.image_id]}
            position = len(pages)
            if args.after_page_id:
                predecessor = next((i for i, x in enumerate(pages) if x["page_module_id"] == args.after_page_id), None)
                if predecessor is None:
                    raise ValueError("after-page-id does not exist")
                position = predecessor + 1
            pages.insert(position, page)
        else:
            if not page or args.after_page_id or args.content_role:
                raise ValueError("select an existing page, or use new-page for a new content responsibility")
            position = len(page["image_ids"])
            if args.after_image_id:
                if args.after_image_id not in page["image_ids"]:
                    raise ValueError("after-image-id is not in this page")
                position = page["image_ids"].index(args.after_image_id) + 1
            page["image_ids"].insert(position, args.image_id)
            page["display_type"] = "CAROUSEL"
        for sequence, item in enumerate(pages, 1):
            item["sequence"] = sequence
        layout["page_modules"] = pages
        ordered_ids = [image_id for item in pages for image_id in item["image_ids"]]
        canvas = layout["canvas"]
        draft = module_stub(args.image_id, "PREMIUM_A_PLUS", ordered_ids.index(args.image_id) + 1,
                            args.sales_task, args.buyer_question, args.target_view,
                            f"{canvas['width_px']}:{canvas['height_px']}", "as_planned", template_id=args.template_id)
        draft["output_requirements"].update(canvas)
        draft["visual_invariants"] = ["Deliver one independent image for design-team assembly; depict only the evidenced current product."]
        draft["forbidden_changes"] = ["Do not draw carousel arrows, pagination dots, or Amazon page UI.",
                                      "Do not assemble multiple A+ page modules into one output."]
        failures = layout_errors(plan, [*modules, draft])
        if failures:
            raise ValueError("; ".join(failures))
        row = store_module_spec(root, folder, draft)
        rows = {x["module_id"]: x for x in [*plan["modules"], row] if x["channel"] == "PREMIUM_A_PLUS"}
        for sequence, image_id in enumerate(ordered_ids, 1):
            rows[image_id]["sequence"] = sequence
        plan["modules"] = [x for x in plan["modules"] if x["channel"] != "PREMIUM_A_PLUS"] + [rows[x] for x in ordered_ids]
        if "selected_counts" in plan.get("quantity_policy", {}):
            plan["quantity_policy"]["selected_counts"]["PREMIUM_A_PLUS"] = len(ordered_ids)
        saved = {x["module_id"]: x for x in state.get("modules", [])}
        state["modules"] = [deepcopy(saved.get(x["module_id"], {"module_id": x["module_id"], "status": "PLANNED"})) for x in plan["modules"]]
        state["next_action"] = "COMPLETE_COMMERCIAL_INPUTS_AND_PLAN"
        write_json(folder / "SET_PLAN.json", plan)
        write_json(folder / "SET_STATE.json", state)
        print(f"ADD  image={args.image_id} page={args.page_module_id}; {len(pages)} page modules, {len(ordered_ids)} independent A+ images")
        print("DRAFT  fill this image's product evidence, claims, composition and quality fields before approval")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
