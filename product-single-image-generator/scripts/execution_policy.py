"""Validate AI-authored input assessments; never classify images by their count."""

MODES = ('ADVANCED', 'AI_ASSISTED')
COMPLETION = {'planning', 'composition', 'style', 'scene', 'copy'}


def draft_policy():
    return {'mode': 'UNRESOLVED', 'reason': '', 'requirements': 'UNSPECIFIED',
            'evidence': 'INSUFFICIENT', 'readiness': 'NEEDS_EVIDENCE', 'allowed_completion': []}


def policy_errors(contract, *, generation=False):
    if 'execution_policy' not in contract:
        return []  # Existing tasks retain their pinned requirements.
    p = contract['execution_policy']
    if not isinstance(p, dict):
        return ['execution_policy must contain an AI-authored input assessment']
    errors = []
    if p.get('mode') not in MODES:
        errors.append('execution_policy mode must be selected by input analysis: ADVANCED or AI_ASSISTED')
    if not isinstance(p.get('reason'), str) or not p['reason'].strip():
        errors.append('execution_policy needs a concrete input-based reason')
    if p.get('requirements') not in ('CLEAR', 'PARTIAL', 'UNSPECIFIED'):
        errors.append('execution_policy requirements must be CLEAR, PARTIAL or UNSPECIFIED')
    if p.get('evidence') not in ('SUFFICIENT', 'PARTIAL', 'INSUFFICIENT'):
        errors.append('execution_policy evidence must assess this task, not image count')
    if p.get('readiness') not in ('READY', 'NEEDS_EVIDENCE', 'REPLAN'):
        errors.append('execution_policy needs explicit task readiness')
    if p.get('minimum_mode') not in (None, 'ADVANCED'):
        errors.append('unsupported minimum execution mode')
    if p.get('minimum_mode') == 'ADVANCED' and p.get('mode') != 'ADVANCED':
        errors.append('explicit ADVANCED requirement cannot be downgraded')
    if p.get('mode') == 'ADVANCED' and (generation or p.get('readiness') == 'READY') and (p.get('requirements') != 'CLEAR' or p.get('evidence') != 'SUFFICIENT'):
        errors.append('ADVANCED requires clear requirements and sufficient task evidence')
    if p.get('readiness') == 'READY' and p.get('evidence') != 'SUFFICIENT':
        errors.append('AI assistance cannot turn insufficient structural evidence into READY')
    allowed = p.get('allowed_completion')
    if not isinstance(allowed, list) or any(not isinstance(x, str) or x not in COMPLETION for x in allowed) or len(set(allowed)) != len(allowed):
        errors.append('allowed_completion only covers planning, composition, style, scene and copy')
    if p.get('copy_origin') not in (None, 'PROVIDED', 'AI_PROPOSED', 'NONE'):
        errors.append('unsupported copy origin')
    if p.get('copy_origin') == 'PROVIDED' and isinstance(allowed, list) and 'copy' in allowed and p.get('copy_rewrite_authorized') is not True:
        errors.append('provided copy cannot be rewritten without explicit authorization')
    if generation and p.get('readiness') != 'READY':
        errors.append('execution_policy task is not READY: resolve evidence or replan this task')
    return errors


def generation_guidance(contract):
    p = contract.get('execution_policy')
    if not isinstance(p, dict) or p.get('mode') not in MODES:
        return []
    if p['mode'] == 'ADVANCED':
        return ['Execution: ADVANCED.']
    return ['Execution: AI_ASSISTED. Apply planned completion in: ' + ', '.join(p.get('allowed_completion', [])) + '. Render Exact copy verbatim; preserve supplied requirements and evidenced structure. Creative proposals do not establish product facts.']
