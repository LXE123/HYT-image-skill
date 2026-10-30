#!/usr/bin/env python3
"""Validate independent product evidence and correction supplements."""
import sys
from pathlib import Path

import argparse
import json
import re
from pathlib import PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "product-single-image-generator" / "scripts"))
from project_store import read_json as store_read, write_json as store_write, digest as store_digest, transaction

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
SOURCE_TYPES = {"REAL_PHOTO", "DESIGN_RENDER", "CAD_RENDER", "DETAIL"}


def sha256(path: Path) -> str:
    return store_digest(path)


def resolve_file(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("路径不能为空")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"路径必须是安全的产品包相对路径：{value}")
    result = (root / relative).resolve()
    result.relative_to(root)
    if not result.is_file():
        raise ValueError(f"文件不存在：{value}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    root = parser.parse_args().package.resolve()
    with transaction(root):
        return check(root)


def check(root):
    errors, warnings = [], []
    try:
        index = store_read(root / "index.json")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL  无法读取 index.json：{exc}")
        return 1
    try:
        state = store_read(root / "PRODUCT_STATE.json")
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL  无法读取 PRODUCT_STATE.json：{exc}")
        return 1
    mode = index.get("evidence_mode")
    if mode not in {"MODEL_ASSISTED", "PHOTO_EVIDENCE"}:
        errors.append("evidence_mode 必须为 MODEL_ASSISTED 或 PHOTO_EVIDENCE")
    if state.get("product_id") != index.get("product_id"):
        errors.append("index.json 与 PRODUCT_STATE.json 的 product_id 不一致")
    reference = state.get("reference_package", {})
    if reference.get("path") != "index.json" or reference.get("version") != index.get("version"):
        errors.append("PRODUCT_STATE.json 的 reference_package 未指向当前 index.json/version")
    if index.get("product_scope") not in {"PRODUCT_ONLY", "PRODUCT_WITH_CONTEXT"}:
        errors.append("product_scope 必须为 PRODUCT_ONLY 或 PRODUCT_WITH_CONTEXT")
    if mode == "MODEL_ASSISTED":
        approved = {item.get("view") for item in index.get("render_templates", []) if isinstance(item, dict) and item.get("status") == "approved" and item.get("rgb_path") and item.get("mask_path")}
        missing = {"front", "back"} - approved
        if missing:
            warnings.append("缺少已批准的渲染/mask 视图：" + ", ".join(sorted(missing)))
    evidence = index.get("product_evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("product_evidence 必须包含至少一张独立产品证据图")
        evidence = []
    seen_evidence_ids = set()
    views = set()
    has_full_product = False
    has_hard_constraint = False
    has_hard_real_photo = False
    for position, item in enumerate(evidence):
        label = f"product_evidence[{position}]"
        if not isinstance(item, dict):
            errors.append(f"{label} 必须是对象")
            continue
        evidence_id = item.get("evidence_id")
        if not isinstance(evidence_id, str) or not SAFE_ID.fullmatch(evidence_id):
            errors.append(f"{label} 缺少安全的 evidence_id")
        elif evidence_id in seen_evidence_ids:
            errors.append(f"evidence_id 重复：{evidence_id}")
        else:
            seen_evidence_ids.add(evidence_id)
        source_type = item.get("source_type")
        if source_type not in SOURCE_TYPES:
            errors.append(f"{label} source_type 无效：{source_type}")
        view = item.get("view")
        if not isinstance(view, str) or not SAFE_ID.fullmatch(view):
            errors.append(f"{label} 缺少安全的 view")
        else:
            views.add(view)
        structures = item.get("structures")
        observed_states = item.get("observed_states", [])
        if not isinstance(observed_states, list) or not all(isinstance(x, str) and x.strip() for x in observed_states):
            errors.append(f"{label} observed_states 必须是可见状态 ID 的字符串数组")
        if not isinstance(structures, list) or not structures or not all(isinstance(value, str) and value.strip() for value in structures):
            errors.append(f"{label} structures 必须是非空字符串数组")
        elif "full_product" in structures:
            has_full_product = True
        hard_constraint = item.get("hard_constraint")
        if not isinstance(hard_constraint, bool):
            errors.append(f"{label} hard_constraint 必须是布尔值")
        elif hard_constraint:
            has_hard_constraint = True
            if source_type == "REAL_PHOTO":
                has_hard_real_photo = True
        try:
            evidence_file = resolve_file(root, item.get("path"))
        except ValueError as error:
            errors.append(f"{label} {error}")
        else:
            if item.get("sha256") != sha256(evidence_file):
                errors.append(f"{label} sha256 与文件内容不一致")
    if evidence and not has_full_product:
        errors.append("至少一张独立证据图必须声明 structures: [full_product, ...]")
    if evidence and not has_hard_constraint:
        errors.append("至少一张独立证据图必须设为 hard_constraint")
    if mode == "PHOTO_EVIDENCE" and evidence and not has_hard_real_photo:
        errors.append("PHOTO_EVIDENCE 至少需要一张 hard_constraint 的 REAL_PHOTO")
    if evidence and len(views) < 2:
        warnings.append("当前只有一个已登记视角；请确认目标生成视图没有未覆盖结构")

    supplements = {}
    for item in index.get("error_supplements", []):
        issue_id, path = item.get("related_issue"), item.get("path")
        supplements.setdefault(issue_id, []).append(item)
        if not isinstance(path, str) or not (root / path).is_file():
            errors.append(f"错误补图文件不存在：{path}")
    for issue in index.get("known_issues", []):
        issue_id, status = issue.get("issue_id"), issue.get("status")
        matched = supplements.get(issue_id, [])
        if not matched:
            errors.append(f"错误 {issue_id} 缺少真实参考补图")
        elif status == "resolved" and not any(item.get("verified") is True for item in matched):
            errors.append(f"错误 {issue_id} 已解决但补图尚未验证")
        elif status == "open":
            warnings.append(f"错误 {issue_id} 仍待验证")

    for line in errors:
        print(f"FAIL  {line}")
    for line in warnings:
        print(f"WARN  {line}")
    if errors:
        print(f"检查失败：{len(errors)} 项；提醒：{len(warnings)} 项")
        return 1
    index_hash = sha256(root / "index.json")
    previous_hash = reference.get("sha256")
    workflow = state.setdefault("workflow", {})
    if not workflow.get("status"):
        if state.get("runs"):
            workflow.update({"status": "REFERENCE_CHANGED", "next_action": "RECONCILE_REFERENCE_CHANGE"})
        else:
            workflow.update({"status": "REFERENCE_READY", "next_action": "BUILD_IDENTITY_BASELINE"})
    elif workflow.get("status") == "REFERENCE_INTAKE":
        workflow.update({"status": "REFERENCE_READY", "next_action": "BUILD_IDENTITY_BASELINE"})
    elif previous_hash and previous_hash != index_hash:
        workflow.update({"status": "REFERENCE_CHANGED", "next_action": "RECONCILE_REFERENCE_CHANGE"})
    reference["sha256"] = index_hash
    state["reference_package"] = reference
    store_write(root / "PRODUCT_STATE.json", state)
    print(f"PASS  独立产品证据有效，错误补图闭环有效。提醒：{len(warnings)} 项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
