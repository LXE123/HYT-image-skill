#!/usr/bin/env python3
"""Create versioned grayscale and contour evidence assets from supplied references."""
import sys
from pathlib import Path

import argparse
from pathlib import PurePosixPath

from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "product-single-image-generator" / "scripts"))
from project_store import read_json as store_read, write_json as store_write, digest as store_digest, exists as store_exists


def digest(path):
    return store_digest(path)


def safe_path(root, value):
    p = PurePosixPath(value)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("source 必须是产品包内的相对路径")
    path = (root / p).resolve()
    path.relative_to(root)
    return path


def save_assets(source, dest, crop, anchor_id, structures):
    image = Image.open(source).convert("RGB")
    if crop:
        x, y, width, height = crop
        if min(x, y, width, height) < 0 or x + width > image.width or y + height > image.height:
            raise ValueError("crop 超出参考图范围")
        image = image.crop((x, y, x + width, y + height))
    dest.mkdir(parents=True, exist_ok=True)
    image.save(dest / "source.png")
    gray = image.convert("L")
    gray.save(dest / "grayscale.png")
    # Edge map is evidence only; it intentionally is not an approved foreground mask.
    gray.filter(ImageFilter.FIND_EDGES).save(dest / "contour.png")
    return {"anchor_id": anchor_id, "source_path": str(source), "source_sha256": digest(source), "crop": crop, "structures": structures, "assets": {name: digest(dest / name) for name in ("source.png", "grayscale.png", "contour.png")}, "status": "REVIEW_REQUIRED", "note": "灰度与轮廓是参考证据；需人工补充结构注释，不能直接当作产品 mask。"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--anchor-id")
    parser.add_argument("--source")
    parser.add_argument("--crop", nargs=4, type=int, metavar=("X", "Y", "WIDTH", "HEIGHT"))
    parser.add_argument("--structures", default="")
    args = parser.parse_args()
    root = args.package.resolve()
    anchors_dir = root / "qa/identity_anchors"
    manifest_path = anchors_dir / "index.json"
    manifest = store_read(manifest_path) if store_exists(manifest_path) else {"schema_version": 1, "anchors": []}
    if not args.anchor_id or not args.source:
        parser.error("创建结构锚点必须同时提供 --anchor-id 和 --source")
    plans = [(args.anchor_id, args.source, args.crop, [v for v in args.structures.split(",") if v])]
    known = {item.get("anchor_id"): item for item in manifest.get("anchors", []) if isinstance(item, dict)}
    for anchor_id, source_rel, crop, structures in plans:
        source = safe_path(root, source_rel)
        if not source.is_file():
            parser.error(f"参考图不存在：{source_rel}")
        prior = known.get(anchor_id)
        if prior:
            same = prior.get("source_path") == source_rel and prior.get("source_sha256") == digest(source) and prior.get("crop") == crop
            if same:
                print(f"SKIP  锚点未变化：{anchor_id}")
                continue
            parser.error(f"锚点 {anchor_id} 已存在且证据已变化；请使用新的 anchor-id 保留版本历史")
        entry = save_assets(source, anchors_dir / anchor_id, crop, anchor_id, structures)
        entry["source_path"] = source_rel
        store_write(anchors_dir / anchor_id / "anchor.json", entry)
        known[anchor_id] = entry
        print(f"CREATE  {anchor_id}")
    manifest["anchors"] = [known[key] for key in sorted(known)]
    anchors_dir.mkdir(parents=True, exist_ok=True)
    store_write(manifest_path, manifest)
    return 0


if __name__ == "__main__":
    from runtime_log import run_cli
    raise SystemExit(run_cli(main))
