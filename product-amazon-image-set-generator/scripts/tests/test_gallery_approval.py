"""Human approval binds the current opening candidates; no real visual QA here."""

import json
import unittest
import subprocess
import sys
from PIL import Image
from pathlib import Path

import test_a_plus_layout as fixtures
from set_common import load_json, write_json


class GalleryApprovalTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.APlusLayoutTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f = self.f
        f.run_script('init_visual_set.py', '--set-id', 'gallery', '--deliverable', 'gallery')
        f.folder = f.root / 'visual_sets/gallery'
        plan = load_json(f.folder / 'SET_PLAN.json')
        f.fill_for_approval(plan)
        f.run_script('validate_set_plan.py', '--set-id', 'gallery', '--approve')

    def runtime(self, *args, success=True):
        return self.f.run_script('set_runtime.py', '--set-id', 'gallery', *args, success=success)

    def generate(self, number):
        packet = json.loads(self.runtime('prepare', '--module-id', f'gallery-{number:02d}').stdout)
        Image.new('RGB', (160, 160), '#eb7221').save(packet['output_path'])
        self.runtime('record', '--module-id', packet['module_id'], '--decision', 'PENDING_REVIEW')
        return packet

    def accept(self, packet):
        f = self.f
        relative = f"qa/visual/{packet['candidate_id']}.json"
        script = Path(__file__).resolve().parents[3] / 'product-single-image-generator/scripts/candidate_qa.py'
        result = subprocess.run([sys.executable, '-B', str(script), str(f.root), '--contract',
                                 packet['contract_path'], '--report', relative, '--init'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path = f.root / relative
        report = load_json(path)
        report['reviewer'] = 'synthetic fixture, not real visual inspection'
        for check in report['checks'].values():
            check.update(status='PASS', observation='synthetic gate fixture')
        report['composition'].update(annotation_method='ASSISTANT_VISUAL_ESTIMATE',
                                     boundary_certainty='CLEAR', required_content='COMPLETE',
                                     product_regions=[{'label': 'synthetic product', 'box': [.1, .1, .9, .9]}])
        write_json(path, report)
        self.runtime('record', '--module-id', packet['module_id'], '--decision', 'ACCEPTED',
                     '--report', relative, '--human-reviewer', 'fixture user',
                     '--decision-reference', 'synthetic explicit approval of current pair')

    def test_no_approval_cannot_prepare_or_materialize_remainder(self):
        before = load_json(self.f.root / 'PRODUCT_STATE.json')['runs']
        result = self.runtime('prepare', '--module-id', 'gallery-03', success=False)
        self.assertIn('WAIT_FOR_GALLERY_OPENING_APPROVAL', result.stderr)
        self.f.run_script('materialize_module_contracts.py', '--set-id', 'gallery',
                          '--module-id', 'gallery-03', success=False)
        self.assertEqual(load_json(self.f.root / 'PRODUCT_STATE.json')['runs'], before)

    def test_both_outputs_are_produced_before_waiting_for_user(self):
        self.generate(1)
        next_work = json.loads(self.runtime('next-generation').stdout)
        self.assertEqual(next_work['current']['module_id'], 'gallery-02')
        self.generate(2)
        waiting = json.loads(self.runtime('next-generation').stdout)
        self.assertEqual(waiting['next_action'], 'WAIT_FOR_GALLERY_OPENING_APPROVAL')
        self.assertNotIn('current', waiting)
        self.assertEqual(waiting['opening_review']['required_skill'], 'product-single-image-generator')


    def test_only_both_current_human_approvals_unlock_remainder(self):
        first, second = self.generate(1), self.generate(2)
        self.accept(first)
        self.runtime('prepare', '--module-id', 'gallery-03', success=False)
        self.accept(second)
        ready = json.loads(self.runtime('next-generation').stdout)
        self.assertEqual(ready['current']['module_id'], 'gallery-03')
        self.assertTrue(ready['opening_review']['approved'])
        self.runtime('prepare', '--module-id', 'gallery-03')

    def test_changed_approved_image_relocks_even_existing_later_contract(self):
        first, second = self.generate(1), self.generate(2)
        self.accept(first)
        self.accept(second)
        later = json.loads(self.runtime('prepare', '--module-id', 'gallery-03').stdout)
        Path(first['output_path']).write_bytes(b'changed after approval')
        result = self.runtime('packet', '--module-id', 'gallery-03', success=False)
        self.assertIn('WAIT_FOR_GALLERY_OPENING_APPROVAL', result.stderr)
        self.runtime('prepare', '--module-id', 'gallery-03', success=False)
        script = Path(__file__).resolve().parents[3] / 'product-single-image-generator/scripts/validate_run_records.py'
        direct = subprocess.run([sys.executable, '-B', str(script), str(self.f.root), '--contract',
                                 later['contract_path'], '--ready-for-generation'], capture_output=True, text=True)
        self.assertNotEqual(direct.returncode, 0)
        self.assertIn('WAIT_FOR_GALLERY_OPENING_APPROVAL', direct.stdout + direct.stderr)

    def test_machine_pass_or_structure_only_status_is_not_pair_approval(self):
        first, second = self.generate(1), self.generate(2)
        self.accept(first)
        self.accept(second)
        path = self.f.root / 'PRODUCT_STATE.json'
        product = load_json(path)
        for candidate in product['candidates']:
            if candidate['candidate_id'] == second['candidate_id']:
                candidate['status'] = 'HUMAN_STRUCTURE_REVIEW_PASSED'
        write_json(path, product)
        self.runtime('prepare', '--module-id', 'gallery-03', success=False)
        for candidate in product['candidates']:
            if candidate['candidate_id'] == second['candidate_id']:
                candidate['status'] = 'ACCEPTED'
                candidate.pop('human_review', None)
        write_json(path, product)
        self.runtime('prepare', '--module-id', 'gallery-03', success=False)


    def test_rejected_opening_can_retry_but_never_unlock_remainder(self):
        first = self.generate(1)
        self.generate(2)
        self.runtime('record', '--module-id', first['module_id'], '--decision', 'REJECTED_VISUAL',
                     '--failure-code', 'LAYOUT')
        retry = json.loads(self.runtime('prepare', '--module-id', first['module_id'], '--retry',
                                        '--correction', 'Keep the product physically upright').stdout)
        self.assertEqual(retry['attempt'], 2)
        self.assertNotEqual(retry['candidate_id'], first['candidate_id'])
        self.runtime('prepare', '--module-id', 'gallery-03', success=False)

    def test_gate_is_only_for_marked_gallery_and_ids_cannot_select_other_images(self):
        from gallery_review import review_policy_errors, opening_review_status
        path = self.f.folder / 'SET_PLAN.json'
        plan = load_json(path)
        self.assertEqual(plan['gallery_opening_review']['image_ids'], ['gallery-01', 'gallery-02'])
        plan['gallery_opening_review']['image_ids'] = ['gallery-02', 'gallery-03']
        self.assertTrue(review_policy_errors(plan))
        plan.pop('gallery_opening_review')
        self.assertIsNone(opening_review_status(self.f.root, plan, {}, {}))
        self.assertEqual(review_policy_errors(plan), [])


    def test_a_plus_generation_is_not_blocked_by_gallery_approval(self):
        f = self.f
        f.run_script('init_visual_set.py', '--set-id', 'mixed', '--deliverable', 'both',
                     '--gallery-count', '3', '--a-plus-count', '1')
        f.folder = f.root / 'visual_sets/mixed'
        plan = load_json(f.folder / 'SET_PLAN.json')
        f.fill_for_approval(plan)
        f.run_script('validate_set_plan.py', '--set-id', 'mixed', '--approve')
        packet = json.loads(f.run_script('set_runtime.py', '--set-id', 'mixed', 'prepare',
                                         '--module-id', 'a-plus-01').stdout)
        self.assertEqual(packet['module_id'], 'a-plus-01')
        self.assertEqual(packet['phase'], 'generation')


if __name__ == '__main__':
    unittest.main()
