#!/usr/bin/env python3
"""Create one reference package and its initial shared workflow state."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from desktop_location import product_package_path


EVIDENCE_DIRS = (
    "input/01_product_evidence",
    "input/02_render_templates",
    "input/03_error_supplements",
    "input/04_pose_references",
)


def write_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} 必须是 JSON 对象")
    return value


def preflight_existing(root: Path, product_id: str, version: str, evidence_mode: str, product_scope: str) -> bool:
    if root.exists() and not root.is_dir():
        raise ValueError(f"目标路径已存在但不是文件夹：{root}")
    if (root / ".initialize.lock").exists():
        raise ValueError("检测到初始化锁；另一个进程可能正在创建产品包，或上次初始化异常中断")
    index_path = root / "index.json"
    state_path = root / "PRODUCT_STATE.json"
    if index_path.exists() != state_path.exists():
        present = index_path.name if index_path.exists() else state_path.name
        missing = state_path.name if index_path.exists() else index_path.name
        raise ValueError(f"检测到不完整产品包：存在 {present} 但缺少 {missing}；请先修复或更换 version")
    if index_path.exists():
        try:
            index = load_object(index_path)
            state = load_object(state_path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise ValueError(f"已有产品包无法安全续用：{error}") from error
        expected = {
            "product_id": product_id,
            "version": version,
            "evidence_mode": evidence_mode,
            "product_scope": product_scope,
        }
        conflicts = [key for key, value in expected.items() if index.get(key) != value]
        if conflicts:
            raise ValueError("已有 index.json 与本次参数冲突：" + ", ".join(conflicts))
        reference = state.get("reference_package", {})
        if state.get("product_id") != product_id or reference.get("path") != "index.json" or reference.get("version") != version:
            raise ValueError("已有 PRODUCT_STATE.json 与目标产品或版本不一致")
        return True
    if root.exists():
        allowed_directories = {"input", *EVIDENCE_DIRS}
        for item in root.rglob("*"):
            relative = item.relative_to(root).as_posix()
            if not item.is_dir() or relative not in allowed_directories:
                raise ValueError(f"目标文件夹包含未识别内容，未写入任何文件：{relative}")
    return False


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--evidence-mode", choices=("MODEL_ASSISTED", "PHOTO_EVIDENCE"), required=True)
    parser.add_argument("--product-scope", choices=("PRODUCT_ONLY", "PRODUCT_WITH_CONTEXT"), required=True)
    parser.add_argument("--desktop-root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        root = product_package_path(args.product_id, args.version, args.desktop_root)
        resume = preflight_existing(root, args.product_id, args.version, args.evidence_mode, args.product_scope)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    try:
        for relative in EVIDENCE_DIRS:
            (root / relative).mkdir(parents=True, exist_ok=True)
    except OSError as error:
        parser.error(f"无法创建产品目录：{error}")
    if resume:
        print(f"RESUME  {root}")
        return 0
    index_path = root / "index.json"
    index = {"product_id": args.product_id, "version": args.version, "evidence_mode": args.evidence_mode, "product_scope": args.product_scope, "product_evidence": [], "render_templates": [], "known_issues": [], "error_supplements": []}
    state_path = root / "PRODUCT_STATE.json"
    lock_path = root / ".initialize.lock"
    try:
        with lock_path.open("x", encoding="utf-8") as lock_stream:
            lock_stream.write(f"pid={os.getpid()}\n")
    except (FileExistsError, OSError) as error:
        parser.error(f"初始化锁创建失败；目录可能正被使用或上次初始化未完成：{error}")
    created: list[Path] = []
    failure: OSError | None = None
    try:
        write_new(index_path, index)
        created.append(index_path)
        write_new(state_path, {
            "schema_version": 2,
            "product_id": args.product_id,
            "sku": args.product_id,
            "reference_package": {"path": "index.json", "version": args.version, "sha256": sha256(index_path)},
            "sellable_object": {"included": [], "excluded": []},
            "product_identity_baseline": {"status": "INCOMPLETE", "visual_invariants": [], "surface_topology": [], "view_constraints": []},
            "identity_lockset": {"version": 0, "status": "INCOMPLETE", "locks": []},
            "workflow": {
                "status": "REFERENCE_INTAKE",
                "active_run_id": None,
                "active_view": None,
                "active_contract": None,
                "active_candidate_id": None,
                "geometry": {"status": "NOT_REQUESTED"},
                "next_action": "ADD_AND_VALIDATE_REFERENCES",
            },
            "evidence_gaps": [],
            "runs": [],
            "candidates": [],
            "geometry_checks": [],
            "decision_log": [],
        })
        created.append(state_path)
    except OSError as error:
        failure = error
        for created_path in reversed(created):
            try:
                created_path.unlink()
            except OSError:
                pass
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass
    if failure:
        parser.error(f"初始化期间目标被其他进程占用或写入失败，已回滚本次控制文件：{failure}")
    print(f"CREATE  {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
