"""SQLite transaction, migration and interrupted generation behaviour.

All image bytes are synthetic; these tests establish state correctness only.
"""

import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import set_runtime
from project_store import DATABASE, digest, get_claim, read_json, transaction, write_json
from project_records import editable_put, export_snapshot, migrate
import test_quality_workflow as fixtures
from context_store import load_contract


class ProjectStoreTest(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.ReferencedWorkflowTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def runtime(self, fixture, action, *args, success=True):
        response = fixture.run_script(SCRIPTS, "set_runtime.py", "--set-id", "set1", action, *args, success=success)
        return json.loads(response.stdout) if success else response

    def test_multi_record_error_rolls_back_and_creates_no_state_json(self):
        f = self.fixture()
        f.prepare_approved_set()
        state_path = f.root / "PRODUCT_STATE.json"
        set_path = f.root / "visual_sets/set1/SET_STATE.json"
        before = (read_json(state_path), read_json(set_path))
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with transaction(f.root):
                state = read_json(state_path)
                state["workflow"]["status"] = "TEST_CHANGED"
                write_json(state_path, state)
                current = read_json(set_path)
                current["status"] = "COMPLETE"
                write_json(set_path, current)
                raise RuntimeError("interrupted before commit")
        self.assertEqual((read_json(state_path), read_json(set_path)), before)
        self.assertTrue((f.root / DATABASE).is_file())
        self.assertFalse(state_path.is_file())
        self.assertFalse(set_path.is_file())
        self.assertFalse((f.root / "visual_sets/set1/SET_PLAN.json").is_file())

    def test_second_writer_reads_only_after_first_writer_commits(self):
        f = self.fixture()
        path = f.root / "PRODUCT_STATE.json"
        code = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from project_store import transaction, read_json, write_json
root=Path(sys.argv[2])
print('ready', flush=True)
with transaction(root):
    path=root/'PRODUCT_STATE.json'
    value=read_json(path)
    value['counter'] += 1
    write_json(path,value)
"""
        with transaction(f.root):
            child = subprocess.Popen([sys.executable, "-B", "-c", code, str(set_runtime.SINGLE), str(f.root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.addCleanup(lambda: child.kill() if child.poll() is None else None)
            self.assertEqual(child.stdout.readline().strip(), "ready")
            state = read_json(path)
            state["counter"] = 10
            write_json(path, state)
        _, error = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, error)
        self.assertEqual(read_json(path)["counter"], 11)

    def test_claim_serializes_ownership_and_wrong_token_cannot_record(self):
        f = self.fixture()
        f.prepare_approved_set()
        packet = self.runtime(f, "prepare")
        claimed = self.runtime(f, "claim", "--module-id", packet["module_id"])
        self.assertIn("claim_token", claimed)
        self.runtime(f, "claim", "--module-id", packet["module_id"], success=False)
        status = self.runtime(f, "next")
        self.assertEqual(status["current"]["status"], "GENERATING")
        self.assertEqual(status["next_action"], "WAIT_OR_RECOVER_GENERATION")
        image = Path(packet["output_path"])
        image.write_bytes(b"saved image before interruption")
        before = read_json(f.root / "PRODUCT_STATE.json")
        self.runtime(f, "record", "--module-id", packet["module_id"], "--decision", "PENDING_REVIEW", "--claim-token", "wrong", success=False)
        self.assertEqual(read_json(f.root / "PRODUCT_STATE.json"), before)
        self.runtime(f, "record", "--module-id", packet["module_id"], "--decision", "PENDING_REVIEW", "--claim-token", claimed["claim_token"])
        self.assertEqual(get_claim(f.root, packet["candidate_id"])["status"], "OUTPUT_SAVED")
        self.assertEqual(self.runtime(f, "next")["current"]["status"], "REVIEW_REQUIRED")

    def test_record_and_set_projection_roll_back_together(self):
        f = self.fixture()
        f.prepare_approved_set()
        packet = self.runtime(f, "prepare")
        Path(packet["output_path"]).write_bytes(b"synthetic saved image")
        state_path = f.root / "PRODUCT_STATE.json"
        set_path = f.root / "visual_sets/set1/SET_STATE.json"
        before = (read_json(state_path), read_json(set_path))
        argv = ["set_runtime.py", str(f.root), "--set-id", "set1", "record", "--module-id", packet["module_id"], "--decision", "PENDING_REVIEW"]
        with patch.object(sys, "argv", argv), patch.object(set_runtime, "synchronize", side_effect=ValueError("injected sync failure")):
            self.assertEqual(set_runtime.main(), 1)
        self.assertEqual((read_json(state_path), read_json(set_path)), before)
        self.assertTrue(Path(packet["output_path"]).is_file())

    def test_failed_generation_requires_explicit_recovery_and_new_attempt(self):
        f = self.fixture()
        f.prepare_approved_set()
        packet = self.runtime(f, "prepare")
        claimed = self.runtime(f, "claim", "--module-id", packet["module_id"])
        self.runtime(f, "prepare", "--module-id", packet["module_id"], success=False)
        self.runtime(f, "recover", "--module-id", packet["module_id"], "--claim-token", claimed["claim_token"], "--reason", "Generator reported a failed request")
        self.assertEqual(get_claim(f.root, packet["candidate_id"])["status"], "FAILED")
        replacement = self.runtime(f, "prepare", "--module-id", packet["module_id"], "--retry", "--correction", "Retry the same evidenced task after tool failure")
        self.assertEqual(replacement["attempt"], 2)
        self.assertNotEqual(replacement["candidate_id"], packet["candidate_id"])

    def test_saved_output_recovery_does_not_regenerate_or_accept(self):
        f = self.fixture()
        f.prepare_approved_set()
        packet = self.runtime(f, "prepare")
        claimed = self.runtime(f, "claim", "--module-id", packet["module_id"])
        image = Path(packet["output_path"])
        image.write_bytes(b"saved before connection loss")
        result = self.runtime(f, "recover", "--module-id", packet["module_id"], "--claim-token", claimed["claim_token"], "--reason", "Output found after restart")
        self.assertEqual(result["next_action"], "REVIEW_CURRENT_IMAGE")
        self.assertEqual(self.runtime(f, "prepare")["phase"], "review")
        self.assertEqual(read_json(f.root / "PRODUCT_STATE.json")["candidates"], [])

    def test_oversize_claim_packet_does_not_leave_a_claim(self):
        f = self.fixture()
        f.prepare_approved_set()
        packet = self.runtime(f, "prepare")
        self.runtime(f, "claim", "--module-id", packet["module_id"], "--max-bytes", "512", success=False)
        self.assertIsNone(get_claim(f.root, packet["candidate_id"]))

    def test_migration_preserves_approved_bindings_and_archives_old_files(self):
        f = self.fixture()
        row, _, _ = f.accepted_fixture()
        f.attach_passing_report_fixture(row)
        self.assertEqual(f.sync()["status"], "COMPLETE")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "legacy"
            export_snapshot(f.root, target)
            (target / "index.json").write_bytes((f.root / "index.json").read_bytes())
            for folder in ("input", "candidates", "qa/identity_anchors"):
                shutil.copytree(f.root / folder, target / folder, dirs_exist_ok=True)
            plan = target / "visual_sets/set1/SET_PLAN.json"
            import hashlib
            expected = hashlib.sha256(plan.read_bytes()).hexdigest()
            result = migrate(target)
            self.assertGreater(result["imported_records"], 3)
            self.assertEqual(digest(plan), expected)
            self.assertEqual(read_json(plan), read_json(f.root / "visual_sets/set1/SET_PLAN.json"))
            self.assertFalse(plan.is_file())
            self.assertTrue((target / "legacy_runtime/visual_sets/set1/SET_PLAN.json").is_file())
            synced = subprocess.run([sys.executable, "-B", str(SCRIPTS / "sync_set_status.py"), str(target), "--set-id", "set1"], capture_output=True, text=True)
            self.assertEqual(synced.returncode, 0, synced.stdout + synced.stderr)
            self.assertEqual(read_json(target / "visual_sets/set1/SET_STATE.json")["status"], "COMPLETE")
            self.assertEqual(read_json(target / "PRODUCT_STATE.json")["candidates"], read_json(f.root / "PRODUCT_STATE.json")["candidates"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                migrate(target)

    def test_invalid_legacy_import_leaves_originals_and_no_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, value in [("index.json", {"product_id": "p"}), ("PRODUCT_STATE.json", {"product_id": "p", "runs": [{"run_id": "x"}, {"run_id": "x"}]})]:
                (root / name).write_text(json.dumps(value))
            before = (root / "PRODUCT_STATE.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "duplicate"):
                migrate(root)
            self.assertEqual((root / "PRODUCT_STATE.json").read_bytes(), before)
            self.assertFalse((root / DATABASE).exists())

    def test_draft_edit_cannot_replace_runtime_decisions(self):
        f = self.fixture()
        path = f.root / "PRODUCT_STATE.json"
        state = read_json(path)
        state["candidates"].append({"candidate_id": "fake", "status": "ACCEPTED"})
        with self.assertRaisesRegex(ValueError, "runtime commands"):
            editable_put(f.root, path, state, digest(path))
        self.assertEqual(read_json(path)["candidates"], [])

    def test_set_summary_is_derived_and_cannot_be_overwritten_by_product_copy(self):
        f = self.fixture()
        f.prepare_approved_set()
        product_path = f.root / "PRODUCT_STATE.json"
        set_path = f.root / "visual_sets/set1/SET_STATE.json"
        stale_product = read_json(product_path)
        current = read_json(set_path)
        current["status"] = "SET_REVIEW"
        write_json(set_path, current)
        write_json(product_path, stale_product)
        self.assertEqual(read_json(product_path)["visual_sets"][0]["status"], "SET_REVIEW")

    def test_standalone_claim_and_registration_use_same_database(self):
        f = self.fixture()
        row = f.prepare_approved_set()
        resolved = load_contract(f.root, f.root / row["contract_path"])
        f.run_script(fixtures.SINGLE, "init_run_records.py", "--run-id", "standalone", "--sku", "test", "--view", "front_3q")
        address = "runs/standalone/front_3q_generation_contract.json"
        draft = read_json(f.root / address)
        resolved = {k: v for k, v in resolved.items() if k not in {"visual_set", "bindings", "storage_mode"}}
        resolved.update({key: draft[key] for key in ("run_id", "candidate_id", "output_path")})
        write_json(f.root / address, resolved)
        f.run_script(fixtures.SINGLE, "compile_generation_prompt.py", "--contract", address)
        response = f.run_script(fixtures.SINGLE, "validate_run_records.py", "--contract", address, "--ready-for-generation", "--claim")
        claim = json.loads(response.stdout.splitlines()[0])
        f.run_script(fixtures.SINGLE, "validate_run_records.py", "--contract", address, "--ready-for-generation", "--claim", success=False)
        (f.root / resolved["output_path"]).write_bytes(b"synthetic standalone image")
        f.run_script(fixtures.SINGLE, "record_candidate.py", "--contract", address, "--decision", "PENDING_REVIEW", "--claim-token", claim["claim_token"])
        saved = next(x for x in read_json(f.root / "PRODUCT_STATE.json")["candidates"] if x["candidate_id"] == claim["candidate_id"])
        self.assertEqual(saved["status"], "PENDING_REVIEW")
        self.assertEqual(get_claim(f.root, claim["candidate_id"])["status"], "OUTPUT_SAVED")

    def test_initializer_creates_database_and_resumes_without_state_file(self):
        with tempfile.TemporaryDirectory() as temp:
            script = SCRIPTS.parents[1] / "product-image-project-builder/scripts/initialize_package.py"
            command = [sys.executable, "-B", str(script), "--product-id", "db-test", "--version", "v1", "--evidence-mode", "PHOTO_EVIDENCE", "--product-scope", "PRODUCT_ONLY", "--desktop-root", temp]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            root = Path(first.stdout.strip().split("  ", 1)[1])
            self.assertTrue((root / DATABASE).is_file())
            self.assertFalse((root / "PRODUCT_STATE.json").exists())
            before = read_json(root / "PRODUCT_STATE.json")
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("RESUME", second.stdout)
            self.assertEqual(read_json(root / "PRODUCT_STATE.json"), before)


if __name__ == "__main__":
    unittest.main()
