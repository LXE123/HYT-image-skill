#!/usr/bin/env python3
"""Compile a draft's evidence-backed instructions before candidate generation."""
from project_store import read_json as store_read, write_json as store_write, exists as store_exists, transaction

import argparse
import json
from pathlib import Path

from quality_rules import compile_prompt, file_at, validate_quality
from module_language import resolve_module_language
from structure_state import dependency_errors
from execution_policy import policy_errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--contract", required=True)
    args = parser.parse_args()
    with transaction(args.package):
        return execute(args, parser)


def execute(args, parser):
    root = args.package.resolve()
    try:
        path = file_at(root, args.contract)
        path.relative_to(root / "runs")
        contract = store_read(path)
        state = store_read(root / "PRODUCT_STATE.json")
        index = store_read(root / "index.json")
        if contract.get("visual_set"):
            raise ValueError("set contracts are compiled at materialization; revise the set plan instead")
        if store_exists(root / contract["output_path"]) or any(x.get("candidate_id") == contract.get("candidate_id") for x in state.get("candidates", [])):
            raise ValueError("candidate exists or was registered; create a replacement contract")
        locks = {x["lock_id"]: x for x in state.get("identity_lockset", {}).get("locks", [])}
        selected = [locks[x] for x in contract.get("required_lock_ids", []) if x in locks]
        failures = dependency_errors(state, contract.get("required_lock_ids"), selected)
        if failures:
            raise ValueError("; ".join(failures))
        contract["identity_lockset_version"] = state["identity_lockset"]["version"]
        if contract.get("module_language_policy_version") == 1:
            contract["module_language"] = resolve_module_language(contract)
        errors = validate_quality(root, contract, index, locks)
        errors.extend(policy_errors(contract, generation=True))
        if errors:
            raise ValueError("; ".join(errors))
        contract["resolved_identity_locks"] = [locks[x] for x in contract["required_lock_ids"]]
        contract["generation_prompt"] = compile_prompt(contract)
        store_write(path, contract)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"COMPILE  {args.contract}; inspect generation_prompt and attach referenced images to the generator")
    return 0


if __name__ == "__main__":
    from runtime_log import run_cli
    raise SystemExit(run_cli(main))
