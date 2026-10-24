#!/usr/bin/env python3
"""Apply an evidence-grounded semantic delta to current product locks; never edit old contracts."""
import argparse
from copy import deepcopy
import json
import os
import re
from pathlib import Path
import tempfile

from quality_rules import digest, file_at
from structure_state import value_hash


def apply_change(root, change, expected_sha):
    root = Path(root).resolve()
    state_path = root / 'PRODUCT_STATE.json'
    if digest(state_path) != expected_sha:
        raise ValueError('product state changed; reread current state before applying the delta')
    state = json.loads(state_path.read_text())
    index = json.loads((root / 'index.json').read_text())
    if state.get('reference_package', {}).get('sha256') != digest(root / 'index.json'):
        raise ValueError('reconcile changed reference evidence before revising structure')
    if set(change) - {'reason', 'updates', 'source_report'} or not isinstance(change.get('reason'), str) or not change['reason'].strip():
        raise ValueError('delta needs a concrete reason and only supported fields')
    updates = change.get('updates')
    if not isinstance(updates, list) or not updates:
        raise ValueError('delta needs nonempty updates')
    if change.get('source_report'):
        report_path = file_at(root, change['source_report'])
        report_path.relative_to(root / 'qa')
        report = json.loads(report_path.read_text())
        candidate = next((x for x in state.get('candidates', []) if x.get('candidate_id') == report.get('candidate_id')), None)
        if not candidate or report.get('candidate_sha256') != candidate.get('sha256') or report.get('candidate_sha256') != digest(file_at(root, candidate['path'])) or report.get('contract_sha256') != digest(file_at(root, candidate['source_contract'])):
            raise ValueError('feedback report does not match registered candidate/contract bytes')
        observations = [*report.get('checks', {}).values(), *report.get('structure_observations', {}).values()]
        if not any(x.get('status') in {'FAIL', 'REVIEW_REQUIRED'} and x.get('observation', '').strip() for x in observations):
            raise ValueError('feedback report needs an observed failure or uncertainty')
    updated = deepcopy(state)
    lockset = updated['identity_lockset']
    locks = {x['lock_id']: x for x in lockset['locks']}
    evidence = {x['path']: x for x in index.get('product_evidence', [])}
    seen, changes = set(), []
    def check_evidence(paths):
        if not isinstance(paths, list) or not paths:
            raise ValueError('each revised lock/relation needs original evidence_paths')
        for path in paths:
            ref = evidence.get(path)
            if not ref or ref.get('source_type') not in {'REAL_PHOTO', 'DESIGN_RENDER', 'CAD_RENDER', 'DETAIL'} or Path(path).parts[0] in {'candidates', 'outputs', 'runs', 'qa'} or digest(file_at(root, path)) != ref.get('sha256'):
                raise ValueError(f'original evidence missing, unregistered or changed: {path}')
    for item in updates:
        if set(item) != {'lock_id', 'expected_lock_sha256', 'replacement'}:
            raise ValueError('update needs lock_id, expected_lock_sha256 and replacement')
        key = item['lock_id']
        old = locks.get(key)
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', key):
            raise ValueError('unsafe lock_id')
        if key in seen or item['expected_lock_sha256'] != (value_hash(old) if old is not None else None):
            raise ValueError(f'unknown, duplicate or stale lock delta: {key}')
        seen.add(key)
        new = item['replacement']
        if not isinstance(new, dict) or new.get('lock_id') != key or new.get('status') not in {'LOCKED', 'REVIEW_REQUIRED'} or not isinstance(new.get('fact'), str) or not new['fact'].strip():
            raise ValueError('replacement needs same lock_id, nonempty fact and explicit LOCKED/REVIEW_REQUIRED status')
        if old and any(field not in new for field in old):
            raise ValueError('replacement must preserve existing lock fields; revise their values explicitly')
        check_evidence(new.get('evidence_paths'))
        relations = new.get('relations', [])
        if not isinstance(relations, list):
            raise ValueError('relations must be a list')
        ids = set()
        for relation in relations:
            if not isinstance(relation, dict) or any(not isinstance(relation.get(k), str) or not relation[k].strip() for k in ('relation_id', 'subject', 'predicate', 'object')) or relation['relation_id'] in ids:
                raise ValueError('relation needs unique relation_id and subject/predicate/object')
            ids.add(relation['relation_id'])
            if ':' in relation['relation_id']:
                raise ValueError('relation_id must not contain colon')
            if 'views' in relation and (not isinstance(relation['views'], list) or not relation['views'] or any(not isinstance(x, str) or not x.strip() for x in relation['views'])):
                raise ValueError('optional relation views must be a nonempty list of view names')
            check_evidence(relation.get('evidence_paths'))
            if not set(relation['evidence_paths']).issubset(new['evidence_paths']):
                raise ValueError('relation evidence must belong to this lock evidence_paths')
        if new == old:
            raise ValueError('delta does not change the current lock')
        locks[key] = deepcopy(new)
        changes.append({'lock_id': key, 'before_sha256': value_hash(old) if old is not None else None, 'after_sha256': value_hash(new)})
    lockset['locks'] = list(locks.values())
    lockset['version'] += 1
    # READY describes the current record; individual unresolved locks block only their dependants.
    updated.setdefault('decision_log', []).append({'action': 'STRUCTURE_STATE_REVISED', 'reason': change['reason'], 'lockset_version': lockset['version'], 'changes': changes, **({'source_report': change['source_report'], 'source_report_sha256': digest(file_at(root, change['source_report']))} if change.get('source_report') else {})})
    data = json.dumps(updated, ensure_ascii=False, indent=2) + '\n'
    with tempfile.NamedTemporaryFile(mode='w', dir=root, prefix='.structure-', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    try:
        if digest(state_path) != expected_sha:
            raise ValueError('product state changed during revision; delta was not applied')
        os.replace(temp, state_path)
    finally:
        temp.unlink(missing_ok=True)
    return {'lockset_version': lockset['version'], 'changed_lock_ids': sorted(seen), 'state_sha256': digest(state_path), 'next_action': 'RESOLVE_CURRENT_TASK_DEPENDENCIES', 'visual_acceptance': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--change', type=Path, required=True)
    parser.add_argument('--expected-state-sha', required=True)
    args = parser.parse_args()
    try:
        result = apply_change(args.package, json.loads(args.change.read_text()), args.expected_state_sha)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
