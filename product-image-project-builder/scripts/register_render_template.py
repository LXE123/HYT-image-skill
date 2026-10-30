#!/usr/bin/env python3
"""Register a clean render and aligned overall mask without copying source files."""
import sys
from pathlib import Path

import argparse
import json
from pathlib import PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "product-single-image-generator" / "scripts"))
from project_store import read_json as store_read, write_json as store_write, digest as store_digest, transaction


def safe(root, value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("路径必须相对于产品包根目录")
    result = (root / path).resolve()
    result.relative_to(root)
    if not result.is_file():
        raise ValueError(f"文件不存在：{value}")
    return result


def sha256(path):
    return store_digest(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--view", required=True)
    parser.add_argument("--rgb", required=True)
    parser.add_argument("--mask", required=True)
    parser.add_argument("--template-id")
    parser.add_argument("--part-id-mask")
    parser.add_argument("--depth")
    parser.add_argument("--normal")
    parser.add_argument("--model-version")
    args = parser.parse_args()
    with transaction(args.package):
        return execute(args, parser)


def execute(args, parser):
    root = args.package.resolve()
    index_path = root / "index.json"
    try:
        index = store_read(index_path)
        rgb, mask = safe(root, args.rgb), safe(root, args.mask)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    template_id = args.template_id or args.view
    record = {"template_id": template_id, "view": args.view, "rgb_path": args.rgb, "mask_path": args.mask, "rgb_sha256": sha256(rgb), "mask_sha256": sha256(mask), "status": "provisional"}
    for key, value in (("part_id_mask_path", args.part_id_mask), ("depth_path", args.depth), ("normal_path", args.normal)):
        if value:
            record[key] = value
            record[key.replace("_path", "_sha256")] = sha256(safe(root, value))
    if args.model_version:
        record["model_version"] = args.model_version
    templates = index.setdefault("render_templates", [])
    if any(isinstance(item, dict) and item.get("template_id") == template_id for item in templates):
        parser.error("template-id 已存在；请新建版本而不要覆盖")
    templates.append(record)
    store_write(index_path, index)
    print(f"REGISTER  {template_id}（初始状态 provisional，人工复核后才可用于锁定）")
    return 0


if __name__ == "__main__":
    from runtime_log import run_cli
    raise SystemExit(run_cli(main))
