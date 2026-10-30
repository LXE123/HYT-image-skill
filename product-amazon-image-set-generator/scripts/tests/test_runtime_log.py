"""Runtime diagnostics survive failed business operations without changing them."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parents[1] / "product-single-image-generator/scripts"))
from project_store import DATABASE, read_json, transaction, write_json
import runtime_log
import test_quality_workflow as fixtures


class RuntimeLogTest(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.ReferencedWorkflowTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def events(self, fixture, **filters):
        return runtime_log.read_events(fixture.root, last=2000, **filters)["events"]

    def test_rollback_log_survives_and_keeps_original_traceback(self):
        f = self.fixture()
        path = f.root / "PRODUCT_STATE.json"
        before = read_json(path)
        with self.assertRaisesRegex(RuntimeError, "injected failure"):
            with transaction(f.root):
                value = read_json(path)
                value["sku"] = "never committed"
                write_json(path, value)
                raise RuntimeError("injected failure after state update")
        self.assertEqual(read_json(path), before)
        failure = [e for e in self.events(f) if e["event"] == "transaction.rolled_back"][-1]
        self.assertEqual(failure["error_type"], "RuntimeError")
        self.assertIn("test_rollback_log_survives", failure["traceback"])
        self.assertEqual(failure["phase"], "body")
        self.assertFalse(any(e["event"] == "transaction.committed" and e.get("transaction_id") == failure["transaction_id"] for e in self.events(f)))

    def test_caught_failure_has_operation_ids_and_details(self):
        f = self.fixture()
        f.prepare_approved_set()
        response = f.run_script(SCRIPTS, "set_runtime.py", "--set-id", "set1", "packet", "--module-id", "gallery-01", "--max-bytes", "512", success=False)
        failure = [e for e in self.events(f) if e["event"] == "operation.error" and e.get("command") == "set_runtime.py"][-1]
        self.assertIn("response exceeds", failure["message"])
        self.assertIn("set_runtime.py", failure["traceback"])
        self.assertEqual(failure["module_id"], "gallery-01")
        self.assertEqual(failure["set_id"], "set1")
        self.assertEqual(failure["action"], "packet")
        self.assertIn(failure["operation_id"], response.stderr)

    def test_subprocesses_are_linked_to_the_parent_operation(self):
        f = self.fixture()
        f.prepare_approved_set()
        response = f.run_script(SCRIPTS, "set_runtime.py", "--set-id", "set1", "prepare")
        self.assertEqual(json.loads(response.stdout)["phase"], "generation")
        events = self.events(f)
        parent = [e for e in events if e["event"] == "operation.started" and e.get("command") == "set_runtime.py" and e.get("action") == "prepare"][-1]
        children = [e for e in events if e.get("parent_operation_id") == parent["operation_id"] and e["event"] == "operation.started"]
        self.assertTrue(children)
        self.assertTrue(any(e["command"] == "validate_run_records.py" for e in children))
        self.assertTrue(any(e["event"] == "subprocess.finished" and e.get("operation_id") == parent["operation_id"] for e in events))

    def test_stdout_protocol_is_unchanged_and_private_inputs_are_not_logged(self):
        f = self.fixture()
        argv = ["sample.py", str(f.root), "--claim-token", "private-token", "--correction", "private-prompt"]
        output = StringIO()
        def success():
            print('{"ok":true}')
            return 0
        with patch.object(sys, "argv", argv), redirect_stdout(output):
            self.assertEqual(runtime_log.run_cli(success), 0)
        self.assertEqual(output.getvalue(), '{"ok":true}\n')
        encoded = json.dumps(self.events(f))
        self.assertNotIn("private-token", encoded)
        self.assertNotIn("private-prompt", encoded)

    def test_claim_token_is_redacted_even_in_an_exception_and_stderr(self):
        f = self.fixture()
        def failure():
            print("bad token private-token", file=sys.stderr)
            raise ValueError("rejected private-token")
        with patch.object(sys, "argv", ["sample.py", str(f.root), "--claim-token=private-token"]), redirect_stderr(StringIO()):
            with self.assertRaises(ValueError):
                runtime_log.run_cli(failure)
        encoded = json.dumps(self.events(f))
        self.assertNotIn("private-token", encoded)
        self.assertIn("[REDACTED]", encoded)

    def test_log_failure_does_not_undo_a_successful_transaction(self):
        f = self.fixture()
        path = f.root / "PRODUCT_STATE.json"
        diagnostic = StringIO()
        with patch.object(runtime_log.os, "open", side_effect=PermissionError("synthetic log write denial")), redirect_stderr(diagnostic):
            with transaction(f.root):
                value = read_json(path)
                value["sku"] = "committed despite logger error"
                write_json(path, value)
        self.assertEqual(read_json(path)["sku"], "committed despite logger error")
        self.assertIn("runtime log unavailable", diagnostic.getvalue())

    def test_diagnostics_do_not_add_requirements_to_partial_product_records(self):
        f = self.fixture()
        path = f.root / "PRODUCT_STATE.json"
        value = read_json(path)
        value["workflow"] = None
        write_json(path, value)
        self.assertIsNone(read_json(path)["workflow"])

    def test_logs_can_be_queried_when_database_is_corrupt(self):
        f = self.fixture()
        database = f.root / DATABASE
        database.write_bytes(b"synthetic broken database")
        response = f.run_script(fixtures.SINGLE, "project_records.py", "list", success=False)
        self.assertIn("database", response.stderr)
        queried = subprocess.run([sys.executable, "-B", str(fixtures.SINGLE / "runtime_log.py"), str(f.root), "--level", "ERROR"], capture_output=True, text=True)
        self.assertEqual(queried.returncode, 0, queried.stderr)
        result = json.loads(queried.stdout)
        self.assertTrue(any(e["event"] == "operation.error" and "database" in e["message"] for e in result["events"]))
        self.assertEqual(database.read_bytes(), b"synthetic broken database")

    def test_query_filters_and_partial_tail_do_not_hide_valid_events(self):
        f = self.fixture()
        path = runtime_log.log_event(f.root, "test.first", module_id="a")
        with path.open("ab") as stream:
            stream.write(b'{"partial":\xff\n')
        runtime_log.log_event(f.root, "test.second", "ERROR", module_id="b")
        result = runtime_log.read_events(f.root, last=1, module_id="b", level="ERROR")
        self.assertEqual(result["events"][0]["event"], "test.second")
        self.assertEqual(result["malformed_lines"], 1)


if __name__ == "__main__":
    unittest.main()
