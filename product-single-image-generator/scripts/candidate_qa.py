#!/usr/bin/env python3
"""Create or validate a visual-inspection record without accepting a candidate."""

from structure_state import structure_requirements
import argparse
import json
from pathlib import Path

from quality_rules import digest, file_at, review_binding, review_status, required_checks
from context_store import load_contract
from finalize_a_plus_image import export_errors



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--report", required=True, help="package-relative QA JSON path")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--init", action="store_true")
    mode.add_argument("--status", action="store_true", help="read saved review validity and next action; never run a visual model")
    parser.add_argument("--comparison-image", action="append", default=[], help="package-relative image inspected for set continuity; repeat at initialization")
    parser.add_argument("--source-image", help="initialize a SOURCE_IMAGE crop review for this package-relative generated original")
    args = parser.parse_args()
    if args.comparison_image and not args.init:
        parser.error("comparison images must be bound when initializing a new report")
    if args.source_image and not args.init:
        parser.error("--source-image is only for initializing a source crop review")
    root = args.package.resolve()
    try:
        contract_path = file_at(root, args.contract)
        contract = load_contract(root, contract_path)
        state = json.loads((root / "PRODUCT_STATE.json").read_text())
        candidate = next((x for x in state.get("candidates", []) if x.get("candidate_id") == contract.get("candidate_id")), None)
        candidate = candidate or {"candidate_id": contract["candidate_id"], "path": contract["output_path"]}
        image_path = file_at(root, args.source_image or candidate["path"])
        # Use the same path guard for a not-yet-created report.
        from pathlib import PurePosixPath
        rel = PurePosixPath(args.report)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("report must be package-relative")
        report_path = (root / rel).resolve()
        report_path.relative_to((root / "qa").resolve())
        if args.init:
            if report_path.exists():
                raise ValueError("report exists; it was not overwritten")
            export_failures = [] if args.source_image else export_errors(root, image_path, contract.get("output_requirements", {}))
            if export_failures:
                raise ValueError("; ".join(export_failures))
            image_hash = digest(image_path)
            comparison_images = [{"path": path} for path in args.comparison_image]
            report = {
                "schema_version": 2, "candidate_id": contract["candidate_id"],
                "phase": "SOURCE_IMAGE" if args.source_image else "FINAL_IMAGE",
                "candidate_sha256": image_hash, "contract_sha256": digest(contract_path),
                "review_binding": review_binding(root, contract, image_hash, comparison_images), "comparison_images": comparison_images,
                "composition": {"coordinate_space": "SOURCE_IMAGE" if args.source_image else "FINAL_IMAGE", "image_sha256": image_hash,
                                "annotation_method": "", "boundary_certainty": "UNCERTAIN",
                                "required_content": "NOT_REVIEWED",
                                "product_regions": [], "copy_regions": [], "protected_regions": []},
                "inspection_method": "VISUAL_INSPECTION", "reviewer": "",
                "checks": {key: {"status": "NOT_REVIEWED", "observation": ""} for key in sorted({"layout_output", "design_quality"} if args.source_image else required_checks(contract))},
                "unresolved_items": [],
            }
            if not args.source_image and structure_requirements(contract):
                report["structure_observations"] = {key: {"status": "NOT_REVIEWED", "observation": ""} for key in structure_requirements(contract)}
            if args.source_image:
                report["reviewed_crop_box"] = None
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(f"CREATE  QA draft: {args.report}; inspect pixels before filling observations")
            return 0
        report = json.loads(file_at(root, args.report).read_text())
        result = review_status(root, contract, contract_path, candidate, report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if args.status or result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
