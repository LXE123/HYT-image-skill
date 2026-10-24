"""State transfer tests with generic synthetic structures; no claimed pixel accuracy."""
import copy
import json
from pathlib import Path
import sys
import unittest

import test_a_plus_layout as fixtures
from set_common import load_json, sha256, write_json
from context_store import load_contract
from quality_rules import focused_prompt, compile_prompt, observation_errors, qa_errors, review_status, review_binding, required_checks
from structure_state import dependency_errors, structure_requirements, value_hash
from revise_structure_state import apply_change


class StructureStateTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.APlusLayoutTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.root
        self.old = copy.deepcopy(self.f.state['identity_lockset']['locks'][0])

    def delta(self, status='LOCKED'):
        new = {**self.old, 'fact': 'A recessed surface belongs to the inner panel', 'status': status,
               'evidence_paths': ['input/own-product.png'],
               'relations': [{'relation_id': 'surface', 'subject': 'recess', 'predicate': 'belongs to',
                              'object': 'inner panel', 'evidence_paths': ['input/own-product.png']}]}
        return {'reason': 'Observed source detail corrects an incomplete surface interpretation',
                'updates': [{'lock_id': 'identity', 'expected_lock_sha256': value_hash(self.old), 'replacement': new}]}

    def apply(self, change=None):
        return apply_change(self.root, change or self.delta(), sha256(self.root/'PRODUCT_STATE.json'))

    def test_revision_replaces_current_fact_and_retains_unrelated_state(self):
        state = load_json(self.root/'PRODUCT_STATE.json')
        state['candidates'] = [{'candidate_id': 'history', 'status': 'ACCEPTED'}]
        write_json(self.root/'PRODUCT_STATE.json', state)
        result = self.apply()
        new = load_json(self.root/'PRODUCT_STATE.json')
        self.assertEqual(result['lockset_version'], 2)
        self.assertEqual(new['candidates'], state['candidates'])
        self.assertNotEqual(new['identity_lockset']['locks'][0]['fact'], self.old['fact'])
        self.assertTrue(dependency_errors(new, ['identity'], [self.old]))
        self.assertFalse(result['visual_acceptance'])

    def test_stale_delta_and_stale_state_do_not_write(self):
        before = (self.root/'PRODUCT_STATE.json').read_bytes()
        with self.assertRaises(ValueError):
            apply_change(self.root, self.delta(), 'wrong')
        bad = self.delta(); bad['updates'][0]['expected_lock_sha256'] = 'wrong'
        with self.assertRaises(ValueError): self.apply(bad)
        self.assertEqual(before, (self.root/'PRODUCT_STATE.json').read_bytes())

    def test_unregistered_or_changed_evidence_cannot_become_current_truth(self):
        for path in ['candidates/generated.png', '../outside.png']:
            bad = self.delta();bad['updates'][0]['replacement']['evidence_paths'] = [path]
            with self.assertRaises(ValueError): self.apply(bad)
        (self.root/'input/own-product.png').write_bytes(b'changed evidence')
        with self.assertRaises(ValueError): self.apply()

    def test_unresolved_revision_is_not_a_confirmed_fact(self):
        self.apply(self.delta('REVIEW_REQUIRED'))
        state = load_json(self.root/'PRODUCT_STATE.json')
        self.assertTrue(dependency_errors(state, ['identity'], state['identity_lockset']['locks']))

    def test_only_current_view_relations_enter_prompt_and_individual_qa(self):
        lock = self.delta()['updates'][0]['replacement']
        lock['relations'][0]['views'] = ['rear']
        contract = {'target_view': 'rear', 'resolved_identity_locks': [lock], 'generation_template': {'prompt_rules': []}, 'quality_contract': {}}
        self.assertIn('inner panel', focused_prompt(contract))
        self.assertTrue(observation_errors(contract, {'checks': {'structure_topology': {'status': 'PASS'}}}))
        report = {'structure_observations': {'identity:surface': {'status': 'PASS', 'observation': 'Fixture identifies the assigned recessed surface'}}}
        self.assertFalse(observation_errors(contract, report))
        report['structure_observations']['identity:surface']['status'] = 'REVIEW_REQUIRED'
        self.assertTrue(observation_errors(contract, report))
        contract['target_view'] = 'front'
        self.assertEqual(structure_requirements(contract), {})
        self.assertNotIn('Current-view structure relations', focused_prompt(contract))
        contract.update(references=[], output_requirements={})
        self.assertNotIn('Current-view structure relations', compile_prompt(contract))
        contract['target_view'] = 'rear'
        self.assertIn('Current-view structure relations', compile_prompt(contract))

    def test_changed_dependency_blocks_only_affected_set_tasks(self):
        other = {**self.old, 'lock_id': 'other', 'fact': 'Unrelated outer profile'}
        self.f.state['identity_lockset']['locks'].append(other)
        write_json(self.root/'PRODUCT_STATE.json', self.f.state)
        plan = self.f.initialize();self.f.fill_for_approval(plan)
        spec_path = self.root/plan['modules'][1]['spec_path']
        spec = load_json(spec_path);spec['required_lock_ids'] = ['other']
        for check in spec['quality_contract']['structure_checks']: check['lock_ids'] = ['other']
        write_json(spec_path,spec)
        self.f.run_script('validate_set_plan.py','--set-id','aplus','--approve')
        plan_bytes = (self.f.folder/'SET_PLAN.json').read_bytes()
        self.apply()
        result = json.loads(self.f.run_script('set_runtime.py','--set-id','aplus','next-generation').stdout)
        self.assertEqual(result['current']['module_id'], 'a-plus-02')
        packet = json.loads(self.f.run_script('set_runtime.py','--set-id','aplus','prepare','--module-id','a-plus-02').stdout)
        self.assertIn('Unrelated outer profile', packet['prompt'])
        self.assertNotIn('inner panel', packet['prompt'])
        self.f.run_script('set_runtime.py','--set-id','aplus','prepare','--module-id','a-plus-01', success=False)
        self.assertEqual(plan_bytes, (self.f.folder/'SET_PLAN.json').read_bytes())
        rows = load_json(self.f.folder/'SET_STATE.json')['modules']
        self.assertEqual(rows[0]['status'], 'BLOCKED')
        self.assertNotEqual(rows[1]['status'], 'BLOCKED')

    def test_saved_review_survives_unrelated_addition_but_not_affected_revision(self):
        contract = {'candidate_id': 'fixture', 'target_view': 'front', 'identity_lockset_version': 1,
                    'required_lock_ids': ['identity'], 'resolved_identity_locks': [self.old],
                    'references': [], 'quality_contract': {}, 'generation_template': {}, 'output_requirements': {}}
        path = self.root/'contract.json';write_json(path,contract)
        candidate = {'candidate_id': 'fixture', 'path': 'input/own-product.png'}
        image_hash = sha256(self.root/candidate['path'])
        report = {'schema_version': 2, 'candidate_id': 'fixture', 'candidate_sha256': image_hash,
                  'contract_sha256': sha256(path), 'review_binding': review_binding(self.root,contract,image_hash),
                  'comparison_images': [], 'reviewer': 'synthetic test', 'inspection_method': 'VISUAL_INSPECTION',
                  'unresolved_items': [], 'checks': {k: {'status': 'PASS', 'observation': 'synthetic observation'} for k in required_checks(contract)},
                  'composition': {'coordinate_space': 'FINAL_IMAGE', 'image_sha256': image_hash,
                                  'annotation_method': 'ASSISTANT_VISUAL_ESTIMATE', 'boundary_certainty': 'CLEAR',
                                  'required_content': 'COMPLETE', 'product_regions': [{'label': 'fixture', 'box': [.1,.1,.9,.9]}],
                                  'copy_regions': [], 'protected_regions': []}}
        self.assertEqual(review_status(self.root,contract,path,candidate,report)['status'],'PASS')
        addition = self.delta();new = addition['updates'][0]['replacement'];new['lock_id']='independent'
        addition['updates'][0].update(lock_id='independent',expected_lock_sha256=None)
        self.apply(addition)
        self.assertEqual(review_status(self.root,contract,path,candidate,report)['status'],'PASS')
        self.apply()
        self.assertEqual(review_status(self.root,contract,path,candidate,report)['execution'],'INVALIDATED')
        self.assertEqual(contract['resolved_identity_locks'],[self.old])

    def test_feedback_report_is_bound_before_revision(self):
        contract_path = self.root/'runs/fake/contract.json';write_json(contract_path, {'candidate_id': 'candidate'})
        state = load_json(self.root/'PRODUCT_STATE.json')
        state['candidates'] = [{'candidate_id': 'candidate', 'path': 'input/own-product.png',
                                'source_contract': 'runs/fake/contract.json', 'sha256': sha256(self.root/'input/own-product.png')}]
        write_json(self.root/'PRODUCT_STATE.json',state)
        report = {'candidate_id': 'candidate','candidate_sha256': state['candidates'][0]['sha256'],
                  'contract_sha256': sha256(contract_path),
                  'checks': {'structure_topology': {'status': 'FAIL','observation': 'Observed missing source-supported relief'}}}
        write_json(self.root/'qa/feedback.json',report)
        delta = self.delta();delta['source_report']='qa/feedback.json'
        self.apply(delta)
        newstate = load_json(self.root/'PRODUCT_STATE.json')
        self.assertEqual(newstate['decision_log'][-1]['source_report_sha256'],sha256(self.root/'qa/feedback.json'))
        self.assertEqual(newstate['candidates'],state['candidates'])

    def test_missing_feedback_report_does_not_write(self):
        before = (self.root/'PRODUCT_STATE.json').read_bytes()
        change = self.delta();change['source_report']='qa/missing.json'
        with self.assertRaises((ValueError,OSError)):self.apply(change)
        self.assertEqual(before,(self.root/'PRODUCT_STATE.json').read_bytes())

    def test_legacy_version_bump_does_not_hide_changed_lock_content(self):
        self.apply()
        state = load_json(self.root/'PRODUCT_STATE.json')
        current = state['identity_lockset']['locks']
        self.assertFalse(dependency_errors(state,['identity'],current,1))
        self.assertTrue(dependency_errors(state,['identity'],[self.old],2))

if __name__ == '__main__': unittest.main()
