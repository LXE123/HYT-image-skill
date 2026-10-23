#!/usr/bin/env python3
"""Create a non-destructive per-view generation contract and activate its workflow state."""

import argparse
import json
import re
from pathlib import Path


SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} 必须是 JSON 对象")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sku", required=True)
    parser.add_argument("--view", required=True)
    parser.add_argument("--format", default="PNG")
    parser.add_argument("--background", default="white")
    parser.add_argument("--a-plus", action="store_true", help="A+ final PNG requires code crop to 1464x600")
    args = parser.parse_args()
    if args.a_plus:
        args.format = "PNG"

    if not SAFE_ID.fullmatch(args.run_id) or not SAFE_ID.fullmatch(args.view):
        parser.error("run-id 和 view 只能使用字母、数字、点、下划线和连字符")

    root = args.package.resolve()
    state_path = root / "PRODUCT_STATE.json"
    index_path = root / "index.json"
    try:
        state, index = read_json(state_path), read_json(index_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(f"无法读取产品包：{exc}")
    if state.get("product_id") != index.get("product_id"):
        parser.error("PRODUCT_STATE.json 与 index.json 的 product_id 不一致")
    if state.get("sku") not in (None, args.sku, state.get("product_id")):
        parser.error("SKU 与 PRODUCT_STATE.json 不一致；请先显式更新并复核状态文件")
    workflow = state.get("workflow", {})
    if workflow.get("status") in {"REFERENCE_INTAKE", "REFERENCE_CHANGED"}:
        parser.error(f"当前参考状态为 {workflow.get('status')}；请先执行 {workflow.get('next_action')}")

    candidate_id = f"{args.run_id}-{args.view}"
    contract_path = root / "runs" / args.run_id / f"{args.view}_generation_contract.json"
    relative_contract = contract_path.relative_to(root).as_posix()
    relative_candidate = f"candidates/inbox/{args.run_id}/{candidate_id}.{args.format.lower()}"
    for relative in (
        f"candidates/inbox/{args.run_id}",
        f"candidates/rejected/{args.run_id}",
        "candidates/accepted",
        f"outputs/{args.run_id}",
        "qa/geometry/templates",
        "qa/geometry/registered",
        "qa/geometry/reports",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)

    if contract_path.exists():
        try:
            contract = read_json(contract_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            parser.error(f"无法读取已有合同：{exc}")
        if args.a_plus and contract.get("output_requirements", {}).get("postprocess") != "CODE_CROP_RESIZE":
            parser.error("existing contract has no A+ code export; create a new run/revision instead of overwriting it")
        candidate_id = contract.get("candidate_id") or candidate_id
        relative_candidate = contract.get("output_path") or relative_candidate
        print(f"SKIP  合同已存在，未覆盖：{relative_contract}")
        candidate_registered = any(isinstance(item, dict) and item.get("candidate_id") == candidate_id for item in state.get("candidates", []))
        if candidate_registered or (isinstance(relative_candidate, str) and (root / relative_candidate).is_file()):
            print(f"RESUME  候选图已存在或已登记；保持当前 workflow：{candidate_id}")
            return 0
    else:
        contract = {
            "schema_version": 2,
            "prompt_format": "focused-v1",
            "creative_policy_version": 1,
            "module_language_policy_version": 1,
            "run_id": args.run_id,
            "candidate_id": candidate_id,
            "sku": args.sku,
            "target_view": args.view,
            "identity_lockset_version": None,
            "required_lock_ids": [],
            "references": [],
            "prior_candidate_references": [],
            "generation_template": {},
            "image_intent": {"sales_task": "", "buyer_question": ""},
            "visual_system": {"direction": "", "lighting": "", "typography": ""},
            "creative_brief": {
                "visual_concept": "",
                "visual_device": "",
                "information_hierarchy": [],
                "graphic_treatment": "",
                "set_role": "",
                "success_criteria": [],
            },
            "quality_contract": {"version": 1, "layout": {}, "human": {"present": False}, "visible_hardware": [], "structure_checks": [], "mechanism": {"depicted": False}},
            "visual_invariants": [],
            "forbidden_changes": [],
            "output_requirements": {"format": args.format, "background": args.background},
            "output_path": relative_candidate,
        }
        if args.a_plus:
            contract["output_requirements"].update(width_px=1464, height_px=600, aspect_ratio="1464:600", postprocess="CODE_CROP_RESIZE", pre_crop_review="OBSERVED_LAYOUT_V1")
        write_json(contract_path, contract)
        print(f"CREATE  合同草稿：{relative_contract}")

    runs = state.setdefault("runs", [])
    if not isinstance(runs, list):
        parser.error("PRODUCT_STATE.json 的 runs 必须是数组")
    run = next((record for record in runs if isinstance(record, dict) and record.get("run_id") == args.run_id), None)
    if run:
        print(f"SKIP  运行已登记：{args.run_id}")
    else:
        runs.append({
            "run_id": args.run_id,
            "sku": args.sku,
            "views": [args.view],
            "status": "CONTRACT_DRAFT",
            "contracts": [relative_contract],
        })
        print(f"UPDATE  已登记运行：{args.run_id}")

    state["sku"] = args.sku
    state["workflow"] = {
        "status": "CONTRACT_DRAFT",
        "active_run_id": args.run_id,
        "active_view": args.view,
        "active_contract": relative_contract,
        "active_candidate_id": candidate_id,
        "geometry": {"status": "NOT_REQUESTED"},
        "next_action": "COMPLETE_AND_VALIDATE_CONTRACT",
    }
    write_json(state_path, state)
    print(f"ACTIVE  candidate={candidate_id}，output={relative_candidate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
