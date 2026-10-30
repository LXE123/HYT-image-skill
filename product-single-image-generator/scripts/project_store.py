"""Project-local SQLite state. JSON addresses identify records, not writable files.

Images and intake evidence remain files. All production records use this module;
short BEGIN IMMEDIATE transactions serialize changes across the three skills.
"""

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid

from runtime_log import _transaction_id, log_event, log_error

DATABASE = "PROJECT.sqlite3"
_active = ContextVar("project_transaction", default=None)
COLLECTIONS = {"runs": "run_id", "candidates": "candidate_id", "geometry_checks": None,
               "decision_log": None}
SCHEMA = (
    "CREATE TABLE product (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)",
    "CREATE TABLE entities (kind TEXT NOT NULL, id TEXT NOT NULL, position INTEGER NOT NULL, status TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id))",
    "CREATE INDEX entity_status ON entities(kind,status)",
    "CREATE TABLE sets (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    "CREATE TABLE modules (set_id TEXT NOT NULL REFERENCES sets(id), id TEXT NOT NULL, position INTEGER NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(set_id,id))",
    "CREATE INDEX module_status ON modules(set_id,status,position)",
    "CREATE TABLE records (address TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL)",
    "CREATE TABLE generation_claims (candidate_id TEXT PRIMARY KEY, token TEXT NOT NULL UNIQUE, contract_address TEXT NOT NULL, contract_sha256 TEXT NOT NULL, status TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
)


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def location(path):
    """Resolve the stable record namespace without searching ancestor directories."""
    path = Path(path).absolute()
    parts = path.parts
    if path.name == "PRODUCT_STATE.json":
        return path.parent.resolve(), "PRODUCT_STATE.json"
    for name in ("visual_sets", "runs", "qa"):
        if name not in parts or path.suffix != ".json":
            continue
        # Use the last matching component (a product may itself be called 'runs').
        pos = len(parts) - 1 - parts[::-1].index(name)
        tail = parts[pos:]
        if name == "qa" and not (len(tail) >= 3 and tail[1] == "visual"):
            continue
        if len(tail) < 3:
            continue
        root = Path(*parts[:pos]).resolve()
        resolved = path.resolve()
        resolved.relative_to(root)
        return root, "/".join(tail)
    return None


def connect(root, create=False):
    root = Path(root).resolve()
    path = root / DATABASE
    if not path.is_file() and not create:
        raise ValueError(f"missing {DATABASE}; migrate an existing JSON project with project_records.py migrate")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    db = None
    try:
        db = sqlite3.connect(str(path) if create else path.as_uri() + "?mode=rw", uri=not create,
                             timeout=5, isolation_level=None)
        db.execute("PRAGMA foreign_keys=ON")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise ValueError(f"unsupported project database version: {version}")
        if version == 0:
            if not create:
                raise ValueError("uninitialized project database")
            db.execute("BEGIN IMMEDIATE")
            try:
                # Another initializer may have completed while this connection waited.
                if db.execute("PRAGMA user_version").fetchone()[0] == 0:
                    for statement in SCHEMA:
                        db.execute(statement)
                    db.execute("PRAGMA user_version=1")
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return db
    except (sqlite3.Error, ValueError) as exc:
        if db is not None:
            db.close()
        if isinstance(exc, sqlite3.Error):
            raise ValueError(f"project database: {exc}") from exc
        raise


@contextmanager
def transaction(root, create=False):
    root = Path(root).resolve()
    current = _active.get()
    if current:
        if current[0] != root:
            raise ValueError("one operation cannot mutate two product databases")
        yield current[1]
        return
    db = None
    token = None
    log_token = _transaction_id.set(uuid.uuid4().hex)
    started = time.monotonic()
    phase = "connect"
    try:
        log_event(root, "transaction.requested")
        db = connect(root, create)
        phase = "begin"
        db.execute("BEGIN IMMEDIATE")
        token = _active.set((root, db))
        phase = "body"
        log_event(root, "transaction.started")
        yield db
        phase = "commit"
        db.commit()
        log_event(root, "transaction.committed", changed_rows=db.total_changes,
                  duration_ms=round((time.monotonic() - started) * 1000))
    except BaseException as exc:
        if db is not None:
            try:
                db.rollback()
            except sqlite3.Error as rollback_error:
                log_error(rollback_error, "transaction.rollback_failed", root=root)
        log_error(exc, "transaction.rolled_back" if token is not None else "transaction.failed", root=root,
                  phase=phase, duration_ms=round((time.monotonic() - started) * 1000))
        if isinstance(exc, sqlite3.Error):
            raise ValueError(f"project transaction: {exc}") from exc
        raise
    finally:
        if token is not None:
            _active.reset(token)
        if db is not None:
            db.close()
        _transaction_id.reset(log_token)


@contextmanager
def reader(root):
    current = _active.get()
    if current and current[0] == Path(root).resolve():
        yield current[1]
        return
    db = connect(root)
    try:
        db.execute("BEGIN")
        yield db
    finally:
        db.rollback()
        db.close()


def _collection(db, kind):
    return [json.loads(row[0]) for row in db.execute(
        "SELECT payload FROM entities WHERE kind=? ORDER BY position", (kind,))]


def _replace_collection(db, kind, values, key):
    if not isinstance(values, list):
        raise ValueError(f"{kind} must be an array")
    ids = [str(item[key]) if key else str(pos) for pos, item in enumerate(values)]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate {kind} identity")
    removed = {row[0] for row in db.execute("SELECT id FROM entities WHERE kind=?", (kind,))} - set(ids)
    db.executemany("DELETE FROM entities WHERE kind=? AND id=?", [(kind, identity) for identity in removed])
    db.executemany("""INSERT INTO entities VALUES(?,?,?,?,?)
        ON CONFLICT(kind,id) DO UPDATE SET position=excluded.position,status=excluded.status,payload=excluded.payload
        WHERE position!=excluded.position OR status IS NOT excluded.status OR payload!=excluded.payload""", [
        (kind, identity, pos, item.get("status"), encode(item))
        for pos, (identity, item) in enumerate(zip(ids, values))])


def _read(db, address):
    if address == "PRODUCT_STATE.json":
        row = db.execute("SELECT payload FROM product WHERE id=1").fetchone()
        if row is None:
            raise FileNotFoundError("product state is not initialized")
        value = json.loads(row[0])
        for kind in COLLECTIONS:
            value[kind] = _collection(db, kind)
        if "identity_lockset" in value:
            value["identity_lockset"]["locks"] = _collection(db, "identity_locks")
        value["visual_sets"] = [
            {k: item[k] for k in ("set_id", "marketplace", "status", "plan_revision", "plan_path", "next_action") if k in item}
            | {"state_path": f"visual_sets/{item['set_id']}/SET_STATE.json"}
            for (payload,) in db.execute("SELECT payload FROM sets ORDER BY rowid")
            for item in [json.loads(payload)]]
        return value
    if address.startswith("visual_sets/") and address.endswith("/SET_STATE.json"):
        set_id = address.split("/")[1]
        row = db.execute("SELECT payload FROM sets WHERE id=?", (set_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"missing set: {set_id}")
        value = json.loads(row[0])
        value["modules"] = [json.loads(x[0]) for x in db.execute(
            "SELECT payload FROM modules WHERE set_id=? ORDER BY position", (set_id,))]
        return value
    row = db.execute("SELECT payload FROM records WHERE address=?", (address,)).fetchone()
    if row is None:
        raise FileNotFoundError(f"missing database record: {address}")
    return json.loads(row[0])


def _write(db, address, value, text=None):
    if not isinstance(value, dict):
        raise ValueError(f"{address} must contain a JSON object")
    if address == "PRODUCT_STATE.json":
        body = {k: v for k, v in value.items() if k not in {*COLLECTIONS, "visual_sets"}}
        for kind, key in COLLECTIONS.items():
            _replace_collection(db, kind, value.get(kind, []), key)
        if "identity_lockset" in body:
            lockset = dict(body["identity_lockset"])
            _replace_collection(db, "identity_locks", lockset.pop("locks", []), "lock_id")
            body["identity_lockset"] = lockset
        db.execute("INSERT INTO product VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload WHERE payload!=excluded.payload", (encode(body),))
    elif address.startswith("visual_sets/") and address.endswith("/SET_STATE.json"):
        set_id = address.split("/")[1]
        if value.get("set_id") != set_id:
            raise ValueError("set state identity differs from record address")
        body = {k: v for k, v in value.items() if k != "modules"}
        db.execute("INSERT INTO sets VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload WHERE payload!=excluded.payload", (set_id, encode(body)))
        ids = [item["module_id"] for item in value.get("modules", [])]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate module identity")
        removed = {row[0] for row in db.execute("SELECT id FROM modules WHERE set_id=?", (set_id,))} - set(ids)
        db.executemany("DELETE FROM modules WHERE set_id=? AND id=?", [(set_id, identity) for identity in removed])
        db.executemany("""INSERT INTO modules VALUES(?,?,?,?,?)
            ON CONFLICT(set_id,id) DO UPDATE SET position=excluded.position,status=excluded.status,payload=excluded.payload
            WHERE position!=excluded.position OR status!=excluded.status OR payload!=excluded.payload""", [
            (set_id, item["module_id"], pos, item.get("status", "PLANNED"), encode(item))
            for pos, item in enumerate(value.get("modules", []))])
    else:
        kind = "review" if address.startswith("qa/visual/") else "contract" if address.startswith("runs/") else "plan"
        db.execute("INSERT INTO records VALUES(?,?,?) ON CONFLICT(address) DO UPDATE SET payload=excluded.payload WHERE payload!=excluded.payload",
                   (address, kind, text if text is not None else encode(value)))
    workflow = value.get("workflow")
    status = value.get("status") or (workflow.get("status") if isinstance(workflow, dict) else None)
    log_event(_active.get()[0] if _active.get() else None, "record.written", address=address,
              status=status,
              **{key: value[key] for key in ("module_id", "candidate_id", "run_id", "set_id") if key in value})


def read_json(path):
    where = location(path)
    if where:
        with reader(where[0]) as db:
            return _read(db, where[1])
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path, value):
    where = location(path)
    if where:
        if not (where[0] / DATABASE).exists() and (where[0] / "PRODUCT_STATE.json").exists():
            raise ValueError("legacy JSON project; run project_records.py migrate before writing")
        with transaction(where[0], create=True) as db:
            _write(db, where[1], value)
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(encode(value), encoding="utf-8")
    temporary.replace(path)


def exists(path):
    where = location(path)
    if not where:
        return Path(path).exists()
    if not (where[0] / DATABASE).is_file():
        return False
    try:
        with reader(where[0]) as db:
            _read(db, where[1])
        return True
    except FileNotFoundError:
        return False


def is_file(path):
    return exists(path) if location(path) else Path(path).is_file()


def read_bytes(path):
    where = location(path)
    if not where:
        return Path(path).read_bytes()
    with reader(where[0]) as db:
        if where[1] == "PRODUCT_STATE.json" or where[1].endswith("/SET_STATE.json"):
            return encode(_read(db, where[1])).encode("utf-8")
        row = db.execute("SELECT payload FROM records WHERE address=?", (where[1],)).fetchone()
        if row is None:
            raise FileNotFoundError(f"missing database record: {where[1]}")
        return row[0].encode("utf-8")


def digest(path):
    if location(path):
        return hashlib.sha256(read_bytes(path)).hexdigest()
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def claim_generation(root, contract_address, candidate_id):
    """Commit task ownership before returning instructions for an external tool."""
    with transaction(root) as db:
        contract_hash = digest(Path(root) / contract_address)
        old = db.execute("SELECT token,status,contract_sha256 FROM generation_claims WHERE candidate_id=?", (candidate_id,)).fetchone()
        if old:
            raise ValueError("candidate already claimed; inspect/recover the existing attempt instead of generating again")
        token = uuid.uuid4().hex
        db.execute("INSERT INTO generation_claims(candidate_id,token,contract_address,contract_sha256,status) VALUES(?,?,?,?, 'RUNNING')",
                   (candidate_id, token, contract_address, contract_hash))
        log_event(root, "generation.claimed", candidate_id=candidate_id, contract_address=contract_address,
                  contract_sha256=contract_hash, status="RUNNING")
        return token


def finish_claim(root, candidate_id, status, token=None, reason=None):
    with transaction(root) as db:
        old = db.execute("SELECT token,status FROM generation_claims WHERE candidate_id=?", (candidate_id,)).fetchone()
        if old is None:
            return  # Imported/standalone candidates may predate task claims.
        if old[1] == status:
            return
        if old[1] != "RUNNING" or token != old[0]:
            raise ValueError("active generation claim requires its claim token")
        address, expected = db.execute("SELECT contract_address,contract_sha256 FROM generation_claims WHERE candidate_id=?", (candidate_id,)).fetchone()
        if digest(Path(root) / address) != expected:
            raise ValueError("claimed contract changed; recover its original binding before recording")
        db.execute("UPDATE generation_claims SET status=?,reason=?,updated_at=CURRENT_TIMESTAMP WHERE candidate_id=?",
                   (status, reason, candidate_id))
        log_event(root, "generation.finished", candidate_id=candidate_id, status=status, reason=reason)


def get_claim(root, candidate_id):
    with reader(root) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM generation_claims WHERE candidate_id=?", (candidate_id,)).fetchone()
        return dict(row) if row else None


def recover_generation(root, contract_address, token, reason):
    """Resolve an explicitly interrupted external call; never infer remote failure."""
    root = Path(root).resolve()
    if not reason or not reason.strip():
        raise ValueError("recovery needs the actual interruption/failure reason")
    with transaction(root):
        contract = read_json(root / contract_address)
        candidate_id = contract["candidate_id"]
        claim = get_claim(root, candidate_id)
        if not claim or claim["status"] != "RUNNING":
            raise ValueError("no interrupted active generation to recover")
        output = (root / contract["output_path"]).resolve()
        output.relative_to(root)
        raw = output.with_name(output.stem + ".raw.png")
        if output.is_file() or raw.is_file():
            finish_claim(root, candidate_id, "OUTPUT_SAVED", token, reason)
            return {"candidate_id": candidate_id, "next_action": "REVIEW_CURRENT_IMAGE" if output.is_file() else "RESUME_POSTPROCESS"}
        finish_claim(root, candidate_id, "FAILED", token, reason)
        product = read_json(root / "PRODUCT_STATE.json")
        product["candidates"].append({"candidate_id": candidate_id, "run_id": contract["run_id"],
                                      "source_contract": contract_address, "path": contract["output_path"],
                                      "status": "REJECTED_TOOL", "failure_code": "TOOL_ERROR", "failure_reason": reason})
        product.setdefault("decision_log", []).append({"action": "GENERATION_FAILED", "candidate_id": candidate_id, "reason": reason})
        for run in product.get("runs", []):
            if run.get("run_id") == contract["run_id"]:
                run["status"] = "REJECTED_TOOL"
        product.setdefault("workflow", {}).update(status="GENERATION_FAILED", next_action="PREPARE_EXPLICIT_RETRY")
        write_json(root / "PRODUCT_STATE.json", product)
        return {"candidate_id": candidate_id, "next_action": "PREPARE_EXPLICIT_RETRY"}
