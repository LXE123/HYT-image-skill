#!/usr/bin/env python3
"""Query/edit project records, migrate legacy JSON projects, or export a snapshot."""

import argparse
import json
from pathlib import Path, PurePosixPath
import sys

from project_store import (DATABASE, _read, _write, digest, encode, location,
                           read_json, reader, transaction, recover_generation)


def address_path(root, address):
    relative = PurePosixPath(address)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("record address must be project-relative")
    path = (root / relative).resolve()
    path.relative_to(root)
    if location(path) != (root, relative.as_posix()):
        raise ValueError("address is not a production database record")
    return path


def migrate(root):
    """Import once, preserving pinned record bytes; old files remain archived inputs."""
    if (root / DATABASE).exists():
        raise ValueError("project database already exists; migration never merges two authorities")
    archive = root / "legacy_runtime"
    if archive.exists():
        raise ValueError("legacy archive already exists; migration will not overwrite it")
    legacy = root / "PRODUCT_STATE.json"
    product = json.loads(legacy.read_text(encoding="utf-8"))
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    if product.get("product_id") != index.get("product_id"):
        raise ValueError("legacy product identity differs from index.json")
    paths = [legacy]
    for folder in ("visual_sets", "runs", "qa/visual"):
        paths.extend(sorted((root / folder).rglob("*.json")))
    rows = [(p.relative_to(root).as_posix(), p.read_text(encoding="utf-8")) for p in paths]
    parsed = [(address, raw, json.loads(raw)) for address, raw in rows]
    if any(not isinstance(value, dict) for _, _, value in parsed):
        raise ValueError("all legacy production records must contain JSON objects")
    with (root / DATABASE).open("xb"):
        pass
    try:
        with transaction(root, create=True) as db:
            for address, raw, value in parsed:
                _write(db, address, value, raw)
    except BaseException:
        (root / DATABASE).unlink(missing_ok=True)
        raise
    # The DB is authoritative immediately after commit. A crash during archiving
    # cannot cause old files to be read or re-imported by the runtime.
    for path in paths:
        target = archive / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        path.rename(target)
    return {"database": str(root / DATABASE), "imported_records": len(rows), "legacy_archive": str(archive)}


def editable_put(root, path, value, expected_sha):
    if not isinstance(value, dict):
        raise ValueError("draft must contain a JSON object")
    with transaction(root) as db:
        address = path.relative_to(root).as_posix()
        old = _read(db, address)
        if digest(path) != expected_sha:
            raise ValueError("record changed since export; reread it before replacing the draft")
        if address == "PRODUCT_STATE.json":
            editable = {"sellable_object", "product_identity_baseline", "identity_lockset", "evidence_gaps", "sku"}
            if any(value.get(key) != old.get(key) for key in set(old) | set(value) if key not in editable):
                raise ValueError("progress and decisions are updated by runtime commands, not document editing")
            if old.get("identity_lockset", {}).get("status") == "READY" and value.get("identity_lockset") != old.get("identity_lockset"):
                raise ValueError("revise established identity locks with revise_structure_state.py")
        elif address.endswith("/SET_STATE.json") or address.endswith("/INPUT_SNAPSHOT.json") or address.endswith("/TEMPLATES.json") or address.endswith("/DESIGN_LIBRARY.json"):
            raise ValueError("runtime state and input snapshots are managed by production commands")
        elif address.startswith("visual_sets/"):
            plan_address = "/".join(address.split("/")[:2]) + "/SET_PLAN.json"
            if _read(db, plan_address).get("status") == "APPROVED":
                raise ValueError("approved plan is immutable; create a new set revision")
            if address == plan_address and value.get("status") != old.get("status"):
                raise ValueError("approve a draft through validate_set_plan.py, not a document edit")
        elif address.startswith("runs/"):
            candidate_id = old.get("candidate_id")
            if db.execute("SELECT 1 FROM entities WHERE kind='candidates' AND id=?", (candidate_id,)).fetchone() or db.execute("SELECT 1 FROM generation_claims WHERE candidate_id=?", (candidate_id,)).fetchone():
                raise ValueError("candidate has already been claimed/produced; create a replacement attempt")
        elif address.startswith("qa/visual/"):
            accepted = [json.loads(row[0]) for row in db.execute("SELECT payload FROM entities WHERE kind='candidates' AND status='ACCEPTED'")]
            if any(candidate.get("checks", {}).get("visual", {}).get("report_path") == address for candidate in accepted):
                raise ValueError("accepted candidate review is historical; use a new review address")
        _write(db, address, value)
    return {"address": address, "sha256": digest(path)}


def export_snapshot(root, destination):
    destination = destination.resolve()
    if destination == root or root in destination.parents:
        raise ValueError("export to a separate directory; exported JSON is a read-only snapshot")
    if destination.exists():
        raise ValueError("export directory exists; choose a new snapshot path")
    with reader(root) as db:
        addresses = ["PRODUCT_STATE.json"]
        addresses += [f"visual_sets/{row[0]}/SET_STATE.json" for row in db.execute("SELECT id FROM sets")]
        addresses += [row[0] for row in db.execute("SELECT address FROM records")]
        contents = [(key, encode(_read(db, key)).encode("utf-8") if key == "PRODUCT_STATE.json" or key.endswith("/SET_STATE.json")
                     else db.execute("SELECT payload FROM records WHERE address=?", (key,)).fetchone()[0].encode("utf-8"))
                    for key in addresses]
    for key, data in contents:
        path = destination / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {"snapshot": str(destination), "records": len(contents), "editable": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("action", choices=("get", "put", "list", "migrate", "export", "recover"))
    parser.add_argument("--address", help="stable logical address, e.g. PRODUCT_STATE.json")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-sha")
    parser.add_argument("--claim-token")
    parser.add_argument("--reason")
    args = parser.parse_args()
    root = args.package.resolve()
    try:
        if args.action == "migrate":
            result = migrate(root)
        elif args.action == "recover":
            if not args.address:
                raise ValueError("recover requires a standalone contract --address")
            path = address_path(root, args.address)
            with transaction(root):
                if read_json(path).get("visual_set"):
                    raise ValueError("use set_runtime.py recover for set-linked work")
                result = recover_generation(root, args.address, args.claim_token, args.reason)
        elif args.action == "export":
            if not args.output:
                raise ValueError("export requires --output")
            result = export_snapshot(root, args.output)
        elif args.action == "list":
            with reader(root) as db:
                result = {"database": DATABASE, "sets": [dict(zip(("set_id", "module_id", "status"), row)) for row in db.execute("SELECT set_id,id,status FROM modules ORDER BY set_id,position")],
                          "records": [row[0] for row in db.execute("SELECT address FROM records ORDER BY address")],
                          "active_generations": [dict(zip(("candidate_id", "contract_address", "created_at", "claim_token"), row)) for row in db.execute("SELECT candidate_id,contract_address,created_at,token FROM generation_claims WHERE status='RUNNING'")]}
        else:
            if not args.address:
                raise ValueError("get/put requires --address")
            path = address_path(root, args.address)
            if args.action == "put":
                if not args.input or not args.expected_sha:
                    raise ValueError("put requires --input and --expected-sha from get")
                result = editable_put(root, path, json.loads(args.input.read_text(encoding="utf-8")), args.expected_sha)
            else:
                with transaction(root):
                    result = read_json(path)
                    if args.output:
                        if location(args.output) or args.output.resolve() == root / DATABASE:
                            raise ValueError("export the editable draft outside the production record namespace")
                        with args.output.open("x", encoding="utf-8") as stream:
                            stream.write(encode(result))
                        result = {"draft": str(args.output.resolve()), "sha256": digest(path)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
