#!/usr/bin/env python3
"""Validate a product run contract and advance the active workflow after preflight."""

from structure_state import dependency_errors
from execution_policy import policy_errors
import argparse
import json
from pathlib import Path, PurePosixPath
from quality_rules import compile_prompt, validate_quality
from context_store import load_contract

ROLES = {"PRODUCT_EVIDENCE": "PRODUCT_IDENTITY_ONLY", "POSE_ONLY": "POSE_CAMERA_COMPOSITION_LIGHTING_BACKGROUND_ONLY"}


def load(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return value
        errors.append(f"{path.name} 必须是 JSON 对象")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"无法读取 {path}: {exc}")
    return {}


def safe_relative(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not PurePosixPath(value).is_absolute() and ".." not in PurePosixPath(value).parts


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--ready-for-generation", action="store_true")
    args = parser.parse_args()
    root, errors = args.package.resolve(), []
    state = load(root / "PRODUCT_STATE.json", errors)
    contract_path = args.contract if args.contract.is_absolute() else root / args.contract
    contract_path = contract_path.resolve()
    relative_contract = None
    try:
        contract_path.relative_to(root / "runs")
        relative_contract = contract_path.relative_to(root).as_posix()
    except ValueError:
        errors.append("合同必须位于产品包 runs/ 目录内")
    try:
        contract = load_contract(root, contract_path)
    except (OSError, ValueError, KeyError) as error:
        errors.append(str(error))
        contract = {}
    required = ("schema_version", "run_id", "sku", "target_view", "references", "prior_candidate_references", "visual_invariants", "forbidden_changes", "output_requirements", "output_path")
    for key in required:
        if key not in contract:
            errors.append(f"合同缺少字段：{key}")
    if contract.get("schema_version") not in {1, 2}:
        errors.append("合同 schema_version 必须为 1 或 2")
    if contract.get("schema_version") == 2 and not contract.get("candidate_id"):
        errors.append("schema_version 2 合同必须包含 candidate_id")
    if state and contract.get("sku") != state.get("sku"):
        errors.append("合同 SKU 与 PRODUCT_STATE.json 不一致")
    output, run_id = contract.get("output_path"), contract.get("run_id")
    expected_prefix = f"candidates/inbox/{run_id}/" if isinstance(run_id, str) else ""
    if not safe_relative(output) or not isinstance(output, str) or not output.startswith(expected_prefix):
        errors.append("output_path 必须是当前 run 的 candidates/inbox 根相对路径")
    if "candidates/rejected/" in str(output):
        errors.append("output_path 不得指向 rejected 区域")
    if contract.get("schema_version") == 2 and isinstance(output, str):
        candidate_id = contract.get("candidate_id")
        if Path(output).stem != candidate_id:
            errors.append("schema_version 2 合同的 output_path 文件名必须与 candidate_id 一致")
    refs = contract.get("references", [])
    if not isinstance(refs, list):
        errors.append("references 必须是数组")
    else:
        for i, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(f"references[{i}] 必须是对象")
                continue
            role, scope, path = ref.get("role"), ref.get("usage_scope"), ref.get("path")
            if role not in ROLES:
                errors.append(f"references[{i}] 的 role 无效")
            elif scope != ROLES[role]:
                errors.append(f"references[{i}] 的 usage_scope 与 role 不匹配")
            if not safe_relative(path):
                errors.append(f"references[{i}] 的 path 必须为安全的根相对路径")
    prior = contract.get("prior_candidate_references", [])
    if not isinstance(prior, list):
        errors.append("prior_candidate_references 必须是数组")
    else:
        for i, ref in enumerate(prior):
            path = ref.get("path") if isinstance(ref, dict) else ref
            if not safe_relative(path) or str(path).startswith("candidates/rejected/"):
                errors.append(f"prior_candidate_references[{i}] 不得引用 rejected 候选图")
    runs = state.get("runs", []) if state else []
    if not any(isinstance(item, dict) and item.get("run_id") == run_id for item in runs):
        errors.append("合同 run_id 未登记在 PRODUCT_STATE.json 的 runs 中")
    if args.ready_for_generation:
        errors.extend(policy_errors(contract, generation=True))
        if isinstance(output, str) and (root / output).is_file():
            errors.append("生成前检查拒绝已存在的合同候选图；请继续审核或创建新合同")
        candidate_id = contract.get("candidate_id") or f"{run_id}-{contract.get('target_view')}"
        if any(isinstance(item, dict) and item.get("candidate_id") == candidate_id for item in state.get("candidates", [])):
            errors.append("生成前检查拒绝已登记的 candidate_id；请继续审核或创建新合同")
        workflow = state.get("workflow", {}) if state else {}
        if workflow and relative_contract and workflow.get("active_contract") not in (None, relative_contract):
            errors.append("合同不是 PRODUCT_STATE.json 中的 active_contract")
        lockset = state.get("identity_lockset") if state else None
        if not isinstance(lockset, dict) or lockset.get("status") != "READY":
            errors.append("生成前检查要求 PRODUCT_STATE.json 中有 READY 的 identity_lockset")
        elif dependency_errors(state, contract.get("required_lock_ids"), contract.get("resolved_identity_locks")):
            errors.extend(dependency_errors(state, contract.get("required_lock_ids"), contract.get("resolved_identity_locks")))
        else:
            required_locks = contract.get("required_lock_ids")
            locks = {item.get("lock_id"): item for item in lockset.get("locks", []) if isinstance(item, dict)}
            try:
                manifest = json.loads((root / "qa/identity_anchors/index.json").read_text(encoding="utf-8"))
                anchors = {item.get("anchor_id"): item for item in manifest.get("anchors", []) if isinstance(item, dict)}
            except (OSError, json.JSONDecodeError):
                anchors = {}
            templates = {}
            try:
                package_index = json.loads((root / "index.json").read_text(encoding="utf-8"))
                templates = {item.get("template_id"): item for item in package_index.get("render_templates", []) if isinstance(item, dict)}
            except (OSError, json.JSONDecodeError):
                errors.append("生成前检查找不到有效的 index.json")
                package_index = {}
            errors.extend(validate_quality(root, contract, package_index, locks))
            expected_resolved = [locks[x] for x in contract.get("required_lock_ids", []) if x in locks]
            if contract.get("resolved_identity_locks") != expected_resolved:
                errors.append("resolved_identity_locks 与当前结构事实不一致；请重新编译草稿或修订套图计划")
            if contract.get("generation_template") and contract.get("quality_contract"):
                if contract.get("generation_prompt") != compile_prompt(contract):
                    errors.append("generation_prompt 缺失或与当前模板/合同不一致；生成前请重新编译提示词")
            if not isinstance(required_locks, list) or not required_locks:
                errors.append("生成前合同必须声明 required_lock_ids")
            else:
                for lock_id in required_locks:
                    lock = locks.get(lock_id)
                    if not isinstance(lock, dict) or lock.get("status") != "LOCKED":
                        errors.append(f"必需结构锁不可用：{lock_id}")
                        continue
                    template_id = lock.get("render_template_id")
                    if template_id:
                        template = templates.get(template_id)
                        if not template or template.get("status") != "approved":
                            errors.append(f"全视图结构锁缺少已批准渲染模板：{lock_id}")
                        else:
                            for key in ("rgb_path", "mask_path"):
                                if not safe_relative(template.get(key)) or not (root / template[key]).is_file():
                                    errors.append(f"全视图结构锁缺少 render {key}：{lock_id}")
                    else:
                        anchor_id = lock.get("anchor_id")
                        anchor = anchors.get(anchor_id)
                        asset_dir = root / "qa/identity_anchors" / str(anchor_id)
                        if not anchor or not all((asset_dir / name).is_file() for name in ("source.png", "grayscale.png", "contour.png", "anchor.json")):
                            errors.append(f"结构锁缺少可复核锚点资产：{lock_id}")
    for error in errors:
        print(f"FAIL  {error}")
    if errors:
        return 1
    if args.ready_for_generation:
        relative_contract = contract_path.relative_to(root).as_posix()
        candidate_id = contract.get("candidate_id") or f"{run_id}-{contract.get('target_view')}"
        state["workflow"] = {
            "status": "GENERATION_READY",
            "active_run_id": run_id,
            "active_view": contract.get("target_view"),
            "active_contract": relative_contract,
            "active_candidate_id": candidate_id,
            "geometry": {"status": "NOT_REQUESTED"},
            "next_action": "GENERATE_CANDIDATE",
        }
        for run in state.get("runs", []):
            if isinstance(run, dict) and run.get("run_id") == run_id:
                run["status"] = "GENERATION_READY"
        write_json(root / "PRODUCT_STATE.json", state)
    print(f"PASS  合同与状态一致：run={run_id}，sku={contract.get('sku')}，view={contract.get('target_view')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
