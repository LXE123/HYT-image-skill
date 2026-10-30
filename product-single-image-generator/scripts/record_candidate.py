#!/usr/bin/env python3
"""Record an image decision; visual QA and real human decisions remain distinct."""

import argparse
import json
from pathlib import Path

from context_store import load_contract
from quality_rules import digest, file_at, qa_errors
from finalize_a_plus_image import export_errors
from structure_state import dependency_errors
from project_store import read_json, write_json, finish_claim, transaction


def record_candidate(root, contract_address, decision, *, candidate_path=None, failure_code=None,
                     report_address=None, human_reviewer=None, decision_reference=None, claim_token=None):
    with transaction(root):
        return _record_candidate(root, contract_address, decision, candidate_path, failure_code,
                                 report_address, human_reviewer, decision_reference, claim_token)


def _record_candidate(root, contract_address, decision, candidate_path, failure_code,
                      report_address, human_reviewer, decision_reference, claim_token):
    product = read_json(root / "PRODUCT_STATE.json")
    path = file_at(root, contract_address)
    contract = load_contract(root, path)
    if not decision.startswith("REJECTED"):
        failures = dependency_errors(product, contract.get("required_lock_ids"), contract.get("resolved_identity_locks"))
        if failures:
            raise ValueError("; ".join(failures))
    image_relative = candidate_path or contract["output_path"]
    image = file_at(root, image_relative)
    if decision == "PENDING_REVIEW":
        failures = export_errors(root, image, contract.get("output_requirements", {}))
        if failures:
            raise ValueError("; ".join(failures))
    previous = next((x for x in product.get("candidates", []) if x.get("candidate_id") == contract["candidate_id"]), None)
    if previous and previous.get("sha256") != digest(image):
        raise ValueError("candidate ID already belongs to different image bytes")
    if previous and previous.get("status") == "ACCEPTED" and decision != "ACCEPTED":
        raise ValueError("accepted human decision cannot be silently overwritten")
    candidate = {**(previous or {}), "candidate_id": contract["candidate_id"], "run_id": contract["run_id"], "source_contract": contract_address, "path": image_relative, "sha256": digest(image), "status": decision}
    if decision.startswith("REJECTED"):
        if not failure_code:
            raise ValueError("rejection requires a short --failure-code")
        candidate["failure_code"] = failure_code
    if report_address:
        report = read_json(file_at(root, report_address))
        if report.get("candidate_id") != contract["candidate_id"] or report.get("candidate_sha256") != candidate["sha256"] or report.get("contract_sha256") != digest(path):
            raise ValueError("QA report belongs to different candidate/contract bytes")
        candidate.setdefault("checks", {})["visual"] = {"report_path": report_address}
    if decision in {"ACCEPTED", "HUMAN_STRUCTURE_REVIEW_PASSED"}:
        if not human_reviewer or not decision_reference or not report_address:
            raise ValueError("human decisions require an actual reviewer, decision reference and QA report")
        failures = qa_errors(root, contract, path, candidate, report)
        if failures:
            raise ValueError("; ".join(failures))
        candidate["human_review"] = {"reviewer": human_reviewer, "decision_reference": decision_reference}
    product["candidates"] = [x for x in product.get("candidates", []) if x.get("candidate_id") != candidate["candidate_id"]] + [candidate]
    status = "ACCEPTED" if decision == "ACCEPTED" else "REJECTED" if decision.startswith("REJECTED") else "HUMAN_REVIEW"
    follow_up = ("NEXT_SET_MODULE" if contract.get("visual_set") else "DELIVER_ACCEPTED_IMAGE") if status == "ACCEPTED" else "REGENERATE_REJECTED_CANDIDATE" if status == "REJECTED" else "COMPLETE_VISUAL_QA_AND_HUMAN_REVIEW"
    workflow = product.setdefault("workflow", {})
    if workflow.get("active_candidate_id") != candidate["candidate_id"]:
        workflow["geometry"] = {"status": "NOT_REQUESTED"}
    workflow.update({"status": status, "active_run_id": contract["run_id"], "active_view": contract["target_view"], "active_contract": contract_address, "active_candidate_id": candidate["candidate_id"], "next_action": follow_up})
    for run in product.get("runs", []):
        if run.get("run_id") == contract["run_id"]:
            run["status"] = status
    finish_claim(root, candidate["candidate_id"], "OUTPUT_SAVED", claim_token)
    product.setdefault("decision_log", []).append({"action": "CANDIDATE_DECISION", "candidate_id": candidate["candidate_id"], "candidate_sha256": candidate["sha256"], "decision": decision, **({"human_review": candidate["human_review"]} if candidate.get("human_review") else {})})
    write_json(root / "PRODUCT_STATE.json", product)
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--decision", required=True, choices=("PENDING_REVIEW", "REJECTED_TOPOLOGY", "REJECTED_VISUAL", "ACCEPTED", "HUMAN_STRUCTURE_REVIEW_PASSED"))
    parser.add_argument("--candidate-path")
    parser.add_argument("--failure-code")
    parser.add_argument("--report")
    parser.add_argument("--human-reviewer")
    parser.add_argument("--decision-reference")
    parser.add_argument("--claim-token")
    args = parser.parse_args()
    root = args.package.resolve()
    try:
        with transaction(root):
            contract = load_contract(root, file_at(root, args.contract))
            if contract.get("visual_set"):
                raise ValueError("use set_runtime.py record for set-linked work so module status commits with the decision")
            result = record_candidate(root, args.contract, args.decision, candidate_path=args.candidate_path,
                                      failure_code=args.failure_code, report_address=args.report,
                                      human_reviewer=args.human_reviewer, decision_reference=args.decision_reference,
                                      claim_token=args.claim_token)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
