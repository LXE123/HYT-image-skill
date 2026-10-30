#!/usr/bin/env python3
"""Register one independent product-evidence image without copying it."""
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


def resolve(root, value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("source 必须是产品包内的相对路径")
    result = (root / path).resolve()
    result.relative_to(root)
    if not result.is_file():
        raise ValueError(f"文件不存在：{value}")
    return result


def sha256(path):
    return store_digest(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--evidence-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-type", choices=sorted(SOURCE_TYPES), required=True)
    parser.add_argument("--view", required=True)
    parser.add_argument("--structures", required=True, help="comma-separated visible facts this image can constrain")
    parser.add_argument("--hard-constraint", action="store_true")
    parser.add_argument("--observed-states", default="", help="comma-separated visibly proven state IDs, e.g. clasp_closed,clasp_open; never infer operation")
    args = parser.parse_args()
    with transaction(args.package):
        return execute(args, parser)


def execute(args, parser):
    if not SAFE_ID.fullmatch(args.evidence_id) or not SAFE_ID.fullmatch(args.view):
        parser.error("evidence-id 和 view 只能使用字母、数字、点、下划线和连字符")
    structures = [value.strip() for value in args.structures.split(",") if value.strip()]
    if not structures:
        parser.error("structures 至少需要一个可见结构事实")
    root = args.package.resolve()
    index_path = root / "index.json"
    try:
        index = store_read(index_path)
        source = resolve(root, args.source)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    items = index.setdefault("product_evidence", [])
    if not isinstance(items, list):
        parser.error("index.json 的 product_evidence 必须是数组")
    if any(isinstance(item, dict) and item.get("evidence_id") == args.evidence_id for item in items):
        parser.error("evidence-id 已存在；请使用新 ID 保留历史")
    items.append({
        "evidence_id": args.evidence_id,
        "path": args.source,
        "sha256": sha256(source),
        "source_type": args.source_type,
        "view": args.view,
        "structures": structures,
        "hard_constraint": args.hard_constraint,
        "observed_states": [x.strip() for x in args.observed_states.split(",") if x.strip()],
    })
    store_write(index_path, index)
    print(f"REGISTER  {args.evidence_id}")
    return 0


if __name__ == "__main__":
    from runtime_log import run_cli
    raise SystemExit(run_cli(main))
