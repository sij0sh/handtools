"""Pure queries over one reduced snapshot state. Every result carries the snapshot run and the
revision that accepted each record, so a reader can tell which evidence it rests on."""
from . import records

MAX_DEPTH = 5
UNKNOWN = 'unknown'


def _rows(state):
    return state.get('records', {})


def _stamp(state, rec):
    return {'snapshot': state['snapshot']['id'], 'record_revision': rec['accepted']['revision'],
            'status': rec['status']}


def _endpoint(value):
    return value if isinstance(value, str) else next(f'{k}: {v}' for k, v in value.items())


def contract_view(state, rec):
    view = {'id': rec['id'], 'direction': rec['direction'], 'classification': rec['classification'],
            'producers': [_endpoint(e) for e in rec.get('producers', [])] or [UNKNOWN],
            'consumers': [_endpoint(e) for e in rec.get('consumers', [])] or [UNKNOWN]}
    view.update({k: rec.get(k, UNKNOWN) for k in records.CONTRACT_DETAILS})
    return dict(view, **_stamp(state, rec))


def summary(state):
    rows = _rows(state).values()
    by_type = {}
    for r in rows:
        key = f'{r["type"]}:{r["status"]}'
        by_type[key] = by_type.get(key, 0) + 1
    unresolved = sorted({r['id'] for r in rows if r['type'] == 'contract'
                         for e in r.get('consumers', []) + r.get('producers', []) if isinstance(e, dict)
                         and 'unresolved' in e} |
                        {r['id'] for r in rows if r['type'] == 'contract' and not (r.get('consumers')
                                                                                    and r.get('producers'))})
    return {'snapshot': state['snapshot'], 'records': by_type, 'open_gaps': len(gaps(state)),
            'stale': len(stale(state)), 'contracts_with_unknown_endpoints': unresolved,
            'cost': state.get('cost', {'files': 0, 'bytes': 0, 'commands': []})}


def contracts(state):
    return [contract_view(state, r) for r in sorted(_rows(state).values(), key=lambda r: r['id'])
            if r['type'] == 'contract']


def edges(state):
    """(from, to, relation, record id): relationships plus contract producer -> contract -> consumer."""
    out = []
    for r in _rows(state).values():
        if r['type'] == 'relationship':
            out.append((r['from'], r['to'], r['relation'], r['id']))
        elif r['type'] == 'contract':
            for e in r.get('producers', []):
                out.append((_endpoint(e), r['id'], 'produces', r['id']))
            for e in r.get('consumers', []):
                out.append((r['id'], _endpoint(e), 'consumes', r['id']))
    return sorted(set(out))


def consumers(state, contract_id):
    rec = _rows(state).get(contract_id)
    if not rec or rec['type'] != 'contract':
        raise ValueError(f'{contract_id} is not a contract in snapshot {state["snapshot"]["id"]}.')
    declared = [_endpoint(e) for e in rec.get('consumers', [])]
    related = [f for f, t, rel, _ in edges(state) if t == contract_id and rel not in ('produces',)]
    return {'contract': contract_id, 'consumers': declared or [UNKNOWN], 'related': sorted(set(related)),
            'classification': rec['classification'], **_stamp(state, rec)}


def neighbors(state, entity, direction='both', depth=1):
    """Bounded traversal: downstream follows from->to, upstream to->from."""
    if direction not in ('upstream', 'downstream', 'both'):
        raise ValueError('direction is upstream|downstream|both.')
    if not isinstance(depth, int) or not 1 <= depth <= MAX_DEPTH:
        raise ValueError(f'depth is 1-{MAX_DEPTH}.')
    found, frontier, seen = [], {entity}, {entity}
    all_edges = edges(state)
    for level in range(1, depth + 1):
        nxt = set()
        for f, t, rel, rid in all_edges:
            for here, there, way in ((f, t, 'downstream'), (t, f, 'upstream')):
                if here in frontier and direction in (way, 'both'):
                    found.append({'from': f, 'to': t, 'relation': rel, 'record': rid, 'depth': level,
                                  'direction': way})
                    if there not in seen:
                        seen.add(there)
                        nxt.add(there)
        frontier = nxt
        if not frontier:
            break
    return {'entity': entity, 'snapshot': state['snapshot']['id'], 'edges': found}


def evidence(state, rid):
    rec = _rows(state).get(rid)
    if not rec:
        raise ValueError(f'{rid} is not recorded in snapshot {state["snapshot"]["id"]}.')
    return {'id': rid, 'classification': rec['classification'], 'confidence': rec.get('confidence', UNKNOWN),
            'evidence': rec.get('evidence', []), 'depends_on': records.references(rec),
            'supersedes': rec.get('supersedes', []), 'reused_from': rec.get('reused_from'), **_stamp(state, rec)}


def gaps(state):
    return [dict({k: r.get(k) for k in ('id', *records.GAP_FIELDS, 'affected')}, **_stamp(state, r))
            for r in sorted(_rows(state).values(), key=lambda r: r['id'])
            if r['type'] == 'gap' and not r.get('resolution')]


def stale(state):
    return [dict(id=r['id'], reason=r.get('stale_reason', ''), **_stamp(state, r))
            for r in sorted(_rows(state).values(), key=lambda r: r['id']) if r['status'] == 'stale']


def observations(state):
    """Observations, including inferred patterns and conflicts; never adopted decisions."""
    return [dict(id=r['id'], claim=r['claim'], classification=r['classification'],
                 conflicts_with=r.get('conflicts_with', []), **_stamp(state, r))
            for r in sorted(_rows(state).values(), key=lambda r: r['id']) if r['type'] == 'observation']


def decisions(state):
    return [dict(id=r['id'], summary=r['summary'], **_stamp(state, r))
            for r in sorted(_rows(state).values(), key=lambda r: r['id']) if r['type'] == 'decision']


NAMES = ('summary', 'contracts', 'consumers', 'neighbors', 'evidence', 'gaps', 'stale', 'observations', 'decisions')
