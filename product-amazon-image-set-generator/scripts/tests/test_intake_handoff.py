"""Field-boundary tests, not AI semantic parsing or visual generation tests."""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / 'product-image-project-builder/scripts/export_design_brief.py'
SPEC = importlib.util.spec_from_file_location('export_design_brief', SCRIPT)
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


class IntakeHandoffTest(unittest.TestCase):
    def setUp(self):
        self.data = {
            'schema_version': 1,
            'job': {'channel': 'PREMIUM_A_PLUS', 'language': 'en', 'width': 1464, 'height': 600},
            'product': {'name': 'Evidence-grounded product', 'sellable_scope': 'band only', 'facts': [
                {'fact_id': 'material', 'text': 'Submitted nylon specification', 'status': 'SUPPORTED'},
                {'fact_id': 'fit', 'text': 'Unverified size claim', 'status': 'UNVERIFIED'},
            ]},
            'audience': 'People seeking everyday wearable accessories',
            'brand_rules': [],
            'modules': [{
                'image_id': 'material-01', 'role': 'material', 'buyer_question': 'What is the material?',
                'must_show': ['Readable actual texture and product relationship'],
                'required_fact_ids': ['material'], 'product_evidence_ids': ['photo-01'],
                'copy': [{'text': 'Nylon texture', 'language': 'en', 'status': 'CURRENT', 'required_fact_ids': ['material']}],
            }],
        }

    def test_old_visuals_and_nested_metadata_do_not_cross_handoff(self):
        self.data['raw_workbook'] = 'original.xlsx'
        self.data['legacy_presentations'] = ['sky blue', 'alternating panels']
        self.data['job']['old_canvas'] = '600x450'
        self.data['product']['facts'][0]['source_picture_caption'] = 'old composition'
        self.data['modules'][0].update({'layout': 'left text right product', 'style_source_ids': ['old-example'], 'raw_image_path': 'old.png'})
        result = EXPORT.compile_brief(self.data)
        self.assertEqual(set(result), {'schema_version', 'job', 'product', 'audience', 'brand_rules', 'modules', 'deferred_modules'})
        self.assertEqual(result['product']['facts'], [{'fact_id': 'material', 'text': 'Submitted nylon specification'}])
        self.assertEqual(set(result['modules'][0]), {'image_id', 'role', 'buyer_question', 'must_show', 'required_fact_ids', 'product_evidence_ids', 'copy'})
        self.assertEqual(result['job'], {'channel': 'PREMIUM_A_PLUS', 'language': 'en', 'width': 1464, 'height': 600})

    def grouped_intake(self, child_counts):
        self.data['job'].update(scope='full_set', target_image_count=13)
        if not hasattr(self, 'image_template'):
            self.image_template = copy.deepcopy(self.data['modules'][0])
        original = self.image_template
        self.data['content_groups'], self.data['modules'] = [], []
        for number, count in enumerate(child_counts, 1):
            group_id = f'group-{number}'
            group = copy.deepcopy(original)
            group.pop('image_id')
            group['group_id'] = group_id
            group['legacy_layout'] = 'old composition must not cross boundary'
            self.data['content_groups'].append(group)
            for child in range(count):
                task = copy.deepcopy(original)
                task.update(image_id=f'image-{number}-{child}', content_group_id=group_id)
                self.data['modules'].append(task)

    def test_seven_group_descriptions_do_not_become_seven_completed_images(self):
        self.grouped_intake([0] * 7)
        result = EXPORT.compile_brief(self.data)
        self.assertEqual(result['job']['target_image_count'], 13)
        self.assertEqual(len(result['content_groups']), 7)
        self.assertEqual(result['modules'], [])
        self.assertNotIn('image_plan', result)
        self.assertNotIn('old composition', json.dumps(result))
        self.grouped_intake([1] * 7)
        result = EXPORT.compile_brief(self.data)
        self.assertEqual(len(result['modules']), 7)
        self.assertEqual(result['job']['target_image_count'], 13)

    def test_seven_groups_can_decompose_to_nine_or_thirteen_distinct_tasks(self):
        for counts in ([1, 1, 2, 2, 1, 1, 1], [1, 2, 3, 4, 1, 1, 1]):
            self.grouped_intake(counts)
            self.data['job']['target_image_count'] = sum(counts)
            result = EXPORT.compile_brief(self.data)
            self.assertEqual(len(result['content_groups']), 7)
            self.assertEqual(len(result['modules']), result['job']['target_image_count'])
            self.assertEqual(len({x['image_id'] for x in result['modules']}), sum(counts))
            self.assertEqual([x['content_group_id'] for x in result['modules']].count('group-3'), counts[2])

    def test_count_alone_does_not_cover_an_unmapped_content_group(self):
        self.grouped_intake([1, 2, 3, 4, 1, 1, 1])
        for task in self.data['modules']:
            task['content_group_id'] = 'group-1'
        result = EXPORT.compile_brief(self.data)
        assigned = {x['content_group_id'] for x in result['modules']}
        self.assertEqual(len({x['group_id'] for x in result['content_groups']} - assigned), 6)

    def test_pilot_count_and_deferred_tasks_preserve_scope_and_total(self):
        self.grouped_intake([1, 1, 1])
        self.data['job'].update(scope='pilot', target_image_count=3)
        self.data['modules'][-1]['required_fact_ids'] = ['fit']
        result = EXPORT.compile_brief(self.data)
        self.assertEqual(result['job']['target_image_count'], 3)
        self.assertEqual(len(result['modules']) + len(result['deferred_modules']), 3)
        self.assertEqual(len(result['modules']), 2)
        self.assertEqual(result['deferred_modules'][0]['content_group_id'], 'group-3')

    def test_unknown_group_and_invalid_target_are_rejected(self):
        self.grouped_intake([1])
        self.data['modules'][0]['content_group_id'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'registered content_group_id'):
            EXPORT.compile_brief(self.data)
        self.data['modules'][0]['content_group_id'] = 'group-1'
        self.data['job']['target_image_count'] = True
        with self.assertRaisesRegex(ValueError, 'target_image_count'):
            EXPORT.compile_brief(self.data)

    def test_explicit_single_scope_defaults_to_one_instead_of_set_target(self):
        self.data['job']['scope'] = 'single'
        result = EXPORT.compile_brief(self.data)
        self.assertEqual(result['job']['target_image_count'], 1)
        self.assertEqual(len(result['modules']), 1)

    def test_product_intake_does_not_choose_the_set_planners_default_count(self):
        self.data['job']['scope'] = 'full_set'
        result = EXPORT.compile_brief(self.data)
        self.assertNotIn('target_image_count', result['job'])

    def test_unsupported_requirement_defers_only_affected_task(self):
        task = copy.deepcopy(self.data['modules'][0])
        task.update({'image_id': 'fit-01', 'role': 'fit', 'buyer_question': 'Which version fits?', 'required_fact_ids': ['fit']})
        self.data['modules'].append(task)
        result = EXPORT.compile_brief(self.data)
        self.assertEqual([x['image_id'] for x in result['modules']], ['material-01'])
        self.assertEqual(result['deferred_modules'], [{'image_id': 'fit-01', 'role': 'fit', 'buyer_question': 'Which version fits?', 'reason': 'MISSING_SUPPORTED_FACTS'}])
        self.assertNotIn('Unverified size claim', json.dumps(result))

    def test_old_language_held_copy_and_unsupported_claims_are_not_used(self):
        self.data['modules'][0]['copy'].extend([
            {'text': 'Old text', 'language': 'en', 'status': 'SUPERSEDED'},
            {'text': 'Unresolved version', 'language': 'en', 'status': 'HOLD'},
            {'text': 'Andere Sprache', 'language': 'de', 'status': 'CURRENT'},
            {'text': 'Unverified size claim', 'language': 'en', 'status': 'CURRENT', 'required_fact_ids': ['fit']},
        ])
        self.assertEqual(EXPORT.compile_brief(self.data)['modules'][0]['copy'], [
            {'text': 'Nylon texture', 'language': 'en', 'required_fact_ids': ['material']},
        ])

    def test_only_current_required_brand_rule_is_forwarded(self):
        self.data['brand_rules'] = [
            {'text': 'Current logo clearspace', 'status': 'CURRENT_REQUIRED', 'raw_path': 'brand.pdf'},
            {'text': 'Old sky blue', 'status': 'LEGACY_SUGGESTION'},
        ]
        self.assertEqual(EXPORT.compile_brief(self.data)['brand_rules'], ['Current logo clearspace'])

    def test_german_source_keeps_exact_characters_whitespace_and_language(self):
        self.data['job']['language'] = 'de'
        self.data['copy_policy_version'] = 1
        original = '  Atmungsaktiv & hautfreundlich.\nFür 38/40/41 mm – Größe wählen!  '
        self.data['modules'][0]['copy'] = [{'text': original, 'language': 'de', 'source_text': original, 'source_language': 'de', 'status': 'CURRENT'}]
        result = EXPORT.compile_brief(self.data)
        self.assertEqual(result['modules'][0]['copy'], [{'text': original, 'language': 'de', 'required_fact_ids': []}])

    def test_unspecified_language_preserves_separate_source_versions(self):
        del self.data['job']['language']
        self.data['modules'][0]['copy'].append({'text': 'Weiches Nylon', 'language': 'de', 'status': 'CURRENT'})
        result = EXPORT.compile_brief(self.data)
        self.assertEqual(result['job']['language'], 'source')
        self.assertEqual([x['language'] for x in result['modules'][0]['copy']], ['en', 'de'])

    def test_new_copy_policy_blocks_silent_translation_or_rewrite(self):
        self.data['job']['language'] = 'source'
        self.data['copy_policy_version'] = 1
        wording = {'text': '柔软尼龙', 'language': 'zh', 'source_text': 'Weiches Nylon', 'source_language': 'de', 'status': 'CURRENT'}
        self.data['modules'][0]['copy'] = [wording]
        with self.assertRaisesRegex(ValueError, 'without explicit'):
            EXPORT.compile_brief(self.data)
        wording['translation_authorized'] = True
        self.assertEqual(EXPORT.compile_brief(self.data)['modules'][0]['copy'][0]['text'], '柔软尼龙')

    def test_new_copy_policy_requires_recorded_source_wording(self):
        self.data['copy_policy_version'] = 1
        with self.assertRaisesRegex(ValueError, 'source_text'):
            EXPORT.compile_brief(self.data)

    def test_both_generator_prompt_formats_keep_exact_german_copy(self):
        single = SCRIPT.parents[2] / 'product-single-image-generator/scripts'
        sys.path.insert(0, str(single))
        from quality_rules import compile_prompt
        original = 'Bequemes, dehnbares Nylon Armband'
        contract = {
            'target_view': 'material_detail', 'generation_template': {'prompt_rules': []},
            'quality_contract': {}, 'references': [], 'output_requirements': {},
            'copy': {'title': original}, 'image_intent': {'buyer_question': '中文分析：解释材质特点'},
        }
        for prompt_format in ('focused-v1', 'legacy'):
            contract['prompt_format'] = prompt_format
            prompt = compile_prompt(contract)
            self.assertIn(original, prompt)
            prefix = 'Exact copy: ' if prompt_format == 'focused-v1' else 'Approved copy only: '
            copy_line = next(x for x in prompt.splitlines() if x.startswith(prefix))
            self.assertEqual(json.loads(copy_line[len(prefix):]), {'title': original})
            self.assertIn('Do not translate', prompt)

    def test_duplicate_task_or_fact_cannot_silently_replace_another(self):
        self.data['modules'].append(copy.deepcopy(self.data['modules'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate image_id'):
            EXPORT.compile_brief(self.data)
        self.data['modules'].pop()
        self.data['product']['facts'].append(copy.deepcopy(self.data['product']['facts'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate fact_id'):
            EXPORT.compile_brief(self.data)

    def test_copy_only_dependency_does_not_defer_visual_task_or_enter_visual_facts(self):
        child = self.data['modules'][0]
        child['sales_task'] = 'Explain material with a supplied supporting line'
        child['copy'].append({'text': 'Unverified compatibility', 'language': 'en', 'status': 'CURRENT', 'required_fact_ids': ['fit']})
        result = EXPORT.compile_brief(self.data)
        self.assertEqual(result['deferred_modules'], [])
        exported = result['modules'][0]
        self.assertEqual(exported['sales_task'], child['sales_task'])
        self.assertEqual(exported['required_fact_ids'], ['material'])
        self.assertEqual([x['text'] for x in exported['copy']], ['Nylon texture'])
        self.assertEqual(child['copy'][-1]['text'], 'Unverified compatibility')

    def test_a_plus_export_requires_only_desktop_canvas_without_changing_gallery(self):
        self.data['job'].update(width=600, height=450)
        with self.assertRaisesRegex(ValueError, 'only 1464x600'):
            EXPORT.compile_brief(self.data)
        self.data['job']['channel'] = 'AMAZON_GALLERY'
        self.assertEqual(EXPORT.compile_brief(self.data)['job']['width'], 600)

    def test_handoff_export_preserves_original_and_does_not_claim_isolation(self):
        with tempfile.TemporaryDirectory(prefix='intake-handoff-') as directory:
            root = Path(directory)
            src, out = root/'intake.json', root/'DESIGN_INPUT.json'
            original = json.dumps(self.data)
            src.write_text(original)
            run = subprocess.run([sys.executable, str(SCRIPT), str(src), '--output', str(out)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(src.read_text(), original)
            self.assertEqual(json.loads(out.read_text()), EXPORT.compile_brief(self.data))
            self.assertIs(json.loads(run.stdout)['context_isolation_verified'], False)
            blocked = subprocess.run([sys.executable, str(SCRIPT), str(src), '--output', str(src)], capture_output=True, text=True)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertEqual(src.read_text(), original)


if __name__ == '__main__':
    unittest.main()
