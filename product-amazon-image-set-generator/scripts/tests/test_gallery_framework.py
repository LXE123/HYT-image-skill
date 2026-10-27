"""Gallery initialization and state transport; synthetic data is not visual QA."""

import json
import unittest

import test_a_plus_layout as fixtures
import test_intake_handoff as intake_fixtures
from set_common import GALLERY_TARGET_IMAGES, default_modules, generation_mode_errors, load_json, plan_modules, write_json
from quality_rules import compile_prompt


class GalleryFrameworkTest(unittest.TestCase):
    def fixture(self):
        f = fixtures.APlusLayoutTest()
        f.setUp()
        self.addCleanup(f.doCleanups)
        return f

    def test_explicit_compact_nine_remains_an_editable_scaffold(self):
        modules = default_modules(9, 0)
        self.assertEqual([m['generation_template']['template_id'] for m in modules],
                         ['main_product'] * 2 + ['product_overview'] * 4 + ['lifestyle_simple'] * 3)
        self.assertTrue(all(m['output_requirements']['background'] == 'white' for m in modules[:2]))
        self.assertTrue(all(not m['quality_contract']['mechanism']['depicted'] for m in modules))
        self.assertTrue(all(not m['generation_template']['requires_structure'] for m in modules))
        self.assertTrue(all(m['copy'] == {'title': '', 'subtitle': '', 'labels': []} for m in modules[6:]))

    def test_complete_seed_separates_character_fit_variants_and_keeps_opening_and_lifestyles(self):
        modules = default_modules(GALLERY_TARGET_IMAGES, 0)
        self.assertEqual(len(modules), 11)
        self.assertEqual([m['generation_template']['template_id'] for m in modules[:2]], ['main_product'] * 2)
        jobs = {m.get('image_intent', {}).get('module_role'): m for m in modules if m.get('image_intent')}
        self.assertEqual(set(jobs), {'product_character', 'fit', 'variants'})
        self.assertEqual(jobs['fit']['generation_template']['template_id'], 'size_fit')
        self.assertEqual(jobs['variants']['generation_template']['template_id'], 'range_story')
        self.assertEqual(len({m['module_id'] for m in jobs.values()}), 3)
        self.assertEqual(sum(m['generation_template']['template_id'] == 'lifestyle_simple' for m in modules), 3)
        self.assertTrue(all(not m['quality_contract']['mechanism']['depicted'] for m in modules))
        # Eleven is not a cap, and additional drafts must not repeat the closing lifestyle.
        larger = default_modules(19, 0)
        self.assertEqual(len(larger), 19)
        self.assertEqual(len({m['module_id'] for m in larger}), 19)
        self.assertNotEqual(larger[-1]['target_view'], larger[-2]['target_view'])

    def test_complete_import_preserves_all_seventeen_tasks_without_seed_truncation(self):
        f = self.fixture()
        path, brief = f.write_ready_design_brief()
        roles = ['main', 'main', 'material', 'detail', 'product_character', 'fit', 'variants', 'operation',
                 'care', 'lifestyle', 'lifestyle', 'lifestyle', 'material', 'detail', 'fit', 'variants', 'product_character']
        brief['job'].update(channel='AMAZON_GALLERY', width=1600, height=1600, target_image_count=len(roles))
        brief['content_groups'] = []
        brief['modules'] = [
            {'image_id': f'complete-{i:02d}', 'role': role, 'buyer_question': f'Covered buyer question {i}',
             'must_show': [f'Actual required information {i}'], 'product_evidence_ids': ['own'], 'copy': []}
            for i, role in enumerate(roles, 1)]
        write_json(path, brief)
        f.run_script('init_visual_set.py', '--set-id', 'complete', '--design-input', str(path))
        plan = load_json(f.root / 'visual_sets/complete/SET_PLAN.json')
        tasks = plan_modules(f.root, plan)
        self.assertEqual(len(tasks), 17)
        self.assertEqual(plan['quantity_policy']['selected_counts']['AMAZON_GALLERY'], 17)
        self.assertEqual(plan['generation_mode'], 'standard')
        self.assertEqual(generation_mode_errors(plan), [])
        self.assertEqual([m['module_id'] for m in tasks], [m['image_id'] for m in brief['modules']])
        self.assertEqual([m['image_intent']['must_show'] for m in tasks], [m['must_show'] for m in brief['modules']])
        self.assertEqual([m['image_intent']['module_role'] for m in tasks], roles)
        self.assertEqual(plan['gallery_opening_review']['image_ids'], ['complete-01', 'complete-02'])
        # Dropping a task cannot be disguised as completion without an explicit count revision.
        plan['modules'].pop()
        self.assertTrue(generation_mode_errors(plan))

    def test_explicit_counts_and_expanded_scope_override_defaults(self):
        f = self.fixture()
        for name, args, expected in (
            ('seven', ['--deliverable', 'gallery', '--count', '7'], (7, 0)),
            ('mixed', ['--deliverable', 'both', '--gallery-count', '7'], (7, 13)),
            ('per-channel', ['--deliverable', 'both', '--count', '11'], (11, 11)),
            ('expanded', ['--deliverable', 'gallery', '--mode', 'expanded'], (36, 0)),
        ):
            f.run_script('init_visual_set.py', '--set-id', name, *args)
            plan = load_json(f.root / f'visual_sets/{name}/SET_PLAN.json')
            self.assertEqual(tuple(sum(m['channel'] == c for m in plan['modules'])
                                   for c in ('AMAZON_GALLERY', 'PREMIUM_A_PLUS')), expected)

    def test_new_coverage_default_does_not_expand_an_existing_nine_image_queue(self):
        f = self.fixture()
        f.run_script('init_visual_set.py', '--set-id', 'saved-nine', '--deliverable', 'gallery', '--count', '9')
        folder = f.root / 'visual_sets/saved-nine'
        before = {name: (folder / name).read_bytes() for name in ('SET_PLAN.json', 'SET_STATE.json')}
        f.run_script('init_visual_set.py', '--set-id', 'saved-nine', '--deliverable', 'gallery', success=False)
        for name, original in before.items():
            self.assertEqual((folder / name).read_bytes(), original)
        self.assertEqual(load_json(folder / 'SET_PLAN.json')['quantity_policy']['selected_counts']['AMAZON_GALLERY'], 9)

    def test_upright_pose_is_local_to_opening_pair_and_reaches_both_prompt_formats(self):
        modules = default_modules(9, 13)
        for i, module in enumerate(modules):
            composition = module['quality_contract']['layout']['composition']
            if i < 2:
                self.assertIn('standing upright', composition)
                self.assertIn('front view' if i == 0 else 'reverse view', composition)
                for prompt_format in (None, 'focused-v1'):
                    contract = {**module, 'references': [], 'prompt_format': prompt_format}
                    self.assertIn(composition, compile_prompt(contract))
            else:
                self.assertNotIn('standing upright', composition)
            # A pose must not be stored as an inherited product-identity rule.
            self.assertEqual(module['visual_invariants'], [])
            self.assertEqual(module['forbidden_changes'], [])

    def test_current_pose_override_and_free_display_layout_are_preserved(self):
        modules = default_modules(9, 0)
        for module, pose in ((modules[0], 'Explicitly requested flat-lay front display'),
                             (modules[5], 'Flat-lay colour comparison with all required variants')):
            module['quality_contract']['layout']['composition'] = pose
            contract = {**module, 'references': [], 'prompt_format': 'focused-v1'}
            prompt = compile_prompt(contract)
            self.assertIn(pose, prompt)
            self.assertNotIn('standing upright', prompt)
            self.assertFalse(module['generation_template']['requires_mechanism'])

    def test_parameters_and_current_presentation_reach_prompt_without_design_examples(self):
        f = self.fixture()
        intake = intake_fixtures.IntakeHandoffTest()
        intake.setUp()
        data = intake.data
        data['job'].update(channel='AMAZON_GALLERY', width=1600, height=1600,
                           scope='pilot', target_image_count=1)
        data['product']['facts'] = [{'fact_id': 'fit', 'text': 'Supported wrist range 150-210 mm', 'status': 'SUPPORTED'}]
        required = ['Show the actual product beside its wrist-range annotation',
                    'Keep 150-210 mm clearly associated with this product']
        data['modules'][0].update(image_id='fit-display', role='fit',
                                  buyer_question='Will it fit my wrist?', must_show=required,
                                  required_fact_ids=['fit'], product_evidence_ids=['own'],
                                  copy=[{'text': '150-210 mm', 'language': 'en', 'status': 'CURRENT', 'required_fact_ids': ['fit']}])
        data['raw_workbook'] = 'historical source discussion must stay archived'
        brief = intake_fixtures.EXPORT.compile_brief(data)
        source = f.root / 'DESIGN_INPUT.json'
        write_json(source, brief)
        f.run_script('init_visual_set.py', '--set-id', 'display', '--design-input', str(source))
        f.folder = f.root / 'visual_sets/display'
        plan = load_json(f.folder / 'SET_PLAN.json')
        f.fill_for_approval(plan)
        f.run_script('validate_set_plan.py', '--set-id', 'display', '--approve')
        packet = json.loads(f.run_script('set_runtime.py', '--set-id', 'display', 'prepare', '--module-id', 'fit-display').stdout)
        spec = plan_modules(f.root, plan)[0]
        self.assertEqual(spec['image_intent']['must_show'], required)
        self.assertEqual(spec['pose_references'], [])
        self.assertEqual(spec['style_source_ids'], [])
        for requirement in required:
            self.assertIn(requirement, packet['prompt'])
        self.assertIn('150-210 mm', packet['prompt'])
        self.assertNotIn('historical source discussion', packet['prompt'])


if __name__ == '__main__':
    unittest.main()
