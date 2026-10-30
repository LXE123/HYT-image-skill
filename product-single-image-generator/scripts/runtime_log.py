#!/usr/bin/env python3
"""Project runtime diagnostics, independent of database transactions."""

import argparse
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import traceback
import uuid

_operation = ContextVar("runtime_operation", default=None)
_transaction_id = ContextVar("runtime_transaction_id", default=None)
ID_OPTIONS = {"--set-id": "set_id", "--module-id": "module_id", "--run-id": "run_id",
              "--contract": "contract_address", "--address": "address", "--decision": "decision",
              "--phase": "phase", "--attempt": "attempt", "--view": "view"}


def error_details(error):
    return {"error_type": type(error).__name__, "message": str(error),
            "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__))}


def _redact(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
    elif isinstance(value, dict):
        value = {key: _redact(item, secrets) for key, item in value.items()}
    elif isinstance(value, list):
        value = [_redact(item, secrets) for item in value]
    return value


def log_event(root, event, level="INFO", **fields):
    """One append per event; logging failures must not change business outcomes."""
    context = _operation.get() or {}
    root = root or context.get("root")
    if root is None:
        return None
    root = Path(root).resolve()
    now = datetime.now(timezone.utc)
    record = {"timestamp": now.isoformat(timespec="milliseconds"), "level": level, "event": event,
              "pid": os.getpid(), **{k: v for k, v in context.items() if k not in {"root", "_redactions"}},
              **({"transaction_id": _transaction_id.get()} if _transaction_id.get() else {}), **fields}
    record = _redact(record, context.get("_redactions", []))
    path = root / "runtime" / "logs" / f"{now:%Y-%m-%d}.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            if os.write(descriptor, data) != len(data):
                raise OSError("incomplete runtime log append")
        finally:
            os.close(descriptor)
        return path
    except (OSError, TypeError, ValueError) as error:
        print(f"runtime log unavailable: {path}: {error}", file=sys.stderr)
        return None


def log_error(error, event="operation.error", root=None, **fields):
    return log_event(root, event, "ERROR", **error_details(error), **fields)


def bind_project(root):
    """Bind initialization after its path preflight, without inventing a project."""
    context = _operation.get()
    if context is not None:
        context["root"] = str(Path(root).resolve())
        log_event(root, "operation.started")


class _StderrCapture:
    def __init__(self, stream):
        self.stream = stream
        self.tail = ""

    def write(self, value):
        self.tail = (self.tail + value)[-8000:]
        return self.stream.write(value)

    def flush(self):
        return self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def run_cli(main):
    """Keep stdout protocols intact; correlate CLI, transaction and child events."""
    argv = sys.argv[1:]
    root = None
    if argv and not argv[0].startswith("-"):
        root = str(Path(argv[0]).resolve())
    elif "--package" in argv and argv.index("--package") + 1 < len(argv):
        root = str(Path(argv[argv.index("--package") + 1]).resolve())
    context = {"operation_id": uuid.uuid4().hex, "command": Path(sys.argv[0]).name}
    context["_redactions"] = [argv[index + 1] for index, value in enumerate(argv[:-1])
                              if value == "--claim-token" and argv[index + 1]]
    context["_redactions"] += [value.split("=", 1)[1] for value in argv
                               if value.startswith("--claim-token=") and value.split("=", 1)[1]]
    parent = os.environ.get("PRODUCT_RUNTIME_PARENT_ID")
    if parent:
        context["parent_operation_id"] = parent
    if root:
        context["root"] = root
    # Do not log argv, prompt/copy payloads, claim tokens, or environment values.
    for index, value in enumerate(argv[:-1]):
        if value in ID_OPTIONS:
            context[ID_OPTIONS[value]] = argv[index + 1]
    if Path(sys.argv[0]).name == "set_runtime.py":
        actions = {"status", "next", "next-generation", "module", "prepare", "packet", "record", "sync", "handoff", "claim", "recover"}
        # The action follows --set-id's value in the public CLI grammar.
        if "--set-id" in argv:
            position = argv.index("--set-id") + 2
            if position < len(argv) and argv[position] in actions:
                context["action"] = argv[position]
    token = _operation.set(context)
    started = time.monotonic()
    capture = _StderrCapture(sys.stderr)
    original_stderr = sys.stderr
    code = 1
    if root:
        log_event(root, "operation.started")
    try:
        sys.stderr = capture
        result = main()
        code = 0 if result is None else result
        return result
    except BaseException as error:
        if isinstance(error, SystemExit):
            code = 0 if error.code is None else error.code if isinstance(error.code, int) else 1
        else:
            code = 130 if isinstance(error, KeyboardInterrupt) else 1
        if code and context.get("root"):
            log_error(error)
        raise
    finally:
        sys.stderr = original_stderr
        if context.get("root"):
            path = log_event(None, "operation.finished", "ERROR" if code else "INFO", exit_code=code,
                             duration_ms=round((time.monotonic() - started) * 1000),
                             **({"stderr_tail": capture.tail} if code and capture.tail else {}))
            if code and path:
                print(f"runtime operation={context['operation_id']} log={path}", file=original_stderr)
        _operation.reset(token)


def child_environment():
    environment = os.environ.copy()
    context = _operation.get()
    if context:
        environment["PRODUCT_RUNTIME_PARENT_ID"] = context["operation_id"]
    return environment


def read_events(root, last=50, **filters):
    events = deque(maxlen=last)
    malformed = 0
    for path in sorted((Path(root) / "runtime/logs").glob("*.jsonl")):
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError("log event must be an object")
                except ValueError:
                    malformed += 1
                    continue
                if all(value is None or record.get(key) == value for key, value in filters.items()):
                    events.append(record)
    return {"events": list(events), "malformed_lines": malformed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--last", type=int, default=50)
    for name in ("operation-id", "set-id", "module-id", "candidate-id", "level"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    if args.last < 1:
        parser.error("--last must be positive")
    try:
        result = read_events(args.package, args.last, operation_id=args.operation_id, set_id=args.set_id,
                             module_id=args.module_id, candidate_id=args.candidate_id, level=args.level)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except OSError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
