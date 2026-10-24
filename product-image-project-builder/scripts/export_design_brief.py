#!/usr/bin/env python3
"""Export only production-relevant fields from an AI-normalized intake record.

This is a field boundary, not semantic classification or context isolation.
Original assets/provenance remain in the intake archive, outside this packet.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path


def text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def exact_text(value: object, label: str) -> str:
    text(value, label)
    return value


def strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return list(dict.fromkeys(text(item, label) for item in value))


def objects(value: object, label: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be an array of objects")
    return value


def compile_responsibilities(intake, items, id_key, clean_job, available):
    """Filter content groups and image tasks without equating their cardinalities."""
    kept, deferred, seen = [], [], set()
    for item in objects(items, id_key):
        identity = text(item.get(id_key), id_key)
        if identity in seen:
            raise ValueError(f"duplicate {id_key}: {identity}")
        seen.add(identity)
        required = strings(item.get("required_fact_ids", []), "required_fact_ids")
        entry = {id_key: identity, **{key: text(item.get(key), key) for key in ("role", "buyer_question")}}
        if "execution_policy" in item:
            if not isinstance(item["execution_policy"], dict):
                raise ValueError("execution_policy must be an input-assessment object")
            entry["execution_policy"] = deepcopy(item["execution_policy"])
        if "sales_task" in item:
            entry["sales_task"] = text(item["sales_task"], "sales_task")
        if id_key == "image_id" and "content_group_id" in item:
            entry["content_group_id"] = text(item["content_group_id"], "content_group_id")
        if any(fact_id not in available for fact_id in required):
            deferred.append({**entry, "reason": "MISSING_SUPPORTED_FACTS"})
            continue
        entry["must_show"] = strings(item.get("must_show"), "must_show")
        if not entry["must_show"]:
            raise ValueError(f"{identity} needs must_show")
        entry["required_fact_ids"] = required
        entry["product_evidence_ids"] = strings(item.get("product_evidence_ids", []), "product_evidence_ids")
        entry["copy"] = []
        for copy in objects(item.get("copy", []), "copy"):
            if copy.get("status") != "CURRENT":
                continue
            language = text(copy.get("language"), "copy.language")
            if clean_job["language"] != "source" and language != clean_job["language"]:
                continue
            dependencies = strings(copy.get("required_fact_ids", []), "copy.required_fact_ids")
            if any(fact_id not in available for fact_id in dependencies):
                continue
            wording = exact_text(copy.get("text"), "copy.text")
            if intake.get("copy_policy_version") == 1:
                original = exact_text(copy.get("source_text"), "copy.source_text")
                original_language = text(copy.get("source_language"), "copy.source_language")
                if (wording != original or language != original_language) and copy.get("translation_authorized") is not True:
                    raise ValueError(f"{identity} copy changes source wording/language without explicit translation or rewrite authorization")
            entry["copy"].append({"text": wording, "language": language, "required_fact_ids": dependencies})
        kept.append(entry)
    return kept, deferred


def compile_brief(intake: dict) -> dict:
    if not isinstance(intake, dict) or intake.get("schema_version") != 1:
        raise ValueError("unsupported intake schema_version")
    job = intake.get("job")
    product = intake.get("product")
    if not isinstance(job, dict) or not isinstance(product, dict):
        raise ValueError("job and product must be objects")
    clean_job = {"channel": text(job.get("channel"), "job.channel"),
                 "language": text(job.get("language", "source"), "job.language")}
    for key in ("width", "height"):
        value = job.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"job.{key} must be a positive integer")
        clean_job[key] = value
    if clean_job["channel"] == "PREMIUM_A_PLUS" and (clean_job["width"], clean_job["height"]) != (1464, 600):
        raise ValueError("A+ delivery requires only 1464x600; select the current canvas before export")
    if "scope" in job:
        if job["scope"] not in {"full_set", "pilot", "single"}:
            raise ValueError("job.scope must be full_set, pilot or single")
        clean_job["scope"] = job["scope"]
    target = job.get("target_image_count")
    if target is None and job.get("scope") == "single":
        target = 1
    if target is not None:
        if not isinstance(target, int) or isinstance(target, bool) or not 1 <= target <= 40:
            raise ValueError("job.target_image_count must be an integer from 1 to 40")
        if job.get("scope") == "single" and target != 1:
            raise ValueError("single scope requires target_image_count 1")
        clean_job["target_image_count"] = target
    clean_product = {key: text(product.get(key), f"product.{key}") for key in ("name", "sellable_scope")}
    facts = []
    seen_facts = set()
    for item in objects(product.get("facts", []), "product.facts"):
        fact_id = text(item.get("fact_id"), "fact_id")
        if fact_id in seen_facts:
            raise ValueError(f"duplicate fact_id: {fact_id}")
        seen_facts.add(fact_id)
        if item.get("status") == "SUPPORTED":
            facts.append({"fact_id": fact_id, "text": text(item.get("text"), "fact.text")})
    clean_product["facts"] = facts
    available = {item["fact_id"] for item in facts}
    module_items = intake.get("modules", [] if "content_groups" in intake else None)
    modules, deferred = compile_responsibilities(intake, module_items, "image_id", clean_job, available)
    result = {
        "schema_version": 1,
        "job": clean_job,
        "product": clean_product,
        "audience": text(intake.get("audience"), "audience"),
        "brand_rules": [text(item.get("text"), "brand_rule.text") for item in objects(intake.get("brand_rules", []), "brand_rules") if item.get("status") == "CURRENT_REQUIRED"],
        "modules": modules,
        "deferred_modules": deferred,
    }
    if "content_groups" in intake:
        groups, deferred_groups = compile_responsibilities(intake, intake["content_groups"], "group_id", clean_job, available)
        group_ids = {x["group_id"] for x in groups + deferred_groups}
        for item in modules + deferred:
            if item.get("content_group_id") not in group_ids:
                raise ValueError(f"{item['image_id']} needs a registered content_group_id")
        result.update(content_groups=groups, deferred_content_groups=deferred_groups)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("intake", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.intake.resolve() == args.output.resolve():
        parser.error("output must not overwrite the original intake")
    try:
        result = compile_brief(json.loads(args.intake.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"output": str(args.output.resolve()), "retained_module_count": len(result["modules"]), "deferred_module_count": len(result["deferred_modules"]), "context_isolation_verified": False}
    summary["target_image_count"] = result["job"].get("target_image_count")
    summary["content_group_count"] = len(result.get("content_groups", [])) + len(result.get("deferred_content_groups", []))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
