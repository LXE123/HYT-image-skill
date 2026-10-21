#!/usr/bin/env python3
"""Run integrated same-view geometry QA and record its summary in product state."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from context_store import load_contract


SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
STATUS_EXIT = {"AUTO_PASSED": 0, "REJECTED": 2, "REVIEW_REQUIRED": 3, "REVIEW_REQUIRED_NO_TEMPLATE": 3}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_new_json(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"immutable report already exists: {path}")
    write_json(path, value)


def safe_relative(value: object) -> bool:
    return isinstance(value, str) and bool(value) and not PurePosixPath(value).is_absolute() and ".." not in PurePosixPath(value).parts


def mask_from_rgb(rgb, settings: dict):
    red, green, blue = (rgb[:, :, i].astype(np.int16) for i in range(3))
    result = (red >= int(settings["min_red"])) & ((red - green) >= int(settings["min_red_green_delta"])) & ((red - blue) >= int(settings["min_red_blue_delta"]))
    x1, y1, x2, y2 = map(int, settings["roi"])
    roi = np.zeros(result.shape, dtype=bool)
    roi[y1:y2, x1:x2] = True
    return result & roi


def centroid(mask):
    ys, xs = np.nonzero(mask)
    return None if not len(xs) else (float(xs.mean()), float(ys.mean()))


def bounds(mask):
    ys, xs = np.nonzero(mask)
    return None if not len(xs) else (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def translate(mask, dx: int, dy: int):
    result = np.zeros_like(mask)
    height, width = mask.shape
    sx1, sx2 = max(0, -dx), min(width, width - dx)
    sy1, sy2 = max(0, -dy), min(height, height - dy)
    dx1, dx2 = max(0, dx), min(width, width + dx)
    dy1, dy2 = max(0, dy), min(height, height + dy)
    if sx2 > sx1 and sy2 > sy1:
        result[dy1:dy2, dx1:dx2] = mask[sy1:sy2, sx1:sx2]
    return result


def width(mask, x: int, y_range: list[int]) -> int:
    y1, y2 = map(int, y_range)
    positions = np.flatnonzero(mask[y1:y2, int(x)])
    return 0 if not len(positions) else int(positions.max() - positions.min() + 1)


def edges(mask):
    return mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))


def record_state(root: Path, state: dict, contract: dict, contract_path: Path, candidate_path: Path, result: dict) -> None:
    report = result.get("report") or f"qa/geometry/reports/{result['run_id']}/{result['candidate_id']}/result.json"
    summary = {
        "run_id": result["run_id"],
        "candidate_id": result["candidate_id"],
        "status": result["status"],
        "candidate_sha256": result["candidate_sha256"],
        "report": report,
        "checked_at": result["checked_at"],
    }
    for key in ("template_sha256", "config", "config_sha256", "reason"):
        if key in result:
            summary[key] = result[key]

    checks = state.setdefault("geometry_checks", [])
    if not isinstance(checks, list):
        raise ValueError("PRODUCT_STATE.json geometry_checks must be an array")
    previous = next((
        item for item in checks
        if isinstance(item, dict)
        and item.get("run_id") == result["run_id"]
        and item.get("candidate_id") == result["candidate_id"]
        and item.get("config_sha256") == summary.get("config_sha256")
    ), None)
    if previous:
        if previous.get("candidate_sha256") not in (None, result["candidate_sha256"]):
            raise ValueError("candidate ID is already bound to a different hash in PRODUCT_STATE.json")
        previous.clear()
        previous.update(summary)
    else:
        checks.append(summary)

    candidates = state.setdefault("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("PRODUCT_STATE.json candidates must be an array")
    candidate = next((item for item in candidates if isinstance(item, dict) and item.get("candidate_id") == result["candidate_id"]), None)
    if candidate is None:
        candidate = {
            "candidate_id": result["candidate_id"],
            "run_id": result["run_id"],
            "path": candidate_path.relative_to(root).as_posix(),
            "sha256": result["candidate_sha256"],
            "status": "PENDING_REVIEW",
            "source_contract": contract_path.relative_to(root).as_posix(),
            "checks": {},
        }
        candidates.append(candidate)
    elif candidate.get("sha256") not in (None, result["candidate_sha256"]):
        raise ValueError("candidate ID is already bound to a different candidate hash")
    candidate.setdefault("checks", {})["geometry"] = summary

    state["workflow"] = {
        "status": "HUMAN_REVIEW",
        "active_run_id": result["run_id"],
        "active_view": contract.get("target_view"),
        "active_contract": contract_path.relative_to(root).as_posix(),
        "active_candidate_id": result["candidate_id"],
        "geometry": summary,
        "next_action": "HUMAN_REVIEW_CANDIDATE",
    }
    for run in state.get("runs", []):
        if isinstance(run, dict) and run.get("run_id") == result["run_id"]:
            run["status"] = "HUMAN_REVIEW"
    write_json(root / "PRODUCT_STATE.json", state)


def reuse_report(root: Path, state: dict, contract: dict, contract_path: Path, candidate_path: Path, result_path: Path, candidate_hash: str, config_hash: str | None) -> int | None:
    if not result_path.exists():
        return None
    try:
        result = load_json(result_path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Existing geometry report is invalid: {error}")
        return 4
    if result.get("candidate_sha256") != candidate_hash or result.get("config_sha256") != config_hash:
        print("Candidate ID already has a geometry report for different candidate or config content")
        return 4
    try:
        record_state(root, state, contract, contract_path, candidate_path, result)
    except (OSError, ValueError) as error:
        print(f"Cannot record existing geometry result: {error}")
        return 4
    print(f"REUSE  {result.get('status')}: {result_path.parent}")
    return STATUS_EXIT.get(result.get("status"), 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    root = args.package.resolve()
    contract_path = args.contract if args.contract.is_absolute() else root / args.contract
    contract_path = contract_path.resolve()
    try:
        contract_path.relative_to(root / "runs")
        contract = load_contract(root, contract_path)
        state = load_json(root / "PRODUCT_STATE.json")
        package_index = load_json(root / "index.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Invalid package or contract: {error}")
        return 4

    run_id = contract.get("run_id")
    view = contract.get("target_view")
    candidate_id = contract.get("candidate_id") or (f"{run_id}-{view}" if run_id and view else None)
    output_path = contract.get("output_path")
    if not all(isinstance(value, str) and SAFE_ID.fullmatch(value) for value in (run_id, view, candidate_id)) or not safe_relative(output_path):
        print("Contract has invalid run, view, candidate, or output identifiers")
        return 4
    candidate_path = (root / output_path).resolve()
    try:
        candidate_path.relative_to(root / "candidates")
    except ValueError:
        print("Contract candidate lies outside the package candidates directory")
        return 4
    if "rejected" in candidate_path.parts or not candidate_path.is_file():
        print("Contract candidate is missing or already rejected")
        return 4
    if contract.get("sku") != state.get("sku") or state.get("product_id") != package_index.get("product_id"):
        print("SKU or product identity does not match state, contract, and index")
        return 4
    if not any(isinstance(item, dict) and item.get("run_id") == run_id for item in state.get("runs", [])):
        print("Contract run is not registered in PRODUCT_STATE.json")
        return 4
    workflow = state.get("workflow", {})
    if workflow and workflow.get("active_contract") not in (None, contract_path.relative_to(root).as_posix()):
        print("Contract is not the active contract in PRODUCT_STATE.json")
        return 4
    lockset = state.get("identity_lockset", {})
    if lockset.get("status") != "READY" or contract.get("identity_lockset_version") != lockset.get("version"):
        print("Identity lockset is absent, stale, or inconsistent")
        return 4

    candidate_hash = digest(candidate_path)
    report_root = root / "qa" / "geometry" / "reports" / run_id / candidate_id
    config_path = args.config
    if config_path is None:
        config_path = root / "qa" / "geometry" / "templates" / view / "config.json"
    elif not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    try:
        config_path.relative_to(root / "qa" / "geometry" / "templates")
    except ValueError:
        print("Geometry config must be inside qa/geometry/templates")
        return 4

    now = datetime.now(timezone.utc).isoformat()
    base = {
        "schema_version": 2,
        "candidate_id": candidate_id,
        "run_id": run_id,
        "sku": contract.get("sku"),
        "view": view,
        "contract": contract_path.relative_to(root).as_posix(),
        "contract_sha256": digest(contract_path),
        "candidate_file": candidate_path.relative_to(root).as_posix(),
        "candidate_sha256": candidate_hash,
        "checked_at": now,
        "human_review_required_before_approval": True,
    }

    if not config_path.is_file():
        report_dir = report_root / "no-template"
        result_path = report_dir / "result.json"
        reused = reuse_report(root, state, contract, contract_path, candidate_path, result_path, candidate_hash, None)
        if reused is not None:
            return reused
        result = {**base, "status": "REVIEW_REQUIRED_NO_TEMPLATE", "reason": "approved_same_view_template_missing", "report": result_path.relative_to(root).as_posix()}
        try:
            write_new_json(result_path, result)
            record_state(root, state, contract, contract_path, candidate_path, result)
        except (OSError, ValueError) as error:
            print(f"Cannot record geometry result: {error}")
            return 4
        print(f"REVIEW_REQUIRED_NO_TEMPLATE: {report_dir}")
        return 3

    try:
        config = load_json(config_path)
        config_hash = digest(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Invalid geometry config: {error}")
        return 4
    report_dir = report_root / config_hash[:12]
    result_path = report_dir / "result.json"
    base.update({
        "config": config_path.relative_to(root).as_posix(),
        "config_sha256": config_hash,
        "report": result_path.relative_to(root).as_posix(),
    })
    if config.get("approval_status") != "APPROVED":
        reused = reuse_report(root, state, contract, contract_path, candidate_path, result_path, candidate_hash, config_hash)
        if reused is not None:
            return reused
        result = {
            **base,
            "status": "REVIEW_REQUIRED_NO_TEMPLATE",
            "reason": "same_view_template_not_approved",
        }
        try:
            write_new_json(result_path, result)
            record_state(root, state, contract, contract_path, candidate_path, result)
        except (OSError, ValueError) as error:
            print(f"Cannot record geometry result: {error}")
            return 4
        print(f"REVIEW_REQUIRED_NO_TEMPLATE: {report_dir}")
        return 3

    if config.get("identity_lockset_version") != lockset.get("version"):
        print("Geometry config does not match the current identity lockset")
        return 4
    renders = {item.get("template_id") for item in package_index.get("render_templates", []) if isinstance(item, dict) and item.get("status") == "approved"}
    if not config.get("source_render_template_ids") or not set(config.get("source_render_template_ids", [])).issubset(renders):
        print("Approved geometry config lacks current approved render sources")
        return 4
    if config.get("sku") != contract.get("sku") or config.get("view") != view:
        print("Geometry config SKU or view does not match the contract")
        return 4

    reused = reuse_report(root, state, contract, contract_path, candidate_path, result_path, candidate_hash, config_hash)
    if reused is not None:
        return reused

    base_dir = config_path.parent
    try:
        template_path, mask_path, annotation_path = tuple((base_dir / config["template"][key]).resolve() for key in ("image", "mask", "annotation"))
        for path in (template_path, mask_path, annotation_path):
            path.relative_to(root)
        load_json(annotation_path)
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        print("Template path escapes the package root, or annotation is missing or invalid")
        return 4
    if not template_path.is_file() or not mask_path.is_file():
        print("Geometry template is incomplete")
        return 4

    try:
        global np, Image
        import numpy as np
        from PIL import Image
    except ImportError as error:
        print(f"Missing dependency: {error.name}. Use the package-local .runtime.", file=sys.stderr)
        return 4

    registration_dir = root / "qa" / "geometry" / "registered" / run_id / candidate_id
    registration_dir.mkdir(parents=True, exist_ok=True)
    copied = registration_dir / candidate_path.name
    if copied.exists() and digest(copied) != candidate_hash:
        print("Candidate ID is already registered to different file content")
        return 4
    if not copied.exists():
        shutil.copy2(candidate_path, copied)
    try:
        rgb = np.asarray(Image.open(candidate_path).convert("RGB"))
        template = np.asarray(Image.open(mask_path).convert("L")) >= 128
    except (OSError, ValueError) as error:
        print(f"Cannot read candidate or template image: {error}")
        return 4

    base.update({
        "template_file": template_path.relative_to(root).as_posix(),
        "template_sha256": digest(template_path),
    })
    expected = (int(config["canvas"]["height"]), int(config["canvas"]["width"]))
    if rgb.shape[:2] != expected:
        result = {**base, "status": "REJECTED", "reason": "canvas_mismatch", "actual_canvas": [rgb.shape[1], rgb.shape[0]], "expected_canvas": [expected[1], expected[0]]}
        write_new_json(result_path, result)
        record_state(root, state, contract, contract_path, candidate_path, result)
        return 2

    candidate = mask_from_rgb(rgb, config["segmentation"])
    source_center, candidate_center = centroid(template), centroid(candidate)
    if source_center is None or candidate_center is None or candidate.sum() < 100:
        result = {**base, "status": "REVIEW_REQUIRED", "reason": "unreliable_segmentation_or_alignment"}
        write_new_json(result_path, result)
        record_state(root, state, contract, contract_path, candidate_path, result)
        return 3
    dx, dy = (int(round(source_center[0] - candidate_center[0])), int(round(source_center[1] - candidate_center[1])))
    if max(abs(dx), abs(dy)) > int(config["registration"]["max_translation_px"]):
        result = {**base, "status": "REVIEW_REQUIRED", "reason": "translation_exceeds_limit", "translation_px": [dx, dy]}
        write_new_json(result_path, result)
        record_state(root, state, contract, contract_path, candidate_path, result)
        return 3

    aligned = translate(candidate, dx, dy)
    source_box, candidate_box = bounds(template), bounds(aligned)
    if source_box is None or candidate_box is None:
        result = {**base, "status": "REVIEW_REQUIRED", "reason": "empty_registered_bounds"}
        write_new_json(result_path, result)
        record_state(root, state, contract, contract_path, candidate_path, result)
        return 3
    scale_delta = max(abs((candidate_box[2] - candidate_box[0]) / (source_box[2] - source_box[0]) - 1), abs((candidate_box[3] - candidate_box[1]) / (source_box[3] - source_box[1]) - 1))
    union = int((template | aligned).sum())
    difference = 100 * int((template ^ aligned).sum()) / max(1, union)
    rows, width_failed = {}, False
    for name, spec in config["measurement_columns"].items():
        wanted, actual = width(template, spec["x"], spec["y_range"]), width(aligned, spec["x"], spec["y_range"])
        error = actual - wanted
        passed = abs(error) <= float(config["checks"]["max_width_error_px"]) and abs(100 * error / max(1, wanted)) <= float(config["checks"]["max_width_error_percent"])
        rows[name] = {"expected_px": wanted, "actual_px": actual, "error_px": error, "passed": passed}
        width_failed |= not passed
    rejected = difference > float(config["checks"]["max_outline_difference_percent"]) or scale_delta > float(config["registration"]["max_scale_delta"]) or width_failed
    status = "REJECTED" if rejected else "AUTO_PASSED"
    result = {
        **base,
        "status": status,
        "registration": {"translation_px": [dx, dy], "scale_delta": round(scale_delta, 6)},
        "outline": {"difference_percent": round(difference, 3), "allowed_percent": config["checks"]["max_outline_difference_percent"]},
        "measurements": rows,
    }
    registration_record = registration_dir / "record.json"
    if registration_record.exists():
        try:
            existing_registration = load_json(registration_record)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"Existing candidate registration is invalid: {error}")
            return 4
        if existing_registration.get("candidate_sha256") != candidate_hash:
            print("Candidate registration record is bound to different content")
            return 4
    else:
        write_new_json(registration_record, {**base, "registered_file": copied.relative_to(root).as_posix(), "status": "REGISTERED"})
    write_json(report_dir / "measurements.json", {"measurements": rows})
    overlay = rgb.copy()
    overlay[edges(template)] = [0, 220, 0]
    overlay[edges(aligned)] = [255, 40, 40]
    Image.fromarray(overlay).save(report_dir / "overlay.png")
    diff = np.zeros((*template.shape, 3), dtype=np.uint8)
    diff[template & aligned] = [220, 220, 220]
    diff[template & ~aligned] = [0, 120, 255]
    diff[aligned & ~template] = [255, 50, 50]
    Image.fromarray(diff).save(report_dir / "outline_diff.png")
    write_new_json(result_path, result)
    try:
        record_state(root, state, contract, contract_path, candidate_path, result)
    except (OSError, ValueError) as error:
        print(f"Geometry report was written, but state update failed: {error}")
        return 4
    print(f"{status}: {report_dir}")
    return STATUS_EXIT[status]


if __name__ == "__main__":
    raise SystemExit(main())
