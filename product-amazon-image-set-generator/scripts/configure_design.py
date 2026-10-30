#!/usr/bin/env python3
"""Choose pinned design recipes in an unproduced draft; never generate images."""

import argparse
import json
from pathlib import Path

from set_common import SAFE_ID, load_json, plan_modules, write_json
from project_store import transaction
from design_store import catalog_at, resolve_design


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--set-id", required=True)
    parser.add_argument("action", choices=("catalog", "configure", "select", "order"))
    parser.add_argument("--template-id", help="filter catalog layouts by image template")
    parser.add_argument("--style-id")
    parser.add_argument("--mode", choices=("adaptive", "catalog"), help="defaults to adaptive; an explicit --style-id retains catalog behavior")
    parser.add_argument("--framework-id")
    parser.add_argument("--rationale")
    parser.add_argument("--module-id")
    parser.add_argument("--layout-id")
    parser.add_argument("--story-stage")
    parser.add_argument("--channel", choices=("gallery", "a-plus"))
    parser.add_argument("--order", help="comma-separated Gallery image IDs or A+ page-module IDs")
    args = parser.parse_args()
    with transaction(args.package):
        return execute(args, parser)


def execute(args, parser):
    if not SAFE_ID.fullmatch(args.set_id):
        parser.error("unsafe set-id")
    root = args.package.resolve()
    folder = root / "visual_sets" / args.set_id
    try:
        plan = load_json(folder / "SET_PLAN.json")
        catalog = catalog_at(root, plan)
        if args.action == "catalog":
            result = {"layouts": [{k: x[k] for k in ("layout_id", "name", "templates", "image_role")} for x in catalog["layouts"]
                                  if not args.template_id or args.template_id in x["templates"]],
                      "styles": [{k: x[k] for k in ("style_id", "name")} for x in catalog["styles"]],
                      "narratives": catalog["narratives"]}
            print(json.dumps(result, ensure_ascii=False))
            return 0
        state = load_json(folder / "SET_STATE.json")
        if plan.get("status") != "DRAFT" or state.get("plan_sha256") or any(x.get("contract_path") for x in state.get("modules", [])):
            raise ValueError("design changes require an unproduced draft; revise approved plans instead")
        if plan.get("design_policy_version") != 1:
            raise ValueError("legacy plan: create a new design-policy revision instead of changing it in place")
        if args.action == "configure":
            if not args.rationale or not args.rationale.strip():
                raise ValueError("configure requires a product/audience-specific --rationale")
            framework_id = args.framework_id or "DIRECT"
            mode = args.mode or ("catalog" if args.style_id else "adaptive")
            if framework_id not in {x["framework_id"] for x in catalog["narratives"]}:
                raise ValueError("choose a catalog framework-id, or omit it for a direct image task")
            if mode == "catalog" and args.style_id not in {x["style_id"] for x in catalog["styles"]}:
                raise ValueError("catalog mode requires a catalog style-id")
            if mode == "adaptive" and args.style_id:
                raise ValueError("adaptive mode uses visual_system and per-image adjustments; omit --style-id")
            plan["design_system"] = {"mode": mode, "narrative_framework_id": framework_id, "rationale": args.rationale}
            if mode == "catalog":
                plan["design_system"]["style_id"] = args.style_id
            write_json(folder / "SET_PLAN.json", plan)
            result = {"design_system": plan["design_system"], "next_action": "RECONCILE_SHARED_STYLE_AND_SELECT_IMAGE_LAYOUTS"}
        elif args.action == "select":
            if not args.module_id or not SAFE_ID.fullmatch(args.module_id):
                raise ValueError("select requires a safe --module-id")
            module = plan_modules(root, plan, args.module_id)[0]
            layout = next((x for x in catalog["layouts"] if x["layout_id"] == args.layout_id), None)
            framework_id = plan.get("design_system", {}).get("narrative_framework_id")
            framework = next((x for x in catalog["narratives"] if x["framework_id"] == framework_id), None)
            adaptive_layout = plan.get("design_system", {}).get("mode") == "adaptive" and args.layout_id == "adaptive"
            if module["template_id"] == "main_product" and args.layout_id != "main_clean":
                raise ValueError("incompatible main-product layout: require main_clean")
            if not adaptive_layout and (not layout or module["template_id"] not in layout["templates"]):
                raise ValueError("layout is missing or incompatible with this image's template")
            if not framework or args.story_stage not in framework["stages"]:
                raise ValueError("configure a narrative first, then select one of its story stages")
            spec_path = (root / module["spec_path"]).resolve()
            spec_path.relative_to(root)
            spec = load_json(spec_path)
            spec.setdefault("creative_brief", {}).update({"layout_id": args.layout_id, "story_stage": args.story_stage})
            zones = {} if adaptive_layout else layout["zones"]["wide" if module["channel"] == "PREMIUM_A_PLUS" else "square"]
            spec["quality_contract"]["layout"].update(zones)
            write_json(spec_path, spec)
            preview = None
            if plan.get("design_system", {}).get("mode") != "adaptive" or spec["quality_contract"]["layout"].get("composition"):
                preview = resolve_design(root, plan, {**module, **spec}, catalog)
            result = {"module_id": args.module_id, "layout_id": args.layout_id, "story_stage": args.story_stage,
                      "layout_starting_points": zones, "design_preview": preview,
                      "next_action": "FILL_PRODUCT_SPECIFIC_CREATIVE_BRIEF_POSE_AND_COPY"}
        else:
            if not args.channel or not args.order:
                raise ValueError("order requires --channel and --order")
            ids = args.order.split(",")
            if len(ids) != len(set(ids)) or not all(SAFE_ID.fullmatch(x) for x in ids):
                raise ValueError("order needs unique safe IDs")
            channel = "AMAZON_GALLERY" if args.channel == "gallery" else "PREMIUM_A_PLUS"
            selected = {x["module_id"]: x for x in plan["modules"] if x["channel"] == channel}
            if args.channel == "a-plus" and plan.get("a_plus_layout"):
                pages = {x["page_module_id"]: x for x in plan["a_plus_layout"]["page_modules"]}
                if set(ids) != set(pages):
                    raise ValueError("grouped A+ order must include every page-module ID exactly once")
                for sequence, page_id in enumerate(ids, 1):
                    pages[page_id]["sequence"] = sequence
                plan["a_plus_layout"]["page_modules"] = [pages[x] for x in ids]
                image_ids = [image_id for page_id in ids for image_id in pages[page_id]["image_ids"]]
            else:
                if set(ids) != set(selected):
                    raise ValueError("order must include every selected channel image ID exactly once")
                image_ids = ids
            if set(image_ids) != set(selected):
                raise ValueError("page membership differs from channel image tasks")
            for sequence, image_id in enumerate(image_ids, 1):
                selected[image_id]["sequence"] = sequence
            plan["modules"] = [x for x in plan["modules"] if x["channel"] != channel] + [selected[x] for x in image_ids]
            plan["modules"].sort(key=lambda x: (x["channel"] != "AMAZON_GALLERY", x["sequence"]))
            write_json(folder / "SET_PLAN.json", plan)
            result = {"channel": args.channel, "ordered_images": image_ids, "next_action": "REVIEW_NARRATIVE_AND_VALIDATE_PLAN"}
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    from runtime_log import run_cli
    raise SystemExit(run_cli(main))
