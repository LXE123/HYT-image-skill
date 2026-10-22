#!/usr/bin/env python3
"""Crop and resample a generated original to an exact 1464x600 PNG; never overwrite."""

import argparse
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path

TARGET = (1464, 600)
METHOD = 'CODE_CROP_RESIZE'
METADATA_KEY = 'a_plus_export'


def image_tools():
    try:
        from PIL import Image, ImageOps, PngImagePlugin
    except ImportError as exc:
        raise ValueError('Pillow is required for code cropping; use the available image runtime or install the declared Pillow dependency') from exc
    return Image, ImageOps, PngImagePlugin


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crop_geometry(size, keep_box=None):
    width, height = size
    ratio = TARGET[0] / TARGET[1]
    crop_w, crop_h = min(width, height * ratio), min(height, width / ratio)
    if keep_box is None:
        if abs(width / height - ratio) > 1e-9:
            raise ValueError('different aspect ratio requires --keep-box covering all product, people and copy that must survive')
        keep_box = [0.0, 0.0, 1.0, 1.0]
    if len(keep_box) != 4 or any(isinstance(n, bool) or not isinstance(n, (float, int)) or not math.isfinite(n) for n in keep_box):
        raise ValueError('keep-box must contain four finite normalized coordinates')
    left, top, right, bottom = keep_box
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError('keep-box must be normalized left top right bottom within 0..1')
    left, top, right, bottom = left * width, top * height, right * width, bottom * height
    if right - left > crop_w + 1e-7 or bottom - top > crop_h + 1e-7:
        raise ValueError('required content does not fit a 1464x600 crop; recompose/regenerate rather than cut it or stretch')
    x = min(max((left + right - crop_w) / 2, 0, right - crop_w), left, width - crop_w)
    y = min(max((top + bottom - crop_h) / 2, 0, bottom - crop_h), top, height - crop_h)
    return [round(v, 8) for v in (x, y, x + crop_w, y + crop_h)]


def render(source, keep_box, allow_upscale=False):
    Image, ImageOps, _ = image_tools()
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert('RGBA')
    box = crop_geometry(image.size, keep_box)
    upscaled = box[2] - box[0] < TARGET[0] - 1e-7 or box[3] - box[1] < TARGET[1] - 1e-7
    if upscaled and not allow_upscale:
        raise ValueError('crop is smaller than delivery size; use a larger original or explicitly --allow-upscale and inspect sharpness')
    output = image.copy() if image.size == TARGET and box == [0, 0, *TARGET] else image.resize(TARGET, Image.Resampling.LANCZOS, box=box)
    return output, image.size, box, upscaled


def finalize(source, output, keep_box=None, allow_upscale=False):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise ValueError('generated original does not exist')
    if source == output or output.exists():
        raise ValueError('keep the generated original; output must be a new, separate PNG file')
    if output.suffix.lower() != '.png':
        raise ValueError('A+ code export writes a .png file')
    image, size, crop, upscaled = render(source, keep_box, allow_upscale)
    record = {'version': 1, 'method': METHOD, 'source_path': Path(os.path.relpath(source, output.parent)).as_posix(), 'source_sha256': sha256(source),
              'source_size': list(size), 'keep_box': list(keep_box) if keep_box is not None else None,
              'crop_box': crop, 'output_size': list(TARGET), 'upscaled': upscaled}
    _, _, PngImagePlugin = image_tools()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text(METADATA_KEY, json.dumps(record, ensure_ascii=False, separators=(',', ':')))
    buffer = BytesIO()
    image.save(buffer, format='PNG', pnginfo=metadata)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(buffer.getvalue())
    return record


def export_errors(root, image_path, requirements):
    """Validate actual pixels and the crop against its retained generated original."""
    if requirements.get('postprocess') != METHOD:
        return []  # Existing candidates retain their original review contract.
    try:
        Image, _, _ = image_tools()
        with Image.open(image_path) as image:
            if image.format != 'PNG' or image.size != TARGET:
                raise ValueError('A+ final pixels must be a 1464x600 PNG')
            record = json.loads(image.info.get(METADATA_KEY, '{}'))
            actual = image.convert('RGBA').tobytes()
        if record.get('version') != 1 or record.get('method') != METHOD:
            raise ValueError('missing code-crop provenance; run finalize_a_plus_image.py before review')
        source = (Path(image_path).resolve().parent / record['source_path']).resolve()
        source.relative_to(Path(root).resolve())
        if source == Path(image_path).resolve() or sha256(source) != record['source_sha256']:
            raise ValueError('retained generated original is missing, changed or replaced by the final image')
        if not isinstance(record.get('upscaled'), bool):
            raise ValueError('invalid upscale record')
        expected, size, crop, upscaled = render(source, record.get('keep_box'), record['upscaled'])
        if (record.get('source_size') != list(size) or record.get('crop_box') != crop
                or record.get('output_size') != list(TARGET) or record['upscaled'] != upscaled
                or actual != expected.tobytes()):
            raise ValueError('final image differs from the recorded crop/resample; export again to a new candidate')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [f'A+ code export: {exc}']
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='retained generated original, not product evidence')
    parser.add_argument('--output', required=True, type=Path, help='new final candidate PNG')
    parser.add_argument('--keep-box', nargs=4, type=float, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'),
                        help='normalized bounds of ALL required content in the EXIF-oriented original')
    parser.add_argument('--allow-upscale', action='store_true', help='explicitly permit enlargement; still inspect sharpness')
    args = parser.parse_args()
    try:
        record = finalize(args.source, args.output, args.keep_box, args.allow_upscale)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(args.output.resolve()), **record}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
