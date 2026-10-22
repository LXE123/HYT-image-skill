"""Exercise page/image separation using synthetic evidence, never real image QA."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from a_plus_layout import design_handoff, image_membership, layout_errors, layout_progress, profile_drafts
from set_common import default_modules, generation_mode_errors, load_json, plan_modules, sha256, store_module_spec, write_json
from context_store import load_contract
from quality_rules import qa_errors, required_checks
from finalize_a_plus_image import finalize, export_errors
from PIL import Image


class APlusLayoutTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aplus-layout-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        source = self.root / "input/own-product.png"
        source.parent.mkdir()
        source.write_bytes(b"synthetic own-product evidence, not inspected pixels")
        self.index = {"product_id": "own-product", "version": "v1", "product_evidence": [
            {"evidence_id": "own", "path": "input/own-product.png", "sha256": sha256(source),
             "source_type": "REAL_PHOTO", "structures": ["component"], "observed_states": ["assembled"], "hard_constraint": True}
        ]}
        write_json(self.root / "index.json", self.index)
        self.state = {"product_id": "own-product", "sku": "own-sku", "reference_package": {"sha256": sha256(self.root / "index.json")},
                      "product_identity_baseline": {"status": "READY"}, "workflow": {"status": "REFERENCE_READY"},
                      "identity_lockset": {"status": "READY", "version": 1, "locks": [
                          {"lock_id": "identity", "status": "LOCKED", "fact": "Own evidenced identity", "affected_views": ["brand_hero"], "anchor_id": "identity"}
                      ]}, "candidates": [], "runs": []}
        write_json(self.root / "PRODUCT_STATE.json", self.state)
        write_json(self.root / "qa/identity_anchors/index.json", {"anchors": [{"anchor_id": "identity"}]})
        for name in ("source.png", "grayscale.png", "contour.png", "anchor.json"):
            path = self.root / "qa/identity_anchors/identity" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic anchor")

    def run_script(self, name, *args, success=True):
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / name), str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def write_final_candidate(self, packet):
        raw = Path(packet['raw_output_path'])
        raw.parent.mkdir(parents=True, exist_ok=True)
        if not raw.exists():
            Image.new('RGB', (1536, 1024), '#c9b7a1').save(raw)
        finalize(raw, Path(packet['output_path']), [0.05, 0.25, 0.95, 0.75])

    def initialize(self, count=9):
        self.run_script("init_visual_set.py", "--set-id", "aplus", "--deliverable", "a-plus", "--count", str(count))
        self.folder = self.root / "visual_sets/aplus"
        return load_json(self.folder / "SET_PLAN.json")

    def fill_for_approval(self, plan):
        plan["design_system"] = {"style_id": "editorial_daylight", "narrative_framework_id": "AIDA", "rationale": "Synthetic fixture: familiar product recognition followed by evidence and selection help"}
        plan.update({"positioning": "Own product", "audience": {"primary": "buyers", "motivation": "inspect own product"},
                     "selling_points": {"s_tier": ["evidenced identity"], "a_tier": [], "b_tier": []},
                     "visual_system": {"direction": "own brand", "palette": ["navy"], "lighting": "soft", "composition": "one image",
                                       "retouching": "preserve identity", "forbidden_cues": ["invented components"]}})
        for row in plan["modules"]:
            spec = load_json(self.root / row["spec_path"])
            spec["product_references"] = [{"path": "input/own-product.png", "role": "PRODUCT_EVIDENCE", "usage_scope": "PRODUCT_IDENTITY_ONLY"}]
            spec["required_lock_ids"] = ["identity"]
            quality = spec["quality_contract"]
            spec["creative_brief"] = {
                "layout_id": {"product_overview": "editorial_hero", "hardware_static": "benefit_split", "material_macro": "detail_context", "lifestyle_simple": "lifestyle_full", "range_story": "closing_story", "size_fit": "fit_guide", "mechanism_steps": "step_sequence"}[row["template_id"]],
                "story_stage": "recognition" if row["sequence"] == 1 else "proof",
                "visual_concept": row["sales_task"] + " expressed with a distinct clear focal subject",
                "visual_device": "Actual material lit with directional daylight and a readable foreground/background relationship",
                "information_hierarchy": [row["sales_task"], "evidenced supporting detail"],
                "graphic_treatment": "Task-specific hierarchy; no unsupported effects or product claims",
                "set_role": "A distinct part of the product story: " + row["target_view"],
                "success_criteria": ["clear primary focal point", "secondary detail supports the assigned buyer question"],
            }
            quality["layout"]["composition"] = "Own product at right in supported view; separate empty copy region at left"
            if row["template_id"] == "hardware_static":
                quality["visible_hardware"] = ["component"]
                quality["structure_checks"] = [{"structure_id": "component", "expected_state": "assembled", "lock_ids": ["identity"],
                                                "evidence_paths": ["input/own-product.png"], "visible_checks": ["preserve actual component interface"]}]
            if quality["human"]["present"]:
                quality["human"].update({"pose_description": "One continuous left shoulder, elbow, wrist and relaxed hand",
                                          "visible_limbs": ["left arm"], "contact_points": ["product against wrist"], "occlusion_order": ["arm in front of torso"]})
            write_json(self.root / row["spec_path"], spec)
        write_json(self.folder / "SET_PLAN.json", plan)

    def test_profile_initializes_seven_groups_nine_own_product_tasks(self):
        plan = self.initialize()
        modules = plan_modules(self.root, plan)
        self.assertEqual(len(plan["a_plus_layout"]["page_modules"]), 7)
        self.assertEqual(len(modules), 9)
        self.assertEqual(plan["generation_mode"], "standard")
        self.assertTrue(all(x["channel"] == "PREMIUM_A_PLUS" for x in modules))
        self.assertTrue(all(x["output_requirements"]["width_px"] == 1464 and x["output_requirements"]["height_px"] == 600 for x in modules))
        self.assertEqual(layout_errors(plan, modules), [])
        self.assertTrue(all(not x["product_references"] and not x["style_source_ids"] and not x["claim_ids"] for x in modules))
        snapshot = load_json(self.folder / "INPUT_SNAPSHOT.json")
        self.assertEqual(snapshot["product_id"], "own-product")
        self.assertEqual(snapshot["commercial_manifest"]["sources"], [])
        status = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "next").stdout)
        self.assertEqual(status["a_plus"]["page_modules"], 7)
        self.assertEqual(status["a_plus"]["image_tasks"], 9)
        self.assertEqual(status["current"]["page"]["page_module_id"], "aplus-hero")

    def test_grouping_rejects_orphan_duplicate_cross_channel_and_wrong_ratio(self):
        layout, modules = profile_drafts()
        plan = {"a_plus_layout": layout}
        for mutate in (
            lambda p, m: p["a_plus_layout"]["page_modules"][2]["image_ids"].pop(),
            lambda p, m: p["a_plus_layout"]["page_modules"][2]["image_ids"].append("a-plus-01"),
            lambda p, m: m[0].update(channel="AMAZON_GALLERY"),
            lambda p, m: m[0]["output_requirements"].update(aspect_ratio="21:9"),
            lambda p, m: m[0]["output_requirements"].update(height_px=450),
        ):
            changed, tasks = copy.deepcopy(plan), copy.deepcopy(modules)
            mutate(changed, tasks)
            self.assertTrue(layout_errors(changed, tasks))

    def test_draft_addition_promotes_group_and_preserves_existing_specs_and_ids(self):
        plan = self.initialize()
        hashes = {x["module_id"]: sha256(self.root / x["spec_path"]) for x in plan["modules"]}
        self.run_script("add_a_plus_image.py", "--set-id", "aplus", "--page-module-id", "aplus-craftsmanship", "--image-id", "edge-detail",
                        "--template-id", "hardware_static", "--target-view", "edge", "--sales-task", "Edge finishing", "--buyer-question", "How is the edge finished?")
        changed = load_json(self.folder / "SET_PLAN.json")
        self.assertEqual(len(changed["a_plus_layout"]["page_modules"]), 7)
        self.assertEqual(len(changed["modules"]), 10)
        self.assertEqual(changed["modules"][2]["module_id"], "edge-detail")
        page = changed["a_plus_layout"]["page_modules"][1]
        self.assertEqual(page["display_type"], "CAROUSEL")
        self.assertEqual(page["image_ids"], ["a-plus-02", "edge-detail"])
        for row in changed["modules"]:
            if row["module_id"] in hashes:
                self.assertEqual(sha256(self.root / row["spec_path"]), hashes[row["module_id"]])
        self.assertEqual(layout_errors(changed, plan_modules(self.root, changed)), [])
        before = (self.folder / "SET_PLAN.json").read_bytes()
        self.run_script("add_a_plus_image.py", "--set-id", "aplus", "--page-module-id", "aplus-craftsmanship", "--image-id", "edge-detail",
                        "--template-id", "hardware_static", "--target-view", "edge", "--sales-task", "Edge", "--buyer-question", "Edge?", success=False)
        self.assertEqual((self.folder / "SET_PLAN.json").read_bytes(), before)

    def test_new_group_is_inserted_without_renaming_existing_images(self):
        self.initialize()
        self.run_script("add_a_plus_image.py", "--set-id", "aplus", "--page-module-id", "aplus-added-detail", "--image-id", "new-detail",
                        "--new-page", "--content-role", "detail", "--after-page-id", "aplus-craftsmanship",
                        "--template-id", "material_macro", "--target-view", "detail", "--sales-task", "New detail", "--buyer-question", "Which detail?")
        plan = load_json(self.folder / "SET_PLAN.json")
        self.assertEqual(len(plan["a_plus_layout"]["page_modules"]), 8)
        self.assertEqual(plan["a_plus_layout"]["page_modules"][2]["page_module_id"], "aplus-added-detail")
        self.assertEqual({x["module_id"] for x in plan["modules"]}, {f"a-plus-{i:02d}" for i in range(1, 10)} | {"new-detail"})
        self.assertEqual(layout_errors(plan, plan_modules(self.root, plan)), [])

    def test_approval_packet_and_designer_handoff_keep_single_image_scope(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve")
        packet = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare").stdout)
        self.assertEqual(packet["page"]["page_module_id"], "aplus-hero")
        self.assertEqual(len(packet["references"]), 1)
        self.assertTrue(packet["references"][0]["path"].endswith("own-product.png"))
        self.assertIn('"width_px":1464', packet["prompt"].replace(" ", ""))
        self.assertIn('"height_px":600', packet["prompt"].replace(" ", ""))
        self.assertNotIn("aplus-lifestyle", packet["prompt"])
        self.assertNotIn("SUNFWR", packet["prompt"])
        self.assertNotIn("cowhide", packet["prompt"])
        before = (self.folder / "SET_PLAN.json").read_bytes()
        self.run_script("add_a_plus_image.py", "--set-id", "aplus", "--page-module-id", "aplus-craftsmanship", "--image-id", "late-detail",
                        "--template-id", "hardware_static", "--target-view", "edge", "--sales-task", "Edge", "--buyer-question", "Edge?", success=False)
        self.assertEqual((self.folder / "SET_PLAN.json").read_bytes(), before)
        self.assertFalse((self.folder / "modules/late-detail.json").exists())
        handoff = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "handoff").stdout)
        self.assertEqual(handoff["assembly_owner"], "DESIGN_TEAM")
        self.assertEqual(sum(len(x["images"]) for x in handoff["page_modules"]), 9)
        self.assertTrue(all("accepted_output" not in x for p in handoff["page_modules"] for x in p["images"]))

    def test_page_status_requires_all_required_children(self):
        layout, modules = profile_drafts()
        plan = {"set_id": "test", "a_plus_layout": layout}
        rows = [{"module_id": x["module_id"], "status": "ACCEPTED", "required": True} for x in modules]
        rows[3]["status"] = "REVIEW_REQUIRED"
        self.assertEqual(layout_progress(plan, rows)[2]["status"], "PENDING")
        rows[3]["status"] = "ACCEPTED"
        self.assertEqual(layout_progress(plan, rows)[2]["status"], "ACCEPTED")
        self.assertEqual(image_membership(plan, "a-plus-04")["image_position"], 2)
        self.assertEqual(design_handoff(plan, rows)["page_modules"][2]["images"][1]["image_task_id"], "a-plus-04")

    def test_explicit_generic_templates_remain_available(self):
        modules = default_modules(9, 9)
        self.assertEqual(len(modules), 18)
        self.assertTrue(all(x["output_requirements"]["aspect_ratio"] == "1464:600" for x in modules if x["channel"] == "PREMIUM_A_PLUS"))
        self.assertEqual(layout_errors({"modules": modules}, modules), [])

    def test_expanded_mode_is_explicit_and_defaults_within_requested_range(self):
        self.run_script("init_visual_set.py", "--set-id", "expanded", "--deliverable", "both", "--mode", "expanded")
        plan = load_json(self.root / "visual_sets/expanded/SET_PLAN.json")
        self.assertEqual(plan["generation_mode"], "expanded")
        self.assertEqual(len(plan["modules"]), 72)
        self.assertEqual(sum(x["channel"] == "AMAZON_GALLERY" for x in plan["modules"]), 36)
        self.assertEqual(sum(x["channel"] == "PREMIUM_A_PLUS" for x in plan["modules"]), 36)
        self.assertNotIn("a_plus_layout", plan)

    def test_large_count_requires_activation_before_any_files_are_created(self):
        for count in (30, 40):
            result = self.run_script("init_visual_set.py", "--set-id", f"blocked-{count}", "--gallery-count", str(count), "--a-plus-count", "0", success=False)
            self.assertIn("explicit --mode expanded", result.stderr)
            self.assertFalse((self.root / f"visual_sets/blocked-{count}").exists())
        self.assertFalse((self.root / "commercial").exists())
        self.run_script("init_visual_set.py", "--set-id", "forty", "--mode", "expanded", "--gallery-count", "0", "--a-plus-count", "40")
        self.assertEqual(len(load_json(self.root / "visual_sets/forty/SET_PLAN.json")["modules"]), 40)
        self.run_script("init_visual_set.py", "--set-id", "too-many", "--mode", "expanded", "--gallery-count", "41", "--a-plus-count", "0", success=False)
        self.assertFalse((self.root / "visual_sets/too-many").exists())

    def test_small_explicit_channels_and_profile_override_take_precedence(self):
        self.run_script("init_visual_set.py", "--set-id", "gallery-only", "--gallery-count", "1", "--a-plus-count", "0")
        plan = load_json(self.root / "visual_sets/gallery-only/SET_PLAN.json")
        self.assertEqual(len(plan["modules"]), 1)
        self.assertEqual(plan["modules"][0]["channel"], "AMAZON_GALLERY")
        self.assertNotIn("a_plus_layout", plan)
        self.run_script("init_visual_set.py", "--set-id", "generic", "--a-plus-profile", "none")
        generic = load_json(self.root / "visual_sets/generic/SET_PLAN.json")
        self.assertEqual(len(generic["modules"]), 13)
        self.assertNotIn("a_plus_layout", generic)
        self.assertTrue(all(x["output_requirements"]["aspect_ratio"] == "1464:600" for x in plan_modules(self.root, generic)))

    def test_local_addition_does_not_silently_activate_large_production(self):
        plan = self.initialize()
        extra = []
        for i, item in enumerate(default_modules(0, 20), 10):
            item["module_id"] = f"extra-{i}"
            item["sequence"] = i
            item["output_requirements"].update({"aspect_ratio": "1464:600", "width_px": 1464, "height_px": 600})
            extra.append(store_module_spec(self.root, self.folder, item))
        plan["a_plus_layout"]["page_modules"][2]["image_ids"].extend(x["module_id"] for x in extra)
        plan["modules"] = extra + plan["modules"]
        write_json(self.folder / "SET_PLAN.json", plan)
        before = (self.folder / "SET_PLAN.json").read_bytes()
        args = ("--set-id", "aplus", "--page-module-id", "aplus-craftsmanship", "--image-id", "thirtieth",
                "--template-id", "hardware_static", "--target-view", "edge", "--sales-task", "Edge", "--buyer-question", "Which edge?")
        blocked = self.run_script("add_a_plus_image.py", *args, success=False)
        self.assertIn("--activate-expanded", blocked.stderr)
        self.assertEqual((self.folder / "SET_PLAN.json").read_bytes(), before)
        self.assertFalse((self.folder / "modules/thirtieth.json").exists())
        self.run_script("add_a_plus_image.py", *args, "--activate-expanded")
        changed = load_json(self.folder / "SET_PLAN.json")
        self.assertEqual(changed["generation_mode"], "expanded")
        self.assertEqual(len(changed["modules"]), 30)
        self.assertEqual(changed["a_plus_layout"]["canvas"], {"width_px": 1464, "height_px": 600})

    def test_new_plan_mode_guard_and_legacy_resume(self):
        channel = {"channel": "PREMIUM_A_PLUS"}
        self.assertTrue(generation_mode_errors({"generation_mode": "standard", "modules": [channel] * 30}))
        self.assertEqual(generation_mode_errors({"generation_mode": "expanded", "modules": [channel] * 40}), [])
        self.assertTrue(generation_mode_errors({"generation_mode": "expanded", "modules": [channel] * 41}))
        self.assertEqual(generation_mode_errors({"modules": [{}] * 60}), [])
        plan = self.initialize()
        plan.pop("generation_mode")
        write_json(self.folder / "SET_PLAN.json", plan)
        before = (self.folder / "SET_PLAN.json").read_bytes()
        status = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "next").stdout)
        self.assertEqual(status["total"], 9)
        self.assertNotIn("generation_mode", status)
        self.assertEqual((self.folder / "SET_PLAN.json").read_bytes(), before)

    def test_unqualified_request_has_no_implicit_channel_or_side_effects(self):
        result = self.run_script("init_visual_set.py", "--set-id", "ambiguous", success=False)
        self.assertIn("choose --deliverable", result.stderr)
        self.assertFalse((self.root / "visual_sets").exists())
        self.assertFalse((self.root / "commercial").exists())

    def test_requested_channels_each_default_to_thirteen(self):
        for scope, expected in (("gallery", (13, 0)), ("a-plus", (0, 13)), ("both", (13, 13))):
            self.run_script("init_visual_set.py", "--set-id", scope, "--deliverable", scope)
            plan = load_json(self.root / f"visual_sets/{scope}/SET_PLAN.json")
            counts = tuple(sum(x["channel"] == channel for x in plan["modules"]) for channel in ("AMAZON_GALLERY", "PREMIUM_A_PLUS"))
            self.assertEqual(counts, expected)
            self.assertEqual(plan["deliverable"], scope)
            self.assertEqual(plan["quantity_policy"]["scope"], "PER_CHANNEL")
            self.assertEqual(tuple(plan["quantity_policy"]["selected_counts"][channel] for channel in ("AMAZON_GALLERY", "PREMIUM_A_PLUS")), expected)
            self.assertEqual(layout_errors(plan, plan_modules(self.root, plan)), [])
            output = json.loads(self.run_script("set_runtime.py", "--set-id", scope, "handoff").stdout)
            self.assertEqual(len(output.get("gallery_images", [])), expected[0])
            self.assertEqual(sum(len(x["images"]) for x in output["page_modules"]), expected[1])
            if expected[0]:
                gallery = next(x for x in plan_modules(self.root, plan) if x["channel"] == "AMAZON_GALLERY")
                self.assertEqual(gallery["output_requirements"]["aspect_ratio"], "1:1")
                self.assertNotIn("width_px", gallery["output_requirements"])

    def test_selected_thirteen_cannot_silently_collapse_to_seven_tasks(self):
        plan = self.initialize(13)
        self.assertEqual(generation_mode_errors(plan), [])
        plan['modules'] = plan['modules'][:7]
        self.assertTrue(any('selected image counts' in x for x in generation_mode_errors(plan)))

    def write_ready_design_brief(self):
        roles = ['hero', 'craftsmanship', 'material', 'component', 'lifestyle', 'lifestyle', 'variants', 'size_and_fit', 'care']
        groups = ['intro', 'making', 'details', 'details', 'contexts', 'contexts', 'choices', 'sizing', 'maintenance']
        brief = {
            'schema_version': 1,
            'job': {'channel': 'PREMIUM_A_PLUS', 'scope': 'full_set', 'target_image_count': 9, 'language': 'de', 'width': 1464, 'height': 600},
            'content_groups': [{'group_id': group, 'role': roles[groups.index(group)], 'buyer_question': 'Group responsibility: ' + group}
                               for group in dict.fromkeys(groups)],
            'modules': [{'image_id': f'custom-{i+1:02d}', 'role': role, 'content_group_id': groups[i],
                         'buyer_question': 'Specific assigned question: ' + role, 'must_show': ['Required source proof for ' + role],
                         'product_evidence_ids': ['own'], 'copy': [{'text': 'Für Größe wählen – äöü', 'language': 'de'}]}
                        for i, role in enumerate(roles)],
            'deferred_modules': [],
        }
        path = self.root / 'DESIGN_INPUT.json'
        write_json(path, brief)
        return path, brief

    def test_filtered_brief_keeps_custom_grouping_ids_count_copy_and_proof_through_generation(self):
        path, brief = self.write_ready_design_brief()
        self.run_script('init_visual_set.py', '--set-id', 'aplus', '--design-input', str(path))
        self.folder = self.root / 'visual_sets/aplus'
        plan = load_json(self.folder / 'SET_PLAN.json')
        self.assertEqual([x['module_id'] for x in plan['modules']], [x['image_id'] for x in brief['modules']])
        self.assertEqual(plan['quantity_policy']['selected_counts']['PREMIUM_A_PLUS'], 9)
        self.assertEqual([len(x['image_ids']) for x in plan['a_plus_layout']['page_modules']], [1, 1, 2, 2, 1, 1, 1])
        self.assertEqual(layout_errors(plan, plan_modules(self.root, plan)), [])
        self.fill_for_approval(plan)
        self.run_script('validate_set_plan.py', '--set-id', 'aplus', '--approve')
        packet = json.loads(self.run_script('set_runtime.py', '--set-id', 'aplus', 'prepare', '--module-id', 'custom-08').stdout)
        contract = load_contract(self.root, self.root / packet['contract_path'])
        self.assertEqual(contract['module_language']['role'], 'fit')
        self.assertIn('Required source proof for size_and_fit', contract['module_language']['must_show'])
        self.assertEqual(contract['image_intent']['content_group_id'], 'sizing')
        self.assertIn('Required source proof for size_and_fit', packet['prompt'])
        self.assertIn('Für Größe wählen – äöü', packet['prompt'])
        snapshot = load_json(self.folder / 'INPUT_SNAPSHOT.json')
        self.assertEqual(sha256(path), snapshot['design_brief']['sha256'])
        self.assertFalse((self.folder / 'DESIGN_INPUT.json').exists())
        raw = load_json(self.root / packet['contract_path'])
        self.assertEqual(set(raw['bindings']), {'plan'})
        # Older envelopes remain readable, but contradictory snapshot bindings fail.
        raw['bindings']['snapshot'] = {'path': plan['input_snapshot'], 'sha256': sha256(self.root / plan['input_snapshot'])}
        legacy_path = self.root / 'legacy-envelope.json'
        write_json(legacy_path, raw)
        self.assertEqual(load_contract(self.root, legacy_path)['image_intent'], contract['image_intent'])
        raw['bindings']['snapshot']['sha256'] = '0' * 64
        write_json(legacy_path, raw)
        with self.assertRaisesRegex(ValueError, 'snapshot differs'):
            load_contract(self.root, legacy_path)

    def test_selected_visual_facts_and_copy_only_benefit_remain_separate_through_prompt(self):
        path, brief = self.write_ready_design_brief()
        brief['product'] = {'facts': [
            {'fact_id': 'surface', 'text': 'Observed two-tone woven surface'},
            {'fact_id': 'comfort', 'text': 'Supplier-supported comfort statement, not visual proof'},
            {'fact_id': 'other', 'text': 'Unrelated supplied detail for another task'},
        ]}
        child = brief['modules'][7]
        child['sales_task'] = 'Explain the selection with an actual surface detail and exact copy'
        child['required_fact_ids'] = ['surface']
        child['copy'] = [{'text': 'Weich & bequem', 'language': 'de', 'required_fact_ids': ['comfort']}]
        write_json(path, brief)
        self.run_script('init_visual_set.py', '--set-id', 'aplus', '--design-input', str(path))
        self.folder = self.root / 'visual_sets/aplus'
        plan = load_json(self.folder / 'SET_PLAN.json')
        self.assertEqual(plan['modules'][7]['sales_task'], child['sales_task'])
        self.fill_for_approval(plan)
        self.run_script('validate_set_plan.py', '--set-id', 'aplus', '--approve')
        packet = json.loads(self.run_script('set_runtime.py', '--set-id', 'aplus', 'prepare', '--module-id', 'custom-08').stdout)
        contract = load_contract(self.root, self.root / packet['contract_path'])
        self.assertEqual(contract['image_intent']['product_facts'], [{'fact_id': 'surface', 'text': brief['product']['facts'][0]['text']}])
        self.assertEqual(contract['copy'], {'labels': ['Weich & bequem']})
        self.assertIn(brief['product']['facts'][0]['text'], packet['prompt'])
        self.assertNotIn(brief['product']['facts'][1]['text'], packet['prompt'])
        self.assertNotIn(brief['product']['facts'][2]['text'], packet['prompt'])

    def test_wrong_canvas_mixed_language_and_unknown_fact_imports_create_no_set(self):
        for case in ('mobile', 'other-canvas', 'languages', 'visual-fact', 'copy-fact'):
            path, brief = self.write_ready_design_brief()
            if case in ('mobile', 'other-canvas'):
                brief['job'].update(width=600 if case == 'mobile' else 970, height=450 if case == 'mobile' else 600)
            elif case == 'languages':
                brief['modules'][0]['copy'].append({'text': 'Unselected translation', 'language': 'en'})
            elif case == 'visual-fact':
                brief['modules'][0]['required_fact_ids'] = ['missing']
            else:
                brief['modules'][0]['copy'][0]['required_fact_ids'] = ['missing']
            write_json(path, brief)
            self.run_script('init_visual_set.py', '--set-id', case, '--design-input', str(path), success=False)
            self.assertFalse((self.root / 'visual_sets').exists())
            self.assertFalse((self.root / 'commercial').exists())

    def test_all_a_plus_paths_reject_other_canvas_while_gallery_keeps_its_own_format(self):
        layout, tasks = profile_drafts(9)
        for grouped in (False, True):
            changed = copy.deepcopy(tasks)
            changed[0]['output_requirements'].update(width_px=600, height_px=450, aspect_ratio='4:3')
            plan = {'a_plus_layout': layout} if grouped else {}
            self.assertTrue(layout_errors(plan, changed))
            self.assertEqual(layout_errors(plan, tasks), [])
        self.assertEqual(layout_errors({}, default_modules(3, 0)), [])

    def test_brief_count_conflict_undecomposed_groups_and_unknown_evidence_create_no_set(self):
        path, brief = self.write_ready_design_brief()
        self.run_script('init_visual_set.py', '--set-id', 'conflict', '--design-input', str(path), '--count', '13', success=False)
        self.assertFalse((self.root / 'visual_sets').exists())
        brief['job']['target_image_count'] = 13
        brief['modules'] = brief['modules'][:7]
        # An old cached readiness label cannot override the actual target/tasks.
        brief['image_plan'] = {'status': 'READY_FOR_DESIGN', 'planned_image_count': 13}
        write_json(path, brief)
        self.run_script('init_visual_set.py', '--set-id', 'short', '--design-input', str(path), success=False)
        self.assertFalse((self.root / 'visual_sets').exists())
        path, brief = self.write_ready_design_brief()
        brief['modules'][0]['product_evidence_ids'] = ['unknown']
        write_json(path, brief)
        self.run_script('init_visual_set.py', '--set-id', 'bad-source', '--design-input', str(path), success=False)
        self.assertFalse((self.root / 'visual_sets').exists())

    def test_imported_tasks_do_not_depend_on_a_second_runtime_brief_copy(self):
        path, brief = self.write_ready_design_brief()
        self.run_script('init_visual_set.py', '--set-id', 'aplus', '--design-input', str(path))
        self.folder = self.root / 'visual_sets/aplus'
        plan = load_json(self.folder / 'SET_PLAN.json')
        self.fill_for_approval(plan)
        path.write_text('{}')
        self.run_script('validate_set_plan.py', '--set-id', 'aplus', '--approve')
        packet = json.loads(self.run_script('set_runtime.py', '--set-id', 'aplus', 'prepare', '--module-id', 'custom-08').stdout)
        self.assertIn('Für Größe wählen – äöü', packet['prompt'])
        self.assertIn('Required source proof for size_and_fit', packet['prompt'])
        snapshot_path = self.folder / 'INPUT_SNAPSHOT.json'
        snapshot = load_json(snapshot_path)
        snapshot['sellable_object'] = {'included': ['tampered']}
        write_json(snapshot_path, snapshot)
        with self.assertRaisesRegex(ValueError, 'pinned file changed'):
            load_contract(self.root, self.root / packet['contract_path'])

    def test_brief_group_integrity_is_checked_without_a_readiness_entity(self):
        path, brief = self.write_ready_design_brief()
        for task in brief['modules']:
            task['content_group_id'] = 'intro'
        write_json(path, brief)
        self.run_script('init_visual_set.py', '--set-id', 'unmapped', '--design-input', str(path), success=False)
        self.assertFalse((self.root / 'visual_sets').exists())
        path, brief = self.write_ready_design_brief()
        brief['content_groups'].append(brief['content_groups'][0])
        write_json(path, brief)
        self.run_script('init_visual_set.py', '--set-id', 'duplicate-group', '--design-input', str(path), success=False)
        self.assertFalse((self.root / 'visual_sets').exists())

    def test_authorized_local_addition_updates_selected_count(self):
        self.initialize(9)
        self.run_script('add_a_plus_image.py', '--set-id', 'aplus', '--page-module-id', 'aplus-craftsmanship',
                        '--image-id', 'extra-detail', '--sales-task', 'Explain supported edge finishing',
                        '--buyer-question', 'How is the evidenced edge finished?', '--target-view', 'edge_detail',
                        '--template-id', 'hardware_static')
        plan = load_json(self.folder / 'SET_PLAN.json')
        self.assertEqual(plan['quantity_policy']['selected_counts']['PREMIUM_A_PLUS'], 10)
        self.assertEqual(generation_mode_errors(plan), [])

    def test_a_plus_range_has_valid_membership_and_distinct_extra_tasks(self):
        for count in range(9, 16):
            layout, tasks = profile_drafts(count)
            self.assertEqual(len(tasks), count)
            self.assertEqual(len({x["buyer_question"] for x in tasks}), count)
            self.assertEqual(layout_errors({"a_plus_layout": layout}, tasks), [])
            self.assertEqual(sum(len(x["image_ids"]) for x in layout["page_modules"]), count)
            self.assertTrue(all(x["output_requirements"]["width_px"] == 1464 for x in tasks))

    def test_two_sets_of_fifteen_are_standard_not_expanded(self):
        self.run_script("init_visual_set.py", "--set-id", "two-sets", "--deliverable", "both", "--count", "15")
        plan = load_json(self.root / "visual_sets/two-sets/SET_PLAN.json")
        self.assertEqual(len(plan["modules"]), 30)
        self.assertEqual(plan["generation_mode"], "standard")
        self.assertEqual(generation_mode_errors(plan), [])

    def test_content_purpose_reaches_generation_and_visual_coverage_is_required(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve")
        packet = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare").stdout)
        self.assertIn("Image purpose:", packet["prompt"])
        self.assertIn("Creative direction:", packet["prompt"])
        self.assertIn("Selected design recipe:", packet["prompt"])
        self.assertIn("editorial_hero", packet["prompt"])
        self.assertNotIn("variant_grid", packet["prompt"])
        self.assertIn("What is the complete actual product?", packet["prompt"])
        path = self.root / packet["contract_path"]
        contract = load_contract(self.root, path)
        image = Path(packet["output_path"])
        self.write_final_candidate(packet)
        candidate = {"candidate_id": packet["candidate_id"], "path": contract["output_path"]}
        report = {"candidate_id": packet["candidate_id"], "candidate_sha256": sha256(image), "contract_sha256": sha256(path),
                  "inspection_method": "VISUAL_INSPECTION", "reviewer": "synthetic fixture", "unresolved_items": [],
                  "checks": {key: {"status": "PASS", "observation": "synthetic recorded result, not real inspection"} for key in required_checks(contract)}}
        self.assertEqual(qa_errors(self.root, contract, path, candidate, report), [])
        design_check = report["checks"].pop("design_quality")
        self.assertTrue(any("design_quality" in x for x in qa_errors(self.root, contract, path, candidate, report)))
        report["checks"]["design_quality"] = design_check
        report["checks"].pop("content_coverage")
        self.assertTrue(any("content_coverage" in x for x in qa_errors(self.root, contract, path, candidate, report)))
        reviewed = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "packet", "--phase", "review").stdout)
        self.assertIn("content_coverage", reviewed["checks"])
        self.assertIn("design_quality", reviewed["checks"])
        self.assertEqual(reviewed["expected"]["creative_brief"], contract["creative_brief"])
        self.assertEqual(reviewed["expected"]["image_intent"]["buyer_question"], "What is the complete actual product?")

    def test_new_plan_requires_actual_creative_decisions_before_approval(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        path = self.root / plan["modules"][0]["spec_path"]
        spec = load_json(path)
        spec["creative_brief"]["visual_device"] = ""
        write_json(path, spec)
        result = self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve", success=False)
        self.assertIn("creative_brief.visual_device", result.stdout)
        self.assertEqual(load_json(self.folder / "SET_PLAN.json")["status"], "DRAFT")
        spec.pop("creative_brief")
        write_json(path, spec)
        result = self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve", success=False)
        self.assertIn("creative_brief", result.stdout)

    def test_previous_policy_plan_does_not_acquire_new_design_checks_on_resume(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        plan.pop("creative_policy_version")
        plan.pop("design_policy_version")
        plan.pop("module_language_policy_version")
        for row in plan["modules"]:
            path = self.root / row["spec_path"]
            spec = load_json(path)
            spec.pop("creative_brief")
            write_json(path, spec)
        write_json(self.folder / "SET_PLAN.json", plan)
        self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve")
        packet = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare").stdout)
        contract = load_contract(self.root, self.root / packet["contract_path"])
        self.assertNotIn("Creative direction:", packet["prompt"])
        self.assertNotIn("design_quality", required_checks(contract))
        self.assertNotIn("module_role_fit", required_checks(contract))

    def test_module_language_changes_with_each_images_actual_job(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve")
        roles = {"a-plus-01": "hero", "a-plus-02": "detail", "a-plus-03": "material", "a-plus-05": "lifestyle", "a-plus-07": "variants", "a-plus-08": "fit", "a-plus-09": "care"}
        languages = []
        for image_id, role in roles.items():
            packet = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare", "--module-id", image_id).stdout)
            contract = load_contract(self.root, self.root / packet["contract_path"])
            language = contract["module_language"]
            self.assertEqual(language["image_task_id"], image_id)
            self.assertEqual(language["role"], role)
            self.assertIn(language["visual_language"], packet["prompt"])
            self.assertIn("module_role_fit", required_checks(contract))
            languages.append(language["visual_language"])
        self.assertEqual(len(languages), len(set(languages)))
        # A shared parent does not turn a hardware detail into material photography.
        detail = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare", "--module-id", "a-plus-04").stdout)
        contract = load_contract(self.root, self.root / detail["contract_path"])
        self.assertEqual(contract["module_language"]["role"], "detail")
        self.assertEqual(contract["module_language"]["parent"]["content_role"], "material_and_details")

    def test_next_generation_skips_saved_pending_image_without_accepting_it(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve")
        first = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare").stdout)
        self.write_final_candidate(first)
        self.run_script("set_runtime.py", "--set-id", "aplus", "record", "--module-id", "a-plus-01", "--decision", "PENDING_REVIEW")
        review = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "next").stdout)
        self.assertEqual(review["current"]["module_id"], "a-plus-01")
        following = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "next-generation").stdout)
        self.assertEqual(following["current"]["module_id"], "a-plus-02")
        second = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare", "--module-id", following["current"]["module_id"]).stdout)
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])
        self.assertNotEqual(first["output_path"], second["output_path"])
        contract = load_contract(self.root, self.root / second["contract_path"])
        self.assertEqual(contract["module_language"]["role"], "detail")
        product = load_json(self.root / "PRODUCT_STATE.json")
        self.assertEqual(product["candidates"][0]["status"], "PENDING_REVIEW")
        self.run_script("set_runtime.py", "--set-id", "aplus", "next-generation", "--module-id", "a-plus-01", success=False)

    def test_role_fit_is_required_in_actual_review_packet(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve")
        packet = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare", "--module-id", "a-plus-03").stdout)
        self.write_final_candidate(packet)
        reviewed = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "packet", "--module-id", "a-plus-03", "--phase", "review").stdout)
        self.assertEqual(reviewed["expected"]["module_language"]["role"], "material")
        self.assertIn("module_role_fit", reviewed["checks"])
        contract = load_contract(self.root, self.root / packet["contract_path"])
        candidate = {"candidate_id": packet["candidate_id"], "path": contract["output_path"]}
        report = {"candidate_id": packet["candidate_id"], "candidate_sha256": sha256(Path(packet["output_path"])), "contract_sha256": sha256(self.root / packet["contract_path"]), "inspection_method": "VISUAL_INSPECTION", "reviewer": "synthetic fixture", "unresolved_items": [], "checks": {key: {"status": "PASS", "observation": "synthetic record only"} for key in required_checks(contract)}}
        report["checks"].pop("module_role_fit")
        self.assertTrue(any("module_role_fit" in e for e in qa_errors(self.root, contract, self.root / packet["contract_path"], candidate, report)))

    def test_repeated_expression_across_roles_is_flagged_even_in_adaptive_mode(self):
        from design_store import design_plan_checks
        plan = self.initialize()
        self.fill_for_approval(plan)
        plan["design_system"] = {"mode": "adaptive", "narrative_framework_id": "DIRECT", "rationale": "Synthetic fixture"}
        for row in plan["modules"]:
            path = self.root / row["spec_path"]
            spec = load_json(path)
            spec["creative_brief"].update(layout_id="adaptive", story_stage="single_message")
            write_json(path, spec)
        errors, warnings = design_plan_checks(self.root, plan, plan_modules(self.root, plan))
        self.assertEqual(errors, [])
        self.assertTrue(any("Different module responsibilities" in w for w in warnings))

    def test_catalog_filter_and_selection_resolve_one_executable_recipe(self):
        self.initialize()
        before = (self.folder / "SET_PLAN.json").read_bytes()
        catalog = json.loads(self.run_script("configure_design.py", "--set-id", "aplus", "catalog", "--template-id", "material_macro").stdout)
        self.assertEqual((self.folder / "SET_PLAN.json").read_bytes(), before)
        self.assertTrue(all("material_macro" in x["templates"] for x in catalog["layouts"]))
        self.assertEqual(len(catalog["styles"]), 6)
        self.run_script("configure_design.py", "--set-id", "aplus", "configure", "--style-id", "active_bright", "--framework-id", "JTBD", "--rationale", "Synthetic fixture: recognizable daily use and factual material proof")
        other_spec = self.folder / "modules/a-plus-02.json"
        other_before = other_spec.read_bytes()
        selected = json.loads(self.run_script("configure_design.py", "--set-id", "aplus", "select", "--module-id", "a-plus-03", "--layout-id", "detail_context", "--story-stage", "proof").stdout)
        self.assertEqual(selected["design_preview"]["style"]["style_id"], "active_bright")
        self.assertEqual(selected["design_preview"]["layout"]["layout_id"], "detail_context")
        self.assertEqual(selected["design_preview"]["narrative"]["stage"], "proof")
        self.assertNotIn("styles", selected["design_preview"])
        spec = load_json(self.folder / "modules/a-plus-03.json")
        self.assertEqual(spec["quality_contract"]["layout"]["product_box"], [.30, .05, .96, .94])
        self.assertEqual(spec["creative_brief"]["visual_concept"], "")
        self.assertEqual(other_spec.read_bytes(), other_before)

    def test_decorative_layout_cannot_be_selected_for_main_product(self):
        self.run_script("init_visual_set.py", "--set-id", "main", "--deliverable", "gallery", "--count", "1")
        self.run_script("configure_design.py", "--set-id", "main", "configure", "--style-id", "dramatic_studio", "--framework-id", "DIRECT", "--rationale", "Synthetic fixture: main image identification")
        path = self.root / "visual_sets/main/modules/gallery-01.json"
        before = path.read_bytes()
        result = self.run_script("configure_design.py", "--set-id", "main", "select", "--module-id", "gallery-01", "--layout-id", "editorial_hero", "--story-stage", "single_message", success=False)
        self.assertIn("incompatible", result.stderr)
        self.assertEqual(path.read_bytes(), before)
        selected = json.loads(self.run_script("configure_design.py", "--set-id", "main", "select", "--module-id", "gallery-01", "--layout-id", "main_clean", "--story-stage", "single_message").stdout)
        self.assertIn("white main-image", selected["design_preview"]["style"]["task_treatment"])
        self.assertIsNone(selected["layout_starting_points"]["copy_box"])

    def test_order_updates_a_plus_page_delivery_and_queue_without_renaming(self):
        plan = self.initialize()
        hashes = {x["module_id"]: sha256(self.root / x["spec_path"]) for x in plan["modules"]}
        order = list(reversed([x["page_module_id"] for x in plan["a_plus_layout"]["page_modules"]]))
        self.run_script("configure_design.py", "--set-id", "aplus", "order", "--channel", "a-plus", "--order", ",".join(order))
        changed = load_json(self.folder / "SET_PLAN.json")
        self.assertEqual([x["page_module_id"] for x in changed["a_plus_layout"]["page_modules"]], order)
        self.assertEqual(changed["modules"][0]["module_id"], "a-plus-09")
        self.assertEqual(layout_errors(changed, plan_modules(self.root, changed)), [])
        for row in changed["modules"]:
            self.assertEqual(sha256(self.root / row["spec_path"]), hashes[row["module_id"]])
        manifest = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "handoff").stdout)
        self.assertEqual(manifest["page_modules"][0]["page_module_id"], "aplus-care")

    def test_approved_design_catalog_is_pinned_and_mutations_are_blocked(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve")
        original = (self.folder / "SET_PLAN.json").read_bytes()
        self.run_script("configure_design.py", "--set-id", "aplus", "configure", "--style-id", "warm_daily", "--framework-id", "DIRECT", "--rationale", "Rejected approved mutation", success=False)
        self.assertEqual((self.folder / "SET_PLAN.json").read_bytes(), original)
        catalog_path = self.folder / "DESIGN_PATTERNS.json"
        catalog = load_json(catalog_path)
        catalog["layouts"][0]["composition_rules"] = ["unexpected change"]
        write_json(catalog_path, catalog)
        result = self.run_script("set_runtime.py", "--set-id", "aplus", "prepare", success=False)
        self.assertIn("pinned design catalog changed", result.stderr)
        self.assertFalse((self.root / "runs").exists())

    def test_unknown_narrative_stage_is_rejected_before_approval(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        path = self.folder / "modules/a-plus-01.json"
        spec = load_json(path)
        spec["creative_brief"]["story_stage"] = "unplanned_stage"
        write_json(path, spec)
        result = self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve", success=False)
        self.assertIn("unknown layout/style/story stage", result.stdout)

    def test_new_draft_uses_adaptive_design_without_a_style_selection(self):
        plan = self.initialize()
        self.assertEqual(plan["design_system"]["mode"], "adaptive")
        self.assertNotIn("style_id", plan["design_system"])
        configured = json.loads(self.run_script("configure_design.py", "--set-id", "aplus", "configure",
                                             "--rationale", "Synthetic fixture: derive decisions from this product and task").stdout)
        self.assertEqual(configured["design_system"]["mode"], "adaptive")
        selected = json.loads(self.run_script("configure_design.py", "--set-id", "aplus", "select",
                                             "--module-id", "a-plus-01", "--layout-id", "adaptive",
                                             "--story-stage", "single_message").stdout)
        self.assertIsNone(selected["design_preview"])
        self.assertEqual(selected["layout_starting_points"], {})

    def test_adaptive_decisions_reach_generation_and_review_without_catalog_style(self):
        source = self.root / "commercial/sources/lighting.md"
        source.parent.mkdir(parents=True)
        source.write_text("Synthetic reference metadata; not real visual inspection")
        write_json(self.root / "commercial/source_manifest.json", {"sources": [
            {"source_id": "lighting", "path": "commercial/sources/lighting.md", "role": "STYLE_REFERENCE",
             "sha256": sha256(source), "source": "synthetic test fixture"}
        ]})
        plan = self.initialize()
        self.fill_for_approval(plan)
        plan["design_system"] = {"mode": "adaptive", "narrative_framework_id": "DIRECT", "rationale": "Synthetic product-specific task"}
        for row in plan["modules"]:
            path = self.root / row["spec_path"]
            spec = load_json(path)
            spec["creative_brief"].update(layout_id="adaptive", story_stage="single_message")
            if row["sequence"] == 1:
                spec["style_source_ids"] = ["lighting"]
                spec["creative_brief"].update(
                    design_adjustments={"lighting": "Grazing light shows the evidenced surface"},
                    reference_influences=[{"source_id": "lighting", "element": "surface lighting", "strength": "low",
                                           "reason": "Make the actual texture legible without importing the reference product"}])
            write_json(path, spec)
        write_json(self.folder / "SET_PLAN.json", plan)
        self.run_script("validate_set_plan.py", "--set-id", "aplus", "--approve")
        packet = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "prepare").stdout)
        self.assertIn("Grazing light", packet["prompt"])
        self.assertNotIn("editorial_daylight", packet["prompt"])
        contract = load_contract(self.root, self.root / packet["contract_path"])
        recipe = contract["design_recipe"]
        self.assertEqual(recipe["mode"], "adaptive")
        self.assertEqual(recipe["reference_influences"][0]["strength"], "low")
        self.assertNotIn("style_id", recipe["style"])
        self.write_final_candidate(packet)
        reviewed = json.loads(self.run_script("set_runtime.py", "--set-id", "aplus", "packet", "--phase", "review").stdout)
        self.assertEqual(reviewed["expected"]["design_recipe"], recipe)

    def test_adaptive_reference_influence_cannot_use_another_images_source(self):
        from design_store import resolve_design
        plan = self.initialize()
        self.fill_for_approval(plan)
        plan["design_system"] = {"mode": "adaptive", "narrative_framework_id": "DIRECT", "rationale": "Synthetic fixture"}
        module = plan_modules(self.root, plan)[0]
        module["creative_brief"].update(layout_id="adaptive", story_stage="single_message",
            reference_influences=[{"source_id": "unselected", "element": "lighting", "strength": "high", "reason": "fixture"}])
        with self.assertRaisesRegex(ValueError, "registered style source"):
            resolve_design(self.root, {**plan, "status": "APPROVED"}, module)

    def test_distinct_images_share_background_light_and_type_boundaries_in_generation_and_review(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        plan['design_system'] = {'mode': 'adaptive', 'narrative_framework_id': 'DIRECT', 'rationale': 'One set, varied image tasks'}
        plan['visual_system'].update(
            background='Light warm-neutral backgrounds; deep tones only as small accents',
            palette=['cream white', 'pale warm stone'],
            lighting='Soft warm-neutral light, open shadows and low-to-medium contrast',
            typography='One sans-serif family with the same heading/body hierarchy',
            forbidden_cues=['dark full background', 'cold blue grade', 'crushed black shadows'])
        surfaces = {'a-plus-01': 'Pale stone environment in the shared light range',
                    'a-plus-03': 'Cream fabric surface in the shared light range'}
        for row in plan['modules']:
            path = self.root / row['spec_path']
            spec = load_json(path)
            spec['creative_brief'].update(layout_id='adaptive', story_stage='single_message')
            if row['module_id'] in surfaces:
                spec['creative_brief']['design_adjustments'] = {'background': surfaces[row['module_id']]}
            write_json(path, spec)
        write_json(self.folder / 'SET_PLAN.json', plan)
        self.run_script('validate_set_plan.py', '--set-id', 'aplus', '--approve')
        for image_id, surface in surfaces.items():
            packet = json.loads(self.run_script('set_runtime.py', '--set-id', 'aplus', 'prepare', '--module-id', image_id).stdout)
            shared_line = next(x for x in packet['prompt'].splitlines() if x.startswith('Visual direction: '))
            self.assertEqual(json.loads(shared_line.removeprefix('Visual direction: ')), plan['visual_system'])
            contract = load_contract(self.root, self.root / packet['contract_path'])
            self.assertEqual(contract['design_recipe']['style']['task_adjustments'], {'background': surface})
            self.assertNotEqual(contract['generation_template']['template_id'], 'main_product')
            self.write_final_candidate(packet)
            reviewed = json.loads(self.run_script('set_runtime.py', '--set-id', 'aplus', 'packet', '--phase', 'review', '--module-id', image_id).stdout)
            self.assertEqual(reviewed['expected']['visual_system'], plan['visual_system'])
            self.assertIn('design_quality', reviewed['checks'])

    def test_adaptive_main_image_cannot_use_free_or_decorative_layout(self):
        self.run_script("init_visual_set.py", "--set-id", "main", "--deliverable", "gallery", "--count", "1")
        self.run_script("configure_design.py", "--set-id", "main", "configure", "--rationale", "Synthetic fixture")
        result = self.run_script("configure_design.py", "--set-id", "main", "select", "--module-id", "gallery-01",
                                 "--layout-id", "adaptive", "--story-stage", "single_message", success=False)
        self.assertIn("require main_clean", result.stderr)

    def test_raw_or_unprocessed_a_plus_cannot_enter_review_even_with_a_pass_label(self):
        plan = self.initialize()
        self.fill_for_approval(plan)
        self.run_script('validate_set_plan.py', '--set-id', 'aplus', '--approve')
        packet = json.loads(self.run_script('set_runtime.py', '--set-id', 'aplus', 'prepare').stdout)
        self.assertNotEqual(packet['raw_output_path'], packet['output_path'])
        image = Path(packet['output_path'])
        Image.new('RGB', (1536,1024), 'white').save(image)
        self.run_script('set_runtime.py', '--set-id', 'aplus', 'record', '--module-id', 'a-plus-01', '--decision', 'PENDING_REVIEW', success=False)
        self.run_script('set_runtime.py', '--set-id', 'aplus', 'packet', '--phase', 'review', success=False)
        Image.new('RGB', (1464,600), 'white').save(image)
        contract_path = self.root / packet['contract_path']
        contract = load_contract(self.root, contract_path)
        candidate = {'path': contract['output_path']}
        report = {'candidate_id': packet['candidate_id'], 'candidate_sha256': sha256(image), 'contract_sha256': sha256(contract_path),
                  'reviewer': 'synthetic fixture', 'inspection_method': 'VISUAL_INSPECTION', 'unresolved_items': [],
                  'checks': {key: {'status':'PASS','observation':'synthetic report'} for key in required_checks(contract)}}
        self.assertTrue(any('provenance' in e for e in qa_errors(self.root, contract, contract_path, candidate, report)))
        image.unlink()
        raw = Path(packet['raw_output_path'])
        Image.new('RGB', (1536,1024), 'white').save(raw)
        resumed = json.loads(self.run_script('set_runtime.py', '--set-id', 'aplus', 'prepare').stdout)
        self.assertEqual(resumed['phase'], 'postprocess')
        self.assertNotIn('prompt', resumed)
        self.write_final_candidate(packet)
        self.run_script('set_runtime.py', '--set-id', 'aplus', 'record', '--module-id', 'a-plus-01', '--decision', 'PENDING_REVIEW')
        self.run_script('set_runtime.py', '--set-id', 'aplus', 'packet', '--phase', 'review')


if __name__ == "__main__":
    unittest.main()
