"""Review binding, task-specific geometry and optional annotated real-image cases.

No object detector or image generator is called. Synthetic fixtures are not visual acceptance.
"""
import copy
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SINGLE = Path(__file__).resolve().parents[3] / 'product-single-image-generator/scripts'
sys.path.insert(0, str(SINGLE))
from PIL import Image
import candidate_qa
import quality_rules
from quality_rules import composition_result, digest, required_checks, review_binding, review_status



from project_store import read_json as store_read, write_json as store_write, read_bytes as store_bytes

class ReviewReuseTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='composition-review-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ('reference.png', 'candidate.png', 'comparison.png'):
            Image.new('RGB', (96, 64), 'white').save(self.root/name)
        self.contract = {'candidate_id': 'candidate', 'target_view': 'detail', 'output_path': 'candidate.png',
                         'references': [{'path': 'reference.png', 'role': 'PRODUCT_EVIDENCE'}],
                         'quality_contract': {'layout': {'product_box': [.5,.1,.95,.9], 'copy_box': [.02,.1,.4,.9]}},
                         'copy': {'title': 'Detail'}, 'output_requirements': {'format': 'PNG'}}
        self.path = self.root/'contract.json'
        store_write(self.path, self.contract)
        store_write(self.root/'PRODUCT_STATE.json', {'candidates': []})
        self.candidate = {'candidate_id': 'candidate', 'path': 'candidate.png'}
        self.report = {'schema_version': 2, 'candidate_id': 'candidate', 'candidate_sha256': digest(self.root/'candidate.png'),
                       'contract_sha256': digest(self.path), 'inspection_method': 'VISUAL_INSPECTION',
                       'reviewer': 'synthetic regression fixture', 'comparison_images': [], 'unresolved_items': [],
                       'checks': {key: {'status': 'PASS', 'observation': 'synthetic recorded observation'} for key in required_checks(self.contract)}}
        self.report['review_binding'] = review_binding(self.root, self.contract, self.report['candidate_sha256'])
        self.report['composition'] = {'coordinate_space': 'FINAL_IMAGE', 'image_sha256': self.report['candidate_sha256'],
                                      'annotation_method': 'ASSISTANT_VISUAL_ESTIMATE', 'boundary_certainty': 'CLEAR',
                                      'required_content': 'COMPLETE',
                                      'product_regions': [{'label': 'assigned detail', 'box': [.55,.2,.9,.8]}],
                                      'copy_regions': [{'label': 'title', 'box': [.05,.2,.35,.3]}], 'protected_regions': []}

    def status(self):
        return review_status(self.root, self.contract, self.path, self.candidate, self.report)

    def test_unchanged_report_reuses_pass_without_changing_files(self):
        before = {p: store_bytes(p) for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(self.status()['status'], 'PASS')
        self.assertEqual(self.status()['execution'], 'REUSE')
        self.assertEqual(self.status()['next_action'], 'AWAIT_REAL_HUMAN_DECISION')
        self.assertEqual(before, {p: store_bytes(p) for p in self.root.iterdir() if p.is_file()})

    def test_candidate_reference_contract_and_rule_changes_invalidate(self):
        for changed in ('candidate.png', 'reference.png', 'copy', 'rules'):
            with self.subTest(changed=changed):
                report = copy.deepcopy(self.report)
                contract = copy.deepcopy(self.contract)
                files = {p: store_bytes(p) for p in self.root.iterdir() if p.is_file()}
                if changed.endswith('.png'):
                    Image.new('RGB', (96,64), 'black').save(self.root/changed)
                elif changed == 'copy':
                    self.contract['copy']['title'] = 'New lettering'
                with patch.object(quality_rules, 'VISUAL_REVIEW_VERSION', 2 if changed == 'rules' else 1):
                    self.assertEqual(self.status()['execution'], 'INVALIDATED')
                    self.assertNotEqual(self.status()['status'], 'PASS')
                self.report, self.contract = report, contract
                for path, content in files.items():
                    path.write_bytes(content)

    def test_unrelated_file_and_queue_fields_do_not_invalidate(self):
        (self.root/'unrelated.txt').write_text('new unrelated upload')
        self.contract['queue_status'] = 'NEXT_IMAGE'
        self.assertEqual(self.status()['status'], 'PASS')

    def test_actual_comparison_image_is_bound(self):
        self.report['comparison_images'] = [{'path': 'comparison.png'}]
        self.report['review_binding'] = review_binding(self.root, self.contract, self.report['candidate_sha256'], self.report['comparison_images'])
        self.assertEqual(self.status()['status'], 'PASS')
        Image.new('RGB', (96,64), 'black').save(self.root/'comparison.png')
        self.assertEqual(self.status()['execution'], 'INVALIDATED')

    def test_claim_basis_change_invalidates_and_missing_output_requests_recovery(self):
        self.contract['claim_decisions'] = [{'claim_id': 'claim', 'status': 'UNVERIFIED'}]
        self.assertEqual(self.status()['execution'], 'INVALIDATED')
        del self.contract['claim_decisions']
        (self.root/'candidate.png').unlink()
        result = self.status()
        self.assertEqual(result['execution'], 'INVALIDATED')
        self.assertEqual(result['next_action'], 'RECOVER_EXISTING_OUTPUT')

    def test_uncertain_region_never_passes_and_reuses_request_for_review(self):
        self.report['composition']['boundary_certainty'] = 'UNCERTAIN'
        result = self.status()
        self.assertEqual(result['status'], 'REVIEW_REQUIRED')
        self.assertEqual(result['execution'], 'REUSE')
        self.assertEqual(result['next_action'], 'RESOLVE_REVIEW_OR_REQUEST_HUMAN')

    def test_observations_must_belong_to_final_image(self):
        for key, value in [('image_sha256', 'other-image'), ('coordinate_space', 'RAW_IMAGE')]:
            with self.subTest(key=key):
                observed = copy.deepcopy(self.report['composition'])
                observed[key] = value
                self.assertEqual(composition_result(self.contract, observed, self.report['candidate_sha256'])['status'], 'REVIEW_REQUIRED')

    def test_normalized_regions_reject_nan_bool_and_reversed_boxes(self):
        for box in ([0,0,float('nan'),1], [False,0,1,1], [0,.7,1,.2], [-.1,0,1,1]):
            with self.subTest(box=box):
                observed = copy.deepcopy(self.report['composition'])
                observed['product_regions'][0]['box'] = box
                self.assertEqual(composition_result(self.contract, observed, self.report['candidate_sha256'])['status'], 'REVIEW_REQUIRED')

    def test_explicit_exclusive_copy_area_fails_but_intentional_overlap_is_allowed(self):
        observed = self.report['composition']
        observed['product_regions'][0]['box'] = [.1,.1,.9,.9]
        self.assertEqual(composition_result(self.contract, observed, self.report['candidate_sha256'])['status'], 'PASS')
        self.contract['quality_contract']['layout']['review_constraints'] = {'product_clear_of_copy': True}
        result = composition_result(self.contract, observed, self.report['candidate_sha256'])
        self.assertEqual(result['status'], 'FAIL')
        self.assertGreater(result['metrics']['product_overlap_with_copy_target'][0], 0)

    def test_missing_or_out_of_target_regions_cannot_pass_explicit_constraints(self):
        self.contract['quality_contract']['layout']['review_constraints'] = {'product_within_target': True, 'copy_within_target': True}
        self.assertEqual(composition_result(self.contract, self.report['composition'], self.report['candidate_sha256'])['status'], 'PASS')
        self.report['composition']['product_regions'][0]['box'] = [.1,.1,.9,.9]
        self.assertEqual(composition_result(self.contract, self.report['composition'], self.report['candidate_sha256'])['status'], 'FAIL')
        self.report['composition']['product_regions'] = []
        self.assertEqual(composition_result(self.contract, self.report['composition'], self.report['candidate_sha256'])['status'], 'REVIEW_REQUIRED')

    def test_detail_and_small_worn_product_have_no_universal_area_threshold(self):
        self.report['composition']['product_regions'][0]['box'] = [.6,.7,.62,.73]
        self.assertEqual(self.status()['status'], 'PASS')
        self.report['composition']['required_content'] = 'INCOMPLETE'
        self.assertEqual(self.status()['status'], 'FAIL')

    def test_saved_failure_is_reused_as_failure_not_repeated_inspection(self):
        self.report['checks']['structure_topology'] = {'status': 'FAIL', 'observation': 'synthetic missing component'}
        result = self.status()
        self.assertEqual(result['execution'], 'REUSE')
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['next_action'], 'CORRECT_OR_REPLAN_CURRENT_IMAGE')

    def test_incomplete_and_legacy_reports_are_not_automatic_passes(self):
        self.report['checks']['layout_output']['status'] = 'NOT_REVIEWED'
        self.assertEqual(self.status()['execution'], 'REVIEW')
        self.report['schema_version'] = 1
        self.assertEqual(self.status()['execution'], 'INVALIDATED')

    def test_cli_status_is_read_only_and_does_not_repeat_export_check(self):
        folder = self.root/'qa/visual'
        folder.mkdir(parents=True)
        store_write(folder/'report.json', self.report)
        before = {p: store_bytes(p) for p in self.root.rglob('*') if p.is_file() and 'runtime' not in p.relative_to(self.root).parts}
        args = ['candidate_qa.py', str(self.root), '--contract', 'contract.json', '--report', 'qa/visual/report.json', '--status']
        with patch.object(sys, 'argv', args), patch.object(candidate_qa, 'export_errors', side_effect=AssertionError('duplicate export check')):
            with patch.object(quality_rules, 'export_errors', wraps=quality_rules.export_errors) as export:
                with redirect_stdout(StringIO()):
                    self.assertEqual(candidate_qa.main(), 0)
                self.assertEqual(export.call_count, 1)
        self.assertEqual(before, {p: store_bytes(p) for p in self.root.rglob('*') if p.is_file() and 'runtime' not in p.relative_to(self.root).parts})


@unittest.skipUnless(os.environ.get('PRODUCT_COMPOSITION_BENCHMARK'), 'real-image benchmark path not supplied; no real-image result claimed')
class RealCompositionBenchmarkTest(unittest.TestCase):
    def test_annotated_real_images_and_declared_derived_cases(self):
        manifest_path = Path(os.environ['PRODUCT_COMPOSITION_BENCHMARK'])
        manifest = store_read(manifest_path)
        self.assertIsInstance(manifest['human_verified'], bool)
        for case in manifest['cases']:
            with self.subTest(case=case['id']):
                image_path = manifest_path.parent/case['image_path']
                self.assertEqual(digest(image_path), case['image_sha256'])
                with Image.open(image_path) as image:
                    image.load()
                    canvas = 'PASS' if image.size == (1464,600) else 'FAIL'
                self.assertEqual(canvas, case['expected_canvas'])
                result = composition_result(case['contract'], case['composition'], digest(image_path))
                self.assertEqual(result['status'], case['expected_composition'])

    def test_source_crop_guard_against_the_same_annotated_cases(self):
        from finalize_a_plus_image import assess_crop
        manifest_path = Path(os.environ['PRODUCT_COMPOSITION_BENCHMARK'])
        manifest = store_read(manifest_path)
        for case in manifest['cases']:
            with self.subTest(case=case['id']):
                image_path = manifest_path.parent/case['image_path']
                observed = copy.deepcopy(case['composition'])
                observed['coordinate_space'] = 'SOURCE_IMAGE'
                report = {'phase': 'SOURCE_IMAGE', 'candidate_sha256': digest(image_path), 'composition': observed,
                          'reviewed_crop_box': [0,0,1,1], 'inspection_method': 'VISUAL_INSPECTION',
                          'reviewer': 'assistant benchmark annotation, pending human confirmation',
                          'checks': {key: {'status': 'PASS', 'observation': 'exercise the declared benchmark crop only'} for key in ('layout_output','design_quality')}}
                with Image.open(image_path) as image:
                    result = assess_crop(image.size, digest(image_path), case['contract'], report)
                self.assertEqual(result['status'], case['expected_composition'])


if __name__ == '__main__':
    unittest.main()
