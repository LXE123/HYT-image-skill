"""Regression checks for missing anatomy/state evidence and completion gates.

Uses synthetic files only; no image-generation calls or visual-quality claims.
"""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AMAZON = Path(__file__).resolve().parents[1]
SINGLE = AMAZON.parents[1] / "product-single-image-generator" / "scripts"
sys.path.insert(0, str(AMAZON))
from set_common import generation_templates, module_stub, sha256, write_json
from quality_rules import qa_errors, required_checks, validate_quality
from context_store import MODULE_KEYS, load_contract



from project_store import read_json as store_read, read_bytes as store_bytes, exists as store_exists

class QualityWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="product-quality-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        evidence = self.root / "input/product.png"
        evidence.parent.mkdir()
        evidence.write_bytes(b"synthetic evidence fixture; no real image inspection")
        self.index = {
            "product_id": "test", "version": "v1", "evidence_mode": "PHOTO_EVIDENCE",
            "product_scope": "PRODUCT_ONLY", "render_templates": [],
            "product_evidence": [{"evidence_id": "actual", "path": "input/product.png", "sha256": sha256(evidence), "structures": ["full_product", "clasp"], "observed_states": ["clasp_closed", "clasp_open"], "source_type": "REAL_PHOTO", "hard_constraint": True, "view": "front"}],
        }
        write_json(self.root / "index.json", self.index)
        self.locks = {"shape": {"lock_id": "shape", "fact": "fixture assembled structure", "affected_views": ["front_3q"], "status": "LOCKED", "anchor_id": "shape"}}
        write_json(self.root / "qa/identity_anchors/index.json", {"anchors": [{"anchor_id": "shape"}]})
        for name in ("source.png", "grayscale.png", "contour.png", "anchor.json"):
            path = self.root / "qa/identity_anchors/shape" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic anchor")
        self.state = {
            "schema_version": 2, "product_id": "test", "sku": "test",
            "reference_package": {"path": "index.json", "version": "v1", "sha256": sha256(self.root / "index.json")},
            "product_identity_baseline": {"status": "READY"},
            "identity_lockset": {"status": "READY", "version": 1, "locks": list(self.locks.values())},
            "workflow": {"status": "REFERENCE_READY"}, "candidates": [], "runs": [],
        }
        write_json(self.root / "PRODUCT_STATE.json", self.state)
        self.module = module_stub("gallery-01", "AMAZON_GALLERY", 1, "Accurate object", "What is included?", "front_3q", "1:1", "white")
        self.module["execution_policy"] = {'mode': 'ADVANCED', 'reason': 'Synthetic task has clear requirements and registered coverage', 'requirements': 'CLEAR', 'evidence': 'SUFFICIENT', 'readiness': 'READY', 'allowed_completion': ['composition']}
        self.module["creative_brief"] = {
            "layout_id": "main_clean", "story_stage": "single_message",
            "visual_concept": "Recognize the complete sellable silhouette immediately",
            "visual_device": "An evidenced three-quarter view with controlled material highlights",
            "information_hierarchy": ["complete product silhouette", "true material and interface detail"],
            "graphic_treatment": "Pure white main-image background, no copy or graphic overlays",
            "set_role": "Primary identification before secondary feature explanation",
            "success_criteria": ["clear silhouette at listing size", "material readable without clutter"],
        }
        self.module["required_lock_ids"] = ["shape"]
        self.module["product_references"] = [{"path": "input/product.png", "role": "PRODUCT_EVIDENCE", "usage_scope": "PRODUCT_IDENTITY_ONLY"}]

    def run_script(self, directory, name, *args, success=True):
        result = subprocess.run([sys.executable, str(directory / name), str(self.root), *args], capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def check(self, module=None):
        return validate_quality(self.root, module or self.module, self.index, self.locks)

    def human_module(self):
        module = copy.deepcopy(self.module)
        module["generation_template"] = generation_templates()["lifestyle_simple"]
        module["quality_contract"]["human"] = {
            "present": True, "pose_description": "Left shoulder-elbow-wrist-hand continuous; right arm outside frame",
            "visible_limbs": ["left arm and hand"], "contact_points": ["strap outside wrist"], "occlusion_order": ["forearm in front of torso"],
        }
        return module

    def hardware_module(self):
        module = copy.deepcopy(self.module)
        module["generation_template"] = generation_templates()["hardware_static"]
        module["quality_contract"]["visible_hardware"] = ["clasp"]
        module["quality_contract"]["structure_checks"] = [{"structure_id": "clasp", "lock_ids": ["shape"], "evidence_paths": ["input/product.png"], "expected_state": "clasp_closed", "visible_checks": ["same count, routing and surfaces"]}]
        return module

    def test_main_template_is_valid_with_complete_source(self):
        self.assertEqual(self.check(), [])

    def test_human_requires_ownership_contact_and_occlusion(self):
        module = self.human_module()
        self.assertEqual(self.check(module), [])
        del module["quality_contract"]["human"]["occlusion_order"]
        self.assertTrue(any("occlusion_order" in x for x in self.check(module)))

    def test_human_template_cannot_opt_out_of_anatomy(self):
        module = self.human_module()
        module["quality_contract"]["human"]["present"] = False
        self.assertTrue(self.check(module))

    def test_hardware_on_lifestyle_still_needs_a_check(self):
        module = self.human_module()
        module["quality_contract"]["visible_hardware"] = ["clasp"]
        self.assertTrue(any("own structure check" in x for x in self.check(module)))

    def test_state_cannot_be_invented(self):
        module = self.hardware_module()
        self.assertEqual(self.check(module), [])
        module["quality_contract"]["structure_checks"][0]["expected_state"] = "invented_hinged_cover"
        self.assertTrue(any("observed-state" in x for x in self.check(module)))

    def test_different_structure_is_not_covered_by_clasp_photo(self):
        module = self.hardware_module()
        module["quality_contract"]["structure_checks"][0]["structure_id"] = "device_connector"
        self.assertTrue(any("does not cover structure" in x for x in self.check(module)))

    def test_unregistered_reference_is_not_product_truth(self):
        self.module["product_references"][0]["path"] = "input/generated.png"
        self.assertTrue(any("unregistered" in x for x in self.check()))

    def test_changed_original_is_blocked(self):
        (self.root / "input/product.png").write_bytes(b"changed fixture")
        self.assertTrue(any("hash changed" in x for x in self.check()))

    def test_operation_requires_both_states(self):
        module = self.hardware_module()
        module["generation_template"] = generation_templates()["mechanism_steps"]
        module["claim_ids"] = ["operation"]
        module["quality_contract"]["mechanism"] = {"depicted": True, "structure_id": "clasp", "action": "verified operation in fixture", "start_state": "clasp_closed", "end_state": "clasp_open", "evidence_paths": ["input/product.png"], "verified_claim_ids": ["operation"]}
        self.assertEqual(self.check(module), [])
        self.index["product_evidence"][0]["observed_states"] = ["clasp_closed"]
        self.assertTrue(any("end_state" in x for x in self.check(module)))

    def prepare_approved_set(self):
        self.run_script(AMAZON, "init_visual_set.py", "--set-id", "set1", "--gallery-count", "1", "--a-plus-count", "0")
        plan_path = self.root / "visual_sets/set1/SET_PLAN.json"
        plan = store_read(plan_path)
        plan.update({"positioning": "Accurate object", "audience": {"primary": "buyers", "motivation": "inspect product"}, "selling_points": {"s_tier": ["accurate view"], "a_tier": [], "b_tier": []}, "visual_system": {"direction": "clean", "palette": ["pink"], "lighting": "soft", "composition": "one product", "retouching": "preserve detail", "forbidden_cues": ["extra parts"]}})
        plan["design_system"] = {"style_id": "precision_tech", "narrative_framework_id": "DIRECT", "rationale": "Synthetic fixture: clear identification of the requested object"}
        if getattr(self, "referenced", False):
            row = plan["modules"][0]
            row.update({k: self.module[k] for k in MODULE_KEYS})
            write_json(self.root / row["spec_path"], {k: v for k, v in self.module.items() if k not in {*MODULE_KEYS[1:], "generation_template"}})
        else:
            plan.update({"schema_version": 1, "modules": [self.module]})
        write_json(plan_path, plan)
        self.run_script(AMAZON, "validate_set_plan.py", "--set-id", "set1", "--approve")
        self.run_script(AMAZON, "materialize_module_contracts.py", "--set-id", "set1")
        set_state = store_read(self.root / "visual_sets/set1/SET_STATE.json")
        record = set_state["modules"][0]
        self.run_script(SINGLE, "init_run_records.py", "--run-id", record["run_id"], "--sku", "test", "--view", "front_3q")
        self.run_script(SINGLE, "validate_run_records.py", "--contract", record["contract_path"], "--ready-for-generation")
        return record

    def accepted_fixture(self):
        record = self.prepare_approved_set()
        contract_path = self.root / record["contract_path"]
        contract = store_read(contract_path)
        image = self.root / contract["output_path"]
        image.write_bytes(b"synthetic candidate fixture; not a real visual pass")
        candidate = {"candidate_id": contract["candidate_id"], "path": contract["output_path"], "sha256": sha256(image), "source_contract": record["contract_path"], "status": "ACCEPTED"}
        state = store_read(self.root / "PRODUCT_STATE.json")
        state["candidates"] = [candidate]
        write_json(self.root / "PRODUCT_STATE.json", state)
        return record, contract, candidate

    def sync(self):
        self.run_script(AMAZON, "sync_set_status.py", "--set-id", "set1")
        return store_read(self.root / "visual_sets/set1/SET_STATE.json")

    def attach_passing_report_fixture(self, record):
        report_relative = "qa/visual/candidate.json"
        self.run_script(SINGLE, "candidate_qa.py", "--contract", record["contract_path"], "--report", report_relative, "--init")
        report_path = self.root / report_relative
        report = store_read(report_path)
        report["reviewer"] = "synthetic regression fixture (not visual inspection of a real image)"
        for check in report["checks"].values():
            check.update({"status": "PASS", "observation": "synthetic recorded result used to exercise gate"})
        report["composition"].update({"annotation_method": "ASSISTANT_VISUAL_ESTIMATE", "boundary_certainty": "CLEAR",
                                      "required_content": "COMPLETE", "product_regions": [{"label": "synthetic product", "box": [.1,.1,.9,.9]}]})
        write_json(report_path, report)
        self.run_script(SINGLE, "candidate_qa.py", "--contract", record["contract_path"], "--report", report_relative)
        state = store_read(self.root / "PRODUCT_STATE.json")
        state["candidates"][0]["checks"] = {"visual": {"report_path": report_relative}}
        write_json(self.root / "PRODUCT_STATE.json", state)
        return report_path

    def test_acceptance_without_qa_cannot_complete_set(self):
        self.accepted_fixture()
        self.assertEqual(self.sync()["status"], "BLOCKED")

    def test_review_packet_reuses_linked_report_without_writing_or_accepting(self):
        record, _, _ = self.accepted_fixture()
        self.attach_passing_report_fixture(record)
        before = {p: store_bytes(p) for p in self.root.rglob('*') if p.is_file()}
        result = self.run_script(AMAZON, "set_runtime.py", "--set-id", "set1", "packet", "--module-id", "gallery-01", "--phase", "review")
        packet = json.loads(result.stdout)
        self.assertEqual(packet['review']['execution'], 'REUSE')
        self.assertEqual(packet['review']['status'], 'PASS')
        self.assertEqual(packet['review']['report_path'], 'qa/visual/candidate.json')
        self.assertEqual(before, {p: store_bytes(p) for p in self.root.rglob('*') if p.is_file()})

    def test_complete_report_then_changed_image(self):
        record, contract, candidate = self.accepted_fixture()
        self.attach_passing_report_fixture(record)
        self.assertEqual(self.sync()["status"], "COMPLETE")
        image = self.root / candidate["path"]
        image.write_bytes(b"replacement image")
        state = store_read(self.root / "PRODUCT_STATE.json")
        state["candidates"][0]["sha256"] = sha256(image)
        write_json(self.root / "PRODUCT_STATE.json", state)
        self.assertEqual(self.sync()["status"], "BLOCKED")

    def test_missing_module_state_cannot_complete_set(self):
        record, _, _ = self.accepted_fixture()
        self.attach_passing_report_fixture(record)
        state_path = self.root / "visual_sets/set1/SET_STATE.json"
        set_state = store_read(state_path)
        set_state["modules"] = []
        write_json(state_path, set_state)
        synced = self.sync()
        self.assertNotEqual(synced["status"], "COMPLETE")
        self.assertEqual(len(synced["modules"]), 1)

    def test_failure_record_blocks_completion(self):
        record, _, _ = self.accepted_fixture()
        path = self.attach_passing_report_fixture(record)
        report = store_read(path)
        report["checks"]["structure_topology"] = {"status": "FAIL", "observation": "wrong connector"}
        write_json(path, report)
        self.assertEqual(self.sync()["status"], "BLOCKED")

    def test_draft_qa_is_not_a_visual_pass(self):
        record, _, _ = self.accepted_fixture()
        self.run_script(SINGLE, "candidate_qa.py", "--contract", record["contract_path"], "--report", "qa/visual/draft.json", "--init")
        self.run_script(SINGLE, "candidate_qa.py", "--contract", record["contract_path"], "--report", "qa/visual/draft.json", success=False)

    def test_standalone_prompt_compiler_and_immutable_candidate(self):
        self.run_script(SINGLE, "init_run_records.py", "--run-id", "single", "--sku", "test", "--view", "front_3q")
        relative = "runs/single/front_3q_generation_contract.json"
        path = self.root / relative
        contract = store_read(path)
        contract["execution_policy"] = copy.deepcopy(self.module["execution_policy"])
        contract.update({"identity_lockset_version": 1, "required_lock_ids": ["shape"], "references": self.module["product_references"], "generation_template": self.module["generation_template"], "quality_contract": self.module["quality_contract"]})
        contract.update({"image_intent": {"sales_task": "Identify the complete sellable product", "buyer_question": "What is included?"}, "creative_brief": copy.deepcopy(self.module["creative_brief"]), "visual_system": {"direction": "Accurate white-background main image", "lighting": "Controlled highlights reveal the actual surface", "typography": "No added lettering"}})
        write_json(path, contract)
        self.run_script(SINGLE, "compile_generation_prompt.py", "--contract", relative)
        self.run_script(SINGLE, "validate_run_records.py", "--contract", relative, "--ready-for-generation")
        compiled = store_read(path)
        self.assertIn("fixture assembled structure", compiled["generation_prompt"])
        self.assertIn("What is included?", compiled["generation_prompt"])
        self.assertIn(contract["creative_brief"]["visual_device"], compiled["generation_prompt"])
        self.assertTrue({"design_quality", "content_coverage"}.issubset(required_checks(compiled)))
        self.assertNotIn("Art direction:", compiled["generation_prompt"])
        (self.root / contract["output_path"]).write_bytes(b"candidate now exists")
        self.run_script(SINGLE, "compile_generation_prompt.py", "--contract", relative, success=False)

    def test_new_standalone_blocks_missing_design_before_tool_prompt(self):
        self.run_script(SINGLE, "init_run_records.py", "--run-id", "no-design", "--sku", "test", "--view", "front_3q")
        relative = "runs/no-design/front_3q_generation_contract.json"
        path = self.root / relative
        contract = store_read(path)
        contract["execution_policy"] = copy.deepcopy(self.module["execution_policy"])
        contract.update({"identity_lockset_version": 1, "required_lock_ids": ["shape"], "references": self.module["product_references"], "generation_template": self.module["generation_template"], "quality_contract": self.module["quality_contract"]})
        del contract["creative_brief"]
        write_json(path, contract)
        result = self.run_script(SINGLE, "compile_generation_prompt.py", "--contract", relative, success=False)
        self.assertIn("creative_brief", result.stderr)
        self.assertIn("image_intent", result.stderr)
        self.assertIn("visual_system", result.stderr)
        self.assertNotIn("generation_prompt", store_read(path))
        self.assertTrue({"design_quality", "content_coverage"}.issubset(required_checks(contract)))

    def test_non_main_art_direction_reaches_both_prompt_formats(self):
        from quality_rules import compile_prompt
        contract = self.human_module()
        contract.update({"target_view": "lifestyle", "references": self.module["product_references"], "output_requirements": {"format": "PNG"}, "visual_system": {"direction": "Quiet environmental portrait", "lighting": "One motivated side-light", "typography": "Small supporting caption"}})
        contract["creative_brief"]["visual_device"] = "Foreground depth separates the worn product from the environment"
        for fmt in (None, "focused-v1"):
            with self.subTest(prompt_format=fmt):
                contract["prompt_format"] = fmt
                prompt = compile_prompt(contract)
                self.assertIn(contract["creative_brief"]["visual_device"], prompt)
                self.assertIn("One motivated side-light", prompt)
                self.assertIn("Art direction:", prompt)

    def test_a_plus_canvas_precedes_creative_rules_in_both_prompt_formats(self):
        from quality_rules import compile_prompt
        contract = self.human_module()
        contract.update({"target_view": "lifestyle", "references": self.module["product_references"],
                         "output_requirements": {"format": "PNG", "width_px": 1464, "height_px": 600,
                                                 "aspect_ratio": "1464:600", "postprocess": "CODE_CROP_RESIZE"}})
        a_plus_output = dict(contract["output_requirements"])
        for fmt in (None, "focused-v1"):
            contract["output_requirements"] = dict(a_plus_output)
            for template_id in ("lifestyle", "main_product"):
                with self.subTest(prompt_format=fmt, template=template_id):
                    contract["prompt_format"] = fmt
                    contract["generation_template"]["template_id"] = template_id
                    prompt = compile_prompt(contract)
                    canvas = prompt.splitlines()[0]
                    self.assertIn("2.44:1", canvas)
                    self.assertIn("1464:600", canvas)
                    self.assertLess(prompt.index(canvas), prompt.index("Template"))
                    self.assertIn(contract["creative_brief"]["visual_device"], prompt)
            contract["output_requirements"] = {"format": "PNG", "aspect_ratio": "1:1"}
            self.assertNotIn("Canvas: 2.44:1", compile_prompt(contract))

    def test_corrupted_prompt_is_blocked_at_preflight(self):
        record = self.prepare_approved_set()
        path = self.root / record["contract_path"]
        contract = store_read(path)
        contract["generation_prompt"] = "invent a different clasp"
        write_json(path, contract)
        self.run_script(SINGLE, "validate_run_records.py", "--contract", record["contract_path"], "--ready-for-generation", success=False)

    def test_human_qa_requires_specific_anatomy_result(self):
        contract = self.human_module()
        contract["candidate_id"] = "human-fixture"
        path = self.root / "human-contract.json"
        write_json(path, contract)
        candidate = {"path": "input/product.png", "candidate_id": "human-fixture"}
        report = {"candidate_id": "human-fixture", "candidate_sha256": sha256(self.root / candidate["path"]), "contract_sha256": sha256(path), "reviewer": "synthetic fixture", "inspection_method": "VISUAL_INSPECTION", "unresolved_items": [], "checks": {key: {"status": "PASS", "observation": "fixture"} for key in required_checks(contract)}}
        self.assertEqual(qa_errors(self.root, contract, path, candidate, report), [])
        del report["checks"]["human_anatomy"]
        self.assertTrue(any("human_anatomy" in x for x in qa_errors(self.root, contract, path, candidate, report)))

    def test_changed_contract_invalidates_report(self):
        record, _, _ = self.accepted_fixture()
        self.attach_passing_report_fixture(record)
        path = self.root / record["contract_path"]
        contract = store_read(path)
        contract["inspection_note"] = "changed after review"
        write_json(path, contract)
        self.assertEqual(self.sync()["status"], "BLOCKED")


class ReferencedWorkflowTest(QualityWorkflowTest):
    referenced = True

    def test_contract_is_a_reference_envelope(self):
        row = self.prepare_approved_set()
        path = self.root / row["contract_path"]
        raw = store_read(path)
        self.assertEqual(raw["storage_mode"], "REFERENCED")
        for key in ("generation_template", "quality_contract", "generation_prompt", "resolved_identity_locks", "visual_system"):
            self.assertNotIn(key, raw)
        resolved = load_contract(self.root, path)
        self.assertEqual(resolved["quality_contract"], self.module["quality_contract"])
        self.assertIn("fixture assembled structure", resolved["generation_prompt"])

    def test_approved_spec_edit_is_blocked(self):
        row = self.prepare_approved_set()
        plan = store_read(self.root / "visual_sets/set1/SET_PLAN.json")
        path = self.root / plan["modules"][0]["spec_path"]
        spec = store_read(path)
        spec["copy"] = {"title": "unsupported edit"}
        write_json(path, spec)
        self.run_script(SINGLE, "validate_run_records.py", "--contract", row["contract_path"], "--ready-for-generation", success=False)

    def test_shared_template_change_is_blocked(self):
        row = self.prepare_approved_set()
        path = self.root / "visual_sets/set1/TEMPLATES.json"
        catalog = store_read(path)
        catalog["templates"][0]["prompt_rules"] = ["changed"]
        write_json(path, catalog)
        self.run_script(SINGLE, "validate_run_records.py", "--contract", row["contract_path"], "--ready-for-generation", success=False)

    def runtime(self, action, *args, success=True):
        output = self.run_script(AMAZON, "set_runtime.py", "--set-id", "set1", action, *args, success=success)
        return json.loads(output.stdout) if success else output

    def test_runtime_packet_excludes_history_and_qa_bookkeeping(self):
        self.prepare_approved_set()
        result = self.runtime("packet")
        self.assertEqual(result["phase"], "generation")
        self.assertNotIn("schema_version", result["prompt"])
        self.assertNotIn("sha256", result["prompt"])
        self.assertNotIn("candidate_sha256", result["prompt"])
        self.assertNotIn("NOT_REVIEWED", result["prompt"])
        self.assertIn("fixture assembled structure", result["prompt"])
        self.assertEqual(len(result["references"]), 1)

    def test_crash_after_image_save_resumes_review(self):
        row = self.prepare_approved_set()
        raw = store_read(self.root / row["contract_path"])
        image = self.root / raw["output_path"]
        image.write_bytes(b"saved before the process was interrupted")
        result = self.runtime("prepare")
        self.assertEqual(result["phase"], "review")
        self.assertEqual(store_bytes(image), b"saved before the process was interrupted")

    def test_explicit_retry_keeps_rejected_attempt_and_resumes_same_retry(self):
        row, contract, _ = self.accepted_fixture()
        state = store_read(self.root / "PRODUCT_STATE.json")
        state["candidates"][0]["status"] = "PENDING_REVIEW"
        write_json(self.root / "PRODUCT_STATE.json", state)
        rejection = self.runtime("record", "--module-id", "gallery-01", "--decision", "REJECTED_TOPOLOGY", "--failure-code", "HARDWARE_STATE")
        self.assertEqual(rejection["current"]["failure_code"], "HARDWARE_STATE")
        saved = store_read(self.root / "PRODUCT_STATE.json")
        self.assertEqual(saved["workflow"]["status"], "REJECTED")
        result = self.runtime("prepare", "--module-id", "gallery-01", "--retry", "--correction", "Preserve the source connector count")
        self.assertEqual(result["attempt"], 2)
        self.assertNotEqual(result["candidate_id"], contract["candidate_id"])
        self.assertTrue(store_exists(self.root / row["contract_path"]))
        resumed = self.runtime("prepare", "--module-id", "gallery-01")
        self.assertEqual(result, resumed)
        self.assertIn("Preserve the source connector count", resumed["prompt"])

    def test_packet_budget_never_silently_truncates(self):
        self.prepare_approved_set()
        result = self.runtime("packet", "--max-bytes", "512", success=False)
        self.assertIn("no constraints were truncated", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_repeat_materialization_preserves_accepted_state(self):
        row, _, _ = self.accepted_fixture()
        self.attach_passing_report_fixture(row)
        self.sync()
        self.run_script(AMAZON, "materialize_module_contracts.py", "--set-id", "set1", "--module-id", "gallery-01")
        state = store_read(self.root / "visual_sets/set1/SET_STATE.json")
        self.assertEqual(state["modules"][0]["status"], "ACCEPTED")
        self.assertEqual(state["status"], "COMPLETE")

    def test_changed_evidence_snapshot_blocks_completion_without_revoking_human_decision(self):
        row, _, _ = self.accepted_fixture()
        self.attach_passing_report_fixture(row)
        self.assertEqual(self.sync()["status"], "COMPLETE")
        index = store_read(self.root / "index.json")
        index["new_correction"] = "source changed after approval"
        write_json(self.root / "index.json", index)
        result = self.runtime("next")
        self.assertEqual(result["set_status"], "BLOCKED")
        self.assertEqual(result["next_action"], "RECONCILE_REFERENCE_CHANGE")
        state = store_read(self.root / "PRODUCT_STATE.json")
        self.assertEqual(state["candidates"][0]["status"], "ACCEPTED")

    def test_thirty_images_recover_from_disk_with_bounded_packets(self):
        self.run_script(AMAZON, "init_visual_set.py", "--set-id", "scale", "--mode", "expanded", "--gallery-count", "30", "--a-plus-count", "0")
        folder = self.root / "visual_sets/scale"
        plan = store_read(folder / "SET_PLAN.json")
        initial_plan_bytes = len(store_bytes(folder / "SET_PLAN.json"))
        plan.update({"positioning": "test", "audience": {"primary": "buyers", "motivation": "inspect"}, "selling_points": {"s_tier": ["accurate view"], "a_tier": [], "b_tier": []}, "visual_system": {"direction": "clean", "palette": ["pink"], "lighting": "soft", "composition": "one object", "retouching": "preserve", "forbidden_cues": ["extra parts"]}})
        plan["design_system"] = {"style_id": "precision_tech", "narrative_framework_id": "DIRECT", "rationale": "Synthetic scale fixture: stable main-image recognition task"}
        for row in plan["modules"]:
            row.update({"target_view": "front_3q", "template_id": "main_product", "template_revision": 1})
            spec = {k: copy.deepcopy(v) for k, v in self.module.items() if k not in {*MODULE_KEYS[1:], "generation_template"}}
            spec["module_id"] = row["module_id"]
            write_json(self.root / row["spec_path"], spec)
        write_json(folder / "SET_PLAN.json", plan)
        self.run_script(AMAZON, "validate_set_plan.py", "--set-id", "scale", "--approve")
        packet_sizes, status_sizes = [], []
        for sequence in range(1, 31):
            output = self.run_script(AMAZON, "set_runtime.py", "--set-id", "scale", "prepare")
            prepared = json.loads(output.stdout)
            output = self.run_script(AMAZON, "set_runtime.py", "--set-id", "scale", "claim", "--module-id", prepared["module_id"])
            work = json.loads(output.stdout)
            self.assertEqual(work["module_id"], f"gallery-{sequence:02d}")
            packet_sizes.append(len(output.stdout.encode()))
            self.assertNotIn("UNRELATED_HISTORY_SENTINEL", output.stdout)
            state = store_read(self.root / "PRODUCT_STATE.json")
            self.assertEqual(len(state["runs"]), sequence)  # Just-in-time contracts only.
            if sequence == 1:
                state["decision_log"] = [{"old_qa": "UNRELATED_HISTORY_SENTINEL " * 10000}]
                write_json(self.root / "PRODUCT_STATE.json", state)
            contract_path = self.root / work["contract_path"]
            contract = load_contract(self.root, contract_path)
            image = Path(work["output_path"])
            image.write_bytes(f"synthetic image {sequence}".encode())
            report_relative = f"qa/visual/scale-{sequence}.json"
            report = {"candidate_id": work["candidate_id"], "candidate_sha256": sha256(image), "contract_sha256": sha256(contract_path), "reviewer": "synthetic regression fixture", "inspection_method": "VISUAL_INSPECTION", "checks": {key: {"status": "PASS", "observation": "synthetic result; not real visual inspection"} for key in required_checks(contract)}, "unresolved_items": []}
            write_json(self.root / report_relative, report)
            self.run_script(AMAZON, "set_runtime.py", "--set-id", "scale", "record", "--module-id", work["module_id"], "--decision", "ACCEPTED", "--report", report_relative, "--human-reviewer", "fixture", "--decision-reference", "synthetic approval fixture", "--claim-token", work["claim_token"])
            output = self.run_script(AMAZON, "set_runtime.py", "--set-id", "scale", "next")
            status_sizes.append(len(output.stdout.encode()))
            status = json.loads(output.stdout)
            self.assertEqual(status["counts"]["ACCEPTED"], sequence)
        self.assertEqual(status["set_status"], "COMPLETE")
        self.assertEqual(status["next_action"], "NONE")
        final_product = store_read(self.root / "PRODUCT_STATE.json")
        self.assertEqual(final_product["workflow"]["status"], "ACCEPTED")
        self.assertTrue(all(x["status"] == "ACCEPTED" for x in final_product["runs"]))
        self.assertLess(max(status_sizes), 1024)
        self.assertLess(max(packet_sizes), 5000)
        self.assertLess(max(packet_sizes) - min(packet_sizes), 128)
        print(f"\nSCALE_MEASUREMENTS draft_plan_bytes={initial_plan_bytes} generation_packet_bytes={min(packet_sizes)}..{max(packet_sizes)} status_bytes={min(status_sizes)}..{max(status_sizes)} images=30")


if __name__ == "__main__":
    unittest.main()
