#!/usr/bin/env python3
"""Compile a draft's evidence-backed instructions before candidate generation."""

import argparse
import json
from pathlib import Path

from quality_rules import compile_prompt, file_at, validate_quality
from module_language import resolve_module_language


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--contract", required=True)
    args = parser.parse_args()
    root = args.package.resolve()
    try:
        path = file_at(root, args.contract)
        path.relative_to(root / "runs")
        contract = json.loads(path.read_text())
        state = json.loads((root / "PRODUCT_STATE.json").read_text())
        index = json.loads((root / "index.json").read_text())
        if contract.get("visual_set"):
            raise ValueError("set contracts are compiled at materialization; revise the set plan instead")
        if (root / contract["output_path"]).exists() or any(x.get("candidate_id") == contract.get("candidate_id") for x in state.get("candidates", [])):
            raise ValueError("candidate exists or was registered; create a replacement contract")
        locks = {x["lock_id"]: x for x in state.get("identity_lockset", {}).get("locks", [])}
        if contract.get("module_language_policy_version") == 1:
            contract["module_language"] = resolve_module_language(contract)
        errors = validate_quality(root, contract, index, locks)
        if errors:
            raise ValueError("; ".join(errors))
        contract["resolved_identity_locks"] = [locks[x] for x in contract["required_lock_ids"]]
        contract["generation_prompt"] = compile_prompt(contract)
        path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"COMPILE  {args.contract}; inspect generation_prompt and attach referenced images to the generator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
