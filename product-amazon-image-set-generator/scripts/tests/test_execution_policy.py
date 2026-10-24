"""Exercise AI-authored execution strategy and code-enforced boundaries."""
import copy
import json
import unittest

import test_a_plus_layout as fixtures
import test_intake_handoff as intake_fixtures
from execution_policy import draft_policy, policy_errors, generation_guidance
from context_store import load_contract
from quality_rules import review_binding
from set_common import load_json, write_json
from init_visual_set import brief_drafts


def decision(mode='ADVANCED'):
    return {'mode': mode, 'reason': 'Assessed this task against the provided requirements and registered views',
            'requirements': 'CLEAR' if mode == 'ADVANCED' else 'PARTIAL', 'evidence': 'SUFFICIENT',
            'readiness': 'READY', 'allowed_completion': ['composition'] if mode == 'ADVANCED' else ['scene', 'style']}


class ExecutionPolicyTest(unittest.TestCase):
    def test_unresolved_new_task_cannot_generate(self):
        self.assertTrue(policy_errors({'execution_policy': draft_policy()}, generation=True))
        self.assertEqual(policy_errors({}), [])

    def test_clear_requirements_and_supported_evidence_allow_advanced(self):
        self.assertFalse(policy_errors({'execution_policy': decision()}, generation=True))
        for key,value in [('requirements','PARTIAL'),('evidence','PARTIAL')]:
            p=decision();p[key]=value
            self.assertTrue(policy_errors({'execution_policy':p}, generation=True))

    def test_assistance_does_not_approve_missing_product_evidence(self):
        p=decision('AI_ASSISTED');p['evidence']='INSUFFICIENT'
        self.assertTrue(policy_errors({'execution_policy':p},generation=True))
        p['readiness']='NEEDS_EVIDENCE'
        self.assertFalse(policy_errors({'execution_policy':p}))
        self.assertTrue(policy_errors({'execution_policy':p},generation=True))

    def test_explicit_advanced_minimum_stays_pending_instead_of_downgrading(self):
        p=decision();p.update(minimum_mode='ADVANCED',evidence='PARTIAL',readiness='NEEDS_EVIDENCE')
        self.assertFalse(policy_errors({'execution_policy':p}))
        self.assertTrue(policy_errors({'execution_policy':p},generation=True))
        p['mode']='AI_ASSISTED'
        self.assertTrue(policy_errors({'execution_policy':p}))

    def test_ai_completion_cannot_include_product_facts_or_rewrite_supplied_copy(self):
        p=decision('AI_ASSISTED');p['allowed_completion'].append('structure')
        self.assertTrue(policy_errors({'execution_policy':p}))
        p['allowed_completion']=['copy'];p['copy_origin']='PROVIDED'
        self.assertTrue(policy_errors({'execution_policy':p}))
        p['copy_rewrite_authorized']=True
        self.assertFalse(policy_errors({'execution_policy':p}))

    def test_bad_assessment_types_are_rejected(self):
        for key in ['mode','evidence','requirements','readiness','minimum_mode','copy_origin']:
            p=decision();p[key]={}
            self.assertTrue(policy_errors({'execution_policy':p}))

    def test_count_alone_does_not_select_a_mode(self):
        f=fixtures.APlusLayoutTest();f.setUp();self.addCleanup(f.doCleanups)
        plan=f.initialize(15)
        for row in plan['modules']:
            self.assertEqual(load_json(f.root/row['spec_path'])['execution_policy']['mode'],'UNRESOLVED')

    def test_mixed_task_modes_preserve_decision_and_skip_only_blocked_child(self):
        f=fixtures.APlusLayoutTest();f.setUp();self.addCleanup(f.doCleanups)
        plan=f.initialize();f.fill_for_approval(plan)
        for i in (0,1):
            path=f.root/plan['modules'][i]['spec_path'];spec=load_json(path)
            spec['execution_policy']=decision('AI_ASSISTED')
            if i==0:spec['execution_policy'].update(evidence='PARTIAL',readiness='NEEDS_EVIDENCE')
            write_json(path,spec)
        f.run_script('validate_set_plan.py','--set-id','aplus','--approve')
        next_task=json.loads(f.run_script('set_runtime.py','--set-id','aplus','next-generation').stdout)
        self.assertEqual(next_task['current']['module_id'],'a-plus-02')
        packet=json.loads(f.run_script('set_runtime.py','--set-id','aplus','prepare','--module-id','a-plus-02').stdout)
        self.assertEqual(packet['execution_mode'],'AI_ASSISTED')
        self.assertIn('Apply planned completion in: scene, style',packet['prompt'])
        contract=load_contract(f.root,f.root/packet['contract_path'])
        self.assertEqual(contract['execution_policy'],decision('AI_ASSISTED'))
        old=review_binding(f.root,contract,'synthetic-hash')
        contract['execution_policy']['reason']='New input assessment after receiving a requirement document'
        self.assertNotEqual(old,review_binding(f.root,contract,'synthetic-hash'))
        f.run_script('set_runtime.py','--set-id','aplus','prepare','--module-id','a-plus-01',success=False)

    def test_filtered_requirement_handoff_preserves_assessment_without_context_copy(self):
        f=intake_fixtures.IntakeHandoffTest();f.setUp()
        p=decision();p['copy_origin']='PROVIDED'
        f.data['modules'][0]['execution_policy']=p
        f.data['raw_workbook']='unrelated source context'
        brief=intake_fixtures.EXPORT.compile_brief(f.data)
        self.assertEqual(brief['modules'][0]['execution_policy'],p)
        self.assertNotIn('raw_workbook',brief)
        p['reason']='changed original'
        self.assertNotEqual(brief['modules'][0]['execution_policy']['reason'],p['reason'])

    def test_import_keeps_selected_mode_and_verbatim_copy(self):
        source={'image_id':'detail','role':'detail','buyer_question':'What is shown?','must_show':['actual part'],
                'copy':[{'text':'Exact supplied wording.','language':'en'}], 'execution_policy':decision()}
        brief={'job':{'channel':'PREMIUM_A_PLUS','width':1464,'height':600,'language':'en'},'modules':[source]}
        _,tasks=brief_drafts(brief,{'product_evidence':[]})
        self.assertEqual(tasks[0]['execution_policy'],decision())
        self.assertEqual(tasks[0]['copy']['labels'],['Exact supplied wording.'])
        source['execution_policy']['reason']='changed original'
        self.assertNotEqual(tasks[0]['execution_policy']['reason'],source['execution_policy']['reason'])

if __name__=='__main__':unittest.main()
