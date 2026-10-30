#!/usr/bin/env python3
"""Crop and resample a generated original to an exact 1464x600 PNG; never overwrite."""
from project_store import read_json as store_read, digest as store_digest, exists as store_exists

import argparse
from io import BytesIO
import json
import math
import os
from pathlib import Path

TARGET = (1464, 600)
METHOD = 'CODE_CROP_RESIZE'
METADATA_KEY = 'a_plus_export'
CROP_REVIEW = 'OBSERVED_LAYOUT_V1'


def image_tools():
    try:
        from PIL import Image, ImageOps, PngImagePlugin
    except ImportError as exc:
        raise ValueError('Pillow is required for code cropping; use the available image runtime or install the declared Pillow dependency') from exc
    return Image, ImageOps, PngImagePlugin


def sha256(path):
    return store_digest(path)


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


def assess_crop(size, source_hash, contract, report, keep_box=None):
    """Project source annotations into the proposed final frame; no object detection."""
    from quality_rules import composition_result, normalized_box
    observed = report.get('composition') or {}
    if not isinstance(observed, dict) or any(not isinstance(observed.get(key), list) for key in ('product_regions', 'copy_regions', 'protected_regions')):
        return {'status': 'REVIEW_REQUIRED', 'reasons': ['source composition needs actual labelled region lists']}
    if (report.get('phase') != 'SOURCE_IMAGE' or observed.get('coordinate_space') != 'SOURCE_IMAGE'
            or report.get('candidate_sha256') != source_hash or observed.get('image_sha256') != source_hash):
        return {'status': 'REVIEW_REQUIRED', 'reasons': ['source review is missing or belongs to different image bytes/coordinates']}
    regions = [item for key in ('product_regions', 'copy_regions', 'protected_regions') for item in observed.get(key, [])]
    if not regions or any(not isinstance(item, dict) or not normalized_box(item.get('box')) for item in regions):
        return {'status': 'REVIEW_REQUIRED', 'reasons': ['annotate all required source regions before calculating a crop']}
    effective_keep = keep_box
    if effective_keep is None and abs(size[0]/size[1] - TARGET[0]/TARGET[1]) > 1e-9:
        boxes = [item['box'] for item in regions]
        effective_keep = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
    try:
        crop = crop_geometry(size, effective_keep)
    except ValueError as exc:
        return {'status': 'FAIL', 'reasons': [str(exc)]}
    normalized_crop = [round(crop[i]/size[i % 2], 8) for i in range(4)]
    result = {'status': 'REVIEW_REQUIRED', 'crop_box': crop, 'normalized_crop_box': normalized_crop, 'keep_box': effective_keep}
    projected = {**observed, 'coordinate_space': 'PROJECTED_FINAL'}
    for key in ('product_regions', 'copy_regions', 'protected_regions'):
        projected[key] = []
        for item in observed.get(key, []):
            b = [item['box'][i]*size[i % 2] for i in range(4)]
            if b[0] < crop[0]-1e-7 or b[1] < crop[1]-1e-7 or b[2] > crop[2]+1e-7 or b[3] > crop[3]+1e-7:
                return {**result, 'status': 'FAIL', 'reasons': [f"crop cuts required region: {item.get('label', key)}"]}
            box = [min(1.0, max(0.0, (b[i]-crop[i % 2])/(crop[i % 2 + 2]-crop[i % 2]))) for i in range(4)]
            projected[key].append({**item, 'box': box})
    geometry = composition_result(contract, projected, source_hash, coordinate_space='PROJECTED_FINAL')
    result.update(geometry=geometry, projected_composition=projected, reasons=list(geometry['reasons']))
    if geometry['status'] != 'PASS':
        result['status'] = geometry['status']
        return result
    reviewed = report.get('reviewed_crop_box')
    if not normalized_box(reviewed) or any(abs(a-b) > 1e-7 for a, b in zip(reviewed, normalized_crop)):
        result['reasons'].append('review the proposed crop and record this exact normalized crop box')
    if report.get('inspection_method') != 'VISUAL_INSPECTION' or not report.get('reviewer'):
        result['reasons'].append('identify the actual source/crop visual reviewer')
    if not isinstance(report.get('checks'), dict):
        return {**result, 'status': 'REVIEW_REQUIRED', 'reasons': [*result['reasons'], 'source crop needs recorded visual checks']}
    for key in ('layout_output', 'design_quality'):
        check = report.get('checks', {}).get(key, {})
        if not isinstance(check, dict) or check.get('status') != 'PASS' or not isinstance(check.get('observation'), str) or not check['observation'].strip():
            result['reasons'].append(f'review {key}: required content, scale, copy space and visual balance after this crop')
    failed = any(isinstance(report['checks'].get(key), dict) and report['checks'][key].get('status') == 'FAIL' for key in ('layout_output', 'design_quality'))
    result['status'] = 'FAIL' if failed else 'REVIEW_REQUIRED' if result['reasons'] else 'PASS'
    return result


def crop_context(root, contract_path, report_path, source, keep_box=None):
    from context_store import load_contract
    from quality_rules import file_at, review_binding
    root = Path(root).resolve()
    source = Path(source).resolve()
    source.relative_to(root)
    paths = [file_at(root, str(Path(p).resolve().relative_to(root)) if Path(p).is_absolute() else str(p)) for p in (contract_path, report_path)]
    contract = load_contract(root, paths[0])
    report = store_read(paths[1])
    if not isinstance(report, dict):
        raise ValueError('source review must be a QA JSON object')
    source_hash = sha256(source)
    if (report.get('schema_version') != 2 or report.get('candidate_id') != contract.get('candidate_id')
            or report.get('contract_sha256') != sha256(paths[0])
            or report.get('review_binding') != review_binding(root, contract, source_hash, report.get('comparison_images', []))):
        raise ValueError('source review binding is stale; inspect current source and contract in a new report')
    Image, ImageOps, _ = image_tools()
    with Image.open(source) as image:
        size = ImageOps.exif_transpose(image).size
    return assess_crop(size, source_hash, contract, report, keep_box), paths


def finalize(source, output, keep_box=None, allow_upscale=False, *, package=None, contract_path=None, review_path=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise ValueError('generated original does not exist')
    if source == output or store_exists(output):
        raise ValueError('keep the generated original; output must be a new, separate PNG file')
    if output.suffix.lower() != '.png':
        raise ValueError('A+ code export writes a .png file')
    guard = None
    if any(x is not None for x in (package, contract_path, review_path)):
        if not all(x is not None for x in (package, contract_path, review_path)):
            raise ValueError('guarded export requires --package, --contract and --review together')
        output.relative_to(Path(package).resolve())
        decision, paths = crop_context(package, contract_path, review_path, source, keep_box)
        if decision['status'] != 'PASS':
            raise ValueError(decision['status'] + ': ' + '; '.join(decision['reasons']))
        keep_box = decision['keep_box']
        guard = {'method': CROP_REVIEW, 'contract_path': Path(os.path.relpath(paths[0], output.parent)).as_posix(),
                 'contract_sha256': sha256(paths[0]), 'report_path': Path(os.path.relpath(paths[1], output.parent)).as_posix(),
                 'report_sha256': sha256(paths[1])}
    image, size, crop, upscaled = render(source, keep_box, allow_upscale)
    record = {'version': 1, 'method': METHOD, 'source_path': Path(os.path.relpath(source, output.parent)).as_posix(), 'source_sha256': sha256(source),
              'source_size': list(size), 'keep_box': list(keep_box) if keep_box is not None else None,
              'crop_box': crop, 'output_size': list(TARGET), 'upscaled': upscaled}
    if guard:
        record['layout_review'] = guard
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
        guard = record.get('layout_review')
        if requirements.get('pre_crop_review') not in (None, CROP_REVIEW):
            raise ValueError('unsupported source composition review method')
        if requirements.get('pre_crop_review') == CROP_REVIEW and not guard:
            raise ValueError('missing source composition review; run guarded export before final QA')
        if guard:
            if guard.get('method') != CROP_REVIEW:
                raise ValueError('unknown source composition review method')
            base = Path(image_path).resolve().parent
            contract_path, report_path = [(base/guard[key]).resolve() for key in ('contract_path', 'report_path')]
            for path, key in ((contract_path, 'contract_sha256'), (report_path, 'report_sha256')):
                path.relative_to(Path(root).resolve())
                if sha256(path) != guard[key]:
                    raise ValueError('source crop review or its contract changed')
            decision, _ = crop_context(root, contract_path, report_path, source, record.get('keep_box'))
            if decision['status'] != 'PASS' or decision['crop_box'] != record['crop_box']:
                raise ValueError('source composition review no longer permits this crop')
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
    parser.add_argument('--package', type=Path, help='product package root for guarded export')
    parser.add_argument('--contract', type=Path, help='existing candidate contract, package-relative or absolute')
    parser.add_argument('--review', type=Path, help='source-image QA report, package-relative or absolute')
    parser.add_argument('--check-only', action='store_true', help='return crop proposal/disposition without writing an output')
    args = parser.parse_args()
    try:
        if args.check_only:
            if not all(x is not None for x in (args.package, args.contract, args.review)):
                raise ValueError('--check-only requires --package, --contract and --review')
            decision, _ = crop_context(args.package, args.contract, args.review, args.source, args.keep_box)
            print(json.dumps(decision, ensure_ascii=False, indent=2))
            return 0
        record = finalize(args.source, args.output, args.keep_box, args.allow_upscale,
                          package=args.package, contract_path=args.contract, review_path=args.review)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(args.output.resolve()), **record}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
