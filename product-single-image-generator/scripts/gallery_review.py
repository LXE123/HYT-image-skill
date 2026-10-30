"""Derive the Gallery opening-pair approval gate from existing candidate records."""
from project_store import read_json as store_read

import hashlib
import re


def review_policy_errors(plan):
    policy = plan.get('gallery_opening_review')
    if 'gallery_opening_review' not in plan:
        return []  # Saved plans opt in through an explicit revision.
    gallery = sorted((m for m in plan.get('modules', []) if m.get('channel') == 'AMAZON_GALLERY'),
                     key=lambda m: m.get('sequence', 0))
    if (not isinstance(policy, dict) or type(policy.get('version')) is not int or policy.get('version') != 1 or len(gallery) < 3
            or policy.get('image_ids') != [m['module_id'] for m in gallery[:2]]
            or any(m.get('template_id', m.get('generation_template', {}).get('template_id')) != 'main_product' for m in gallery[:2])):
        return ['gallery_opening_review must identify the first two Gallery tasks before its remainder']
    return []


def _file(root, name):
    if not isinstance(name, str) or not name:
        raise ValueError('missing approval artifact path')
    path = (root / name).resolve()
    path.relative_to(root.resolve())
    return path


def _read(path):
    return store_read(path)


def opening_review_status(root, plan, state, product):
    if 'gallery_opening_review' not in plan:
        return None
    errors = review_policy_errors(plan)
    if errors:
        raise ValueError('; '.join(errors))
    # Local imports avoid coupling standalone initialization to the set runtime.
    from context_store import load_contract
    from quality_rules import qa_errors
    from structure_state import dependency_errors
    ids = plan['gallery_opening_review']['image_ids']
    rows = {m['module_id']: m for m in state.get('modules', [])}
    candidates = {c['candidate_id']: c for c in product.get('candidates', [])}
    pending = []
    for image_id in ids:
        row = rows.get(image_id, {})
        candidate = candidates.get(row.get('candidate_id'), {})
        human = candidate.get('human_review', {})
        valid = (candidate.get('status') == 'ACCEPTED' and human.get('reviewer')
                 and human.get('decision_reference') and candidate.get('source_contract') == row.get('contract_path'))
        if valid:
            try:
                image = _file(root, candidate.get('path'))
                contract_path = _file(root, row.get('contract_path'))
                contract = load_contract(root, contract_path)
                report = _read(_file(root, candidate.get('checks', {}).get('visual', {}).get('report_path')))
                valid = (hashlib.sha256(image.read_bytes()).hexdigest() == candidate.get('sha256')
                         and contract.get('candidate_id') == candidate.get('candidate_id')
                         and contract.get('visual_set', {}).get('module_id') == image_id
                         and not dependency_errors(product, contract.get('required_lock_ids'), contract.get('resolved_identity_locks'))
                         and not qa_errors(root, contract, contract_path, candidate, report))
            except (OSError, ValueError, KeyError, TypeError):
                valid = False
        if not valid:
            pending.append(image_id)
    return {'image_ids': ids, 'approved': not pending, 'pending_ids': pending,
            'required_skill': 'product-single-image-generator'}


def require_opening_approval(root, plan, state, product, module_id):
    gate = opening_review_status(root, plan, state, product)
    module = next((m for m in plan.get('modules', []) if m['module_id'] == module_id), {})
    if (gate and not gate['approved'] and module.get('channel') == 'AMAZON_GALLERY'
            and module_id not in gate['image_ids']):
        raise ValueError('WAIT_FOR_GALLERY_OPENING_APPROVAL: show the upright front/reverse outputs '
                         'and obtain explicit user approval for both current candidates before the remainder')


def require_contract_opening_approval(root, contract):
    link = contract.get('visual_set')
    if not link:
        return
    set_id = link.get('set_id', '')
    if not isinstance(set_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', set_id):
        raise ValueError('unsafe visual set ID')
    folder = root / 'visual_sets' / set_id
    require_opening_approval(root, _read(folder / 'SET_PLAN.json'), _read(folder / 'SET_STATE.json'),
                             _read(root / 'PRODUCT_STATE.json'), link.get('module_id'))
