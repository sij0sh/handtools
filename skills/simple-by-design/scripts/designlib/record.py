"""decisions.json: validation, the agent's payload, goal hashes, and IDs."""
import hashlib
import json
import re

from . import storage

GOAL_KEYS = ('goal', 'constraints', 'criteria')


def _strings(value, where):
    if not isinstance(value, list) or not all(isinstance(s, str) and s for s in value):
        raise ValueError(f'{where} must be a list of nonempty strings.')


def _keys(obj, where, required, optional):
    if not isinstance(obj, dict):
        raise ValueError(f'{where} must be an object.')
    missing = [k for k in required if k not in obj]
    extra = [k for k in obj if k not in required + optional]
    if missing or extra:
        raise ValueError(f'{where}: missing {missing}, unknown {extra}.')


def validate(record):
    """Check record against references/decisions.schema.json, plus cross-references."""
    _keys(record, 'record', ['goals'], [])
    if not isinstance(record['goals'], list):
        raise ValueError('goals must be a list.')
    goal_ids = set()
    for g in record['goals']:
        _keys(g, 'goal', ['id', 'goal', 'decisions'], ['constraints', 'criteria'])
        gid = g['id']
        if not isinstance(gid, str) or not re.fullmatch(r'G\d+', gid) or gid in goal_ids:
            raise ValueError(f'goal id {gid!r} must be unique G#.')
        goal_ids.add(gid)
        if not isinstance(g['goal'], str) or not g['goal']:
            raise ValueError(f'{gid}.goal must be a nonempty string.')
        for key in ('constraints', 'criteria'):
            if key in g:
                _strings(g[key], f'{gid}.{key}')
        if not isinstance(g['decisions'], list):
            raise ValueError(f'{gid}.decisions must be a list.')
        ids = []
        for d in g['decisions']:
            _keys(d, f'{gid} decision', ['id', 'question', 'status'], ['answer', 'after', 'rationale'])
            did = d['id']
            if not isinstance(did, str) or not re.fullmatch(r'D\d+', did) or did in ids:
                raise ValueError(f'{gid}: decision id {did!r} must be unique D#.')
            ids.append(did)
            where = f'{gid}.{did}'
            if not isinstance(d['question'], str) or not d['question']:
                raise ValueError(f'{where}.question must be a nonempty string.')
            if d['status'] not in ('open', 'resolved'):
                raise ValueError(f'{where}.status must be "open" or "resolved".')
            if d['status'] == 'resolved' and not d.get('answer'):
                raise ValueError(f'{where} is resolved but has no answer.')
            for key in ('answer', 'rationale'):
                if key in d and (not isinstance(d[key], str) or not d[key]):
                    raise ValueError(f'{where}.{key} must be a nonempty string.')
            if 'after' in d:
                _strings(d['after'], f'{where}.after')
        for d in g['decisions']:
            for dep in d.get('after', []):
                if dep == d['id'] or dep not in ids:
                    raise ValueError(f'{gid}.{d["id"]}.after: {dep} is not another decision in {gid}.')


def exists(root):
    return (root / storage.RECORD).exists()


def load(root):
    record = storage.read_json(root / storage.RECORD)
    validate(record)
    return record


def load_or_empty(root):
    return load(root) if exists(root) else {'goals': []}


def save(root, record):
    storage.write_json(root / storage.RECORD, record)


def find_goal(record, gid):
    for g in record['goals']:
        if g['id'] == gid:
            return g
    raise ValueError(f'Goal {gid} not found.')


def goal_hash(record, gid):
    """Return a hash of one goal, or None when the goal is absent."""
    if record is None or gid is None:
        return None
    for g in record['goals']:
        if g['id'] == gid:
            data = json.dumps(g, sort_keys=True, separators=(',', ':')).encode('utf-8')
            return hashlib.sha256(data).hexdigest()
    return None


def open_rows(goal):
    return [d['id'] for d in goal['decisions'] if d['status'] == 'open']


def next_id(items, prefix):
    numbers = [int(i['id'][1:]) for i in items if re.fullmatch(prefix + r'\d+', i['id'])]
    return f'{prefix}{max(numbers, default=0) + 1}'


def public_goal(goal):
    """Goal as the agent sees it: `status` is derived, so it is hidden."""
    shown = dict(goal)
    shown['decisions'] = [{k: v for k, v in d.items() if k != 'status'} for d in goal['decisions']]
    return shown


def apply_payload(record, payload, gid, ground):
    """Apply the agent's edits to one goal in record; return that goal's id."""
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object.')
    extra = [k for k in payload if k not in ('id', 'decisions') + GOAL_KEYS]
    if extra:
        raise ValueError(f'Payload: unknown keys {extra}.')
    if 'id' in payload:
        if not ground:
            raise ValueError('Payload `id` is only valid in ground.')
        goal = find_goal(record, payload['id'])
    elif ground:
        if not payload.get('goal'):
            raise ValueError('Ground payload needs `goal` (new set) or `id` (reuse).')
        goal = {'id': next_id(record['goals'], 'G'), 'goal': payload['goal']}
        record['goals'].append(goal)
    else:
        goal = find_goal(record, gid)
    for key in GOAL_KEYS:
        if key not in payload:
            continue
        if payload[key] is None:
            if key == 'goal':
                raise ValueError('Payload `goal` cannot be null.')
            goal.pop(key, None)
        else:
            goal[key] = payload[key]
    goal.setdefault('decisions', [])
    rows = payload.get('decisions', [])
    if not isinstance(rows, list):
        raise ValueError('Payload `decisions` must be a list.')
    by_id = {d['id']: d for d in goal['decisions']}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            raise ValueError('Each payload row needs an `id`.')
        did = row['id']
        if 'status' in row:
            raise ValueError(f'{did}: `status` follows from `answer`; send `answer` or `"answer": null`.')
        if 'drop' in row:
            if row['drop'] is not True or set(row) != {'id', 'drop'}:
                raise ValueError(f'{did}: drop a row with exactly {{"id": "{did}", "drop": true}}.')
            if did not in by_id:
                raise ValueError(f'{did}: cannot drop; no such row in {goal["id"]}.')
            goal['decisions'].remove(by_id.pop(did))
            continue
        decision = by_id.get(did)
        if decision is None:
            decision = by_id[did] = {'id': did}
            goal['decisions'].append(decision)
        for key, value in row.items():
            if key == 'id':
                continue
            if value is None:
                if key == 'question':
                    raise ValueError(f'{did}: `question` cannot be null.')
                decision.pop(key, None)
            else:
                decision[key] = value
        decision['status'] = 'resolved' if decision.get('answer') else 'open'
    validate(record)
    return goal['id']
