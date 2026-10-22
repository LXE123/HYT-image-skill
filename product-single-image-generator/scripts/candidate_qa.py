#!/usr/bin/env python3
"""Create or validate a visual-inspection record without accepting a candidate."""

import argparse
import json
from pathlib import Path

from quality_rules import digest, file_at, qa_errors, required_checks
from context_store import load_contract
from finalize_a_plus_image import export_errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--report", required=True, help="package-relative QA JSON path")
    parser.add_argument("--init", action="store_true")
    args = parser.parse_args()
    root = args.package.resolve()
    try:
        contract_path = file_at(root, args.contract)
        contract = load_contract(root, contract_path)
        state = json.loads((root / "PRODUCT_STATE.json").read_text())
        candidate = next((x for x in state.get("candidates", []) if x.get("candidate_id") == contract.get("candidate_id")), None)
        candidate = candidate or {"candidate_id": contract["candidate_id"], "path": contract["output_path"]}
        image_path = file_at(root, candidate["path"])
        export_failures = export_errors(root, image_path, contract.get("output_requirements", {}))
        if export_failures:
            raise ValueError("; ".join(export_failures))
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
            report = {
                "schema_version": 1, "candidate_id": contract["candidate_id"],
                "candidate_sha256": digest(image_path), "contract_sha256": digest(contract_path),
                "inspection_method": "VISUAL_INSPECTION", "reviewer": "",
                "checks": {key: {"status": "NOT_REVIEWED", "observation": ""} for key in sorted(required_checks(contract))},
                "unresolved_items": [],
            }
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(f"CREATE  QA draft: {args.report}; inspect pixels before filling observations")
            return 0
        report = json.loads(file_at(root, args.report).read_text())
        errors = qa_errors(root, contract, contract_path, candidate, report)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        return 1
    print("PASS  recorded visual checks are complete and hashes match; human acceptance remains separate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
