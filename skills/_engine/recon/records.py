"""Recon record types, envelope version and validation. Pure: no filesystem, no clock.

A record states what is known about the project and its ecosystem, with evidence. Unknown
fields stay absent; nothing here demands an answer the evidence does not give.
"""
import json
import re

SCHEMA = 'handtools.recon'
VERSION = 1
MAX_RECORDS = 200
MAX_TEXT = 500
MAX_ID = 200

TYPES = ('component', 'contract', 'relationship', 'observation', 'decision', 'gap')
PREFIX = {'component': 'component', 'contract': 'contract', 'relationship': 'rel', 'observation': 'obs',
          'decision': 'decision', 'gap': 'gap'}
TYPE_OF = {v: k for k, v in PREFIX.items()}
CLASSIFICATIONS = ('observed', 'configured', 'declared', 'inferred', 'unknown')
CONFIDENCE = ('high', 'medium', 'low')
CONTRACT_KINDS = ('http', 'queue', 'schedule', 'schema', 'table', 'file', 'webhook', 'sdk')
DIRECTIONS = ('inbound', 'outbound', 'both', 'internal')
# Contract details: optional; absent means unknown.
CONTRACT_DETAILS = ('owner', 'schema', 'version', 'compatibility', 'ordering', 'retries', 'idempotency',
                    'failure_recovery', 'migration', 'retention', 'authority')
GAP_FIELDS = ('question', 'searched', 'missing', 'consequence', 'next_lookup')
STATUSES = ('current', 'stale')
DEPTHS = ('orient', 'map', 'deepen')
COST_KEYS = ('files', 'bytes')
ID = re.compile(r'^(component|contract|rel|obs|decision|gap):\S[^\n]*$')
DECISION_ID = re.compile(r'^decision:(G\d+)/(D\d+)$')


def need(cond, msg):
    if not cond:
        raise ValueError(msg)


def text(obj, key, where, required=True):
    value = obj.get(key)
    if value is None and not required:
        return None
    need(isinstance(value, str) and value.strip(), f'{where}: `{key}` must be non-empty text.')
    need(len(value) <= MAX_TEXT, f'{where}: `{key}` is longer than {MAX_TEXT} characters.')
    return value


def type_of(rid):
    """`contract:queue:orders.created` -> 'contract'."""
    return TYPE_OF.get(rid.split(':', 1)[0])


def is_id(value):
    return isinstance(value, str) and len(value) <= MAX_ID and bool(ID.match(value))


def relationship_id(relation, source, target):
    return f'rel:{relation}:{source}->{target}'


def endpoint(value, where):
    """A component/contract id, {"external": name} or {"unresolved": "<role> of <id>"}."""
    if isinstance(value, str):
        need(is_id(value), f'{where}: `{value}` is not a record id.')
        return
    need(isinstance(value, dict) and len(value) == 1 and set(value) <= {'external', 'unresolved'},
         f'{where}: an endpoint is a record id, {{"external": "name"}} or {{"unresolved": "<role> of <id>"}}.')
    text(value, next(iter(value)), where)


def evidence(ref, where, hashed):
    need(isinstance(ref, dict), f'{where}: evidence refs are objects.')
    text(ref, 'source', where)
    path = text(ref, 'path', where)
    need(not path.startswith('/') and '..' not in path.split('/'), f'{where}: evidence path must be relative.')
    text(ref, 'statement', where)
    if ref.get('lines') is not None:
        need(isinstance(ref['lines'], str) and re.match(r'^\d+(-\d+)?$', ref['lines']),
             f'{where}: `lines` is "a" or "a-b" (informational only).')
    if hashed:
        need(isinstance(ref.get('sha256'), str) and len(ref['sha256']) == 64,
             f'{where}: evidence needs the file sha256 (the recorder fills it).')


def references(record):
    """Record ids this record depends on: explicit depends_on plus ids in its own fields."""
    out = list(record.get('depends_on', []))
    for key in ('from', 'to', 'affected'):
        value = record.get(key)
        out += value if isinstance(value, list) else [value]
    for key in ('producers', 'consumers'):
        out += record.get(key, [])
    return sorted({r for r in out if is_id(r) and r != record['id']})


def validate_record(record, hashed=True):
    """One record or a drop; `hashed` False checks agent input before the recorder adds hashes."""
    need(isinstance(record, dict), 'records are objects.')
    rid = record.get('id')
    need(is_id(rid), f'`{rid}`: id is `<type>:<natural key>` (component|contract|rel|obs|decision|gap), '
                     f'at most {MAX_ID} characters, no line numbers needed.')
    where = rid
    if record.get('drop') is True:
        text(record, 'reason', where)
        need(set(record) <= {'id', 'drop', 'reason'}, f'{where}: a drop has only id, drop, reason.')
        return
    kind = type_of(rid)
    need(record.get('type', kind) == kind, f'{where}: type must be {kind} for this id prefix.')
    need(record.get('classification') in CLASSIFICATIONS,
         f'{where}: classification is one of {", ".join(CLASSIFICATIONS)}.')
    if record.get('confidence') is not None:
        need(record['confidence'] in CONFIDENCE, f'{where}: confidence is one of {", ".join(CONFIDENCE)}.')
    if record.get('status') is not None:
        need(record['status'] in STATUSES, f'{where}: status is current|stale.')
    refs = record.get('evidence', [])
    need(isinstance(refs, list), f'{where}: `evidence` must be a list.')
    for ref in refs:
        evidence(ref, where, hashed)
    deps = record.get('depends_on', [])
    need(isinstance(deps, list) and all(is_id(d) for d in deps), f'{where}: depends_on lists record ids.')
    if kind in ('component', 'contract', 'relationship', 'observation') and record['classification'] != 'unknown':
        need(refs, f'{where}: cite at least one evidence ref, or classify it unknown.')
    text(record, 'note', where, required=False)
    if kind == 'component':
        text(record, 'responsibility', where)
        for key in ('sources', 'entrypoints', 'state', 'commands'):
            need(isinstance(record.get(key, []), list), f'{where}: `{key}` must be a list.')
    elif kind == 'contract':
        _, ckind, channel = (rid.split(':', 2) + ['', ''])[:3]
        need(ckind in CONTRACT_KINDS and channel, f'{where}: contract ids are contract:<kind>:<channel>, kind one of '
                                                  f'{", ".join(CONTRACT_KINDS)}.')
        need(record.get('direction') in DIRECTIONS, f'{where}: direction is one of {", ".join(DIRECTIONS)}.')
        for key in ('producers', 'consumers'):
            value = record.get(key, [])
            need(isinstance(value, list), f'{where}: `{key}` must be a list.')
            for e in value:
                endpoint(e, f'{where} {key}')
        for key in CONTRACT_DETAILS:
            text(record, key, where, required=False)
    elif kind == 'relationship':
        relation = text(record, 'relation', where)
        need(is_id(record.get('from')) and is_id(record.get('to')), f'{where}: `from` and `to` are record ids.')
        need(rid == relationship_id(relation, record['from'], record['to']),
             f'{where}: id must be {relationship_id(relation, record["from"], record["to"])}.')
    elif kind == 'observation':
        text(record, 'claim', where)
        if record.get('conflicts_with') is not None:
            need(isinstance(record['conflicts_with'], list) and all(is_id(c) for c in record['conflicts_with']),
                 f'{where}: conflicts_with lists record ids.')
    elif kind == 'decision':
        need(DECISION_ID.match(rid), f'{where}: decision ids are decision:G#/D# from the ADR log; an inferred '
                                     'pattern is an observation, never a decision.')
        need(record['classification'] == 'declared', f'{where}: a decision reference is classified declared.')
        text(record, 'summary', where)
    elif kind == 'gap':
        for key in GAP_FIELDS:
            text(record, key, where)
        need(isinstance(record.get('affected'), list) and all(is_id(a) for a in record['affected']),
             f'{where}: `affected` lists record ids.')
        text(record, 'resolution', where, required=False)


def adopted(record_log):
    """Answered, non-superseded decisions in a parsed .agents/design/decisions.json -> {'G#/D#'}."""
    out = set()
    for goal in (record_log or {}).get('goals', []):
        for d in goal.get('decisions', []):
            if d.get('answer') and d.get('status') != 'superseded':
                out.add(f'{goal["id"]}/{d["id"]}')
    return out


def validate_envelope(payload, hashed=True, decisions=None):
    """The record.accepted payload. `decisions` (adopted G#/D# set) is checked when given."""
    need(isinstance(payload, dict), 'record payload must be an object.')
    need(payload.get('schema') == SCHEMA, f'record schema must be {SCHEMA}.')
    need(payload.get('version') == VERSION, f'unsupported {SCHEMA} version {payload.get("version")!r}; '
                                            f'this engine reads version {VERSION}.')
    recs = payload.get('records')
    need(isinstance(recs, list) and 0 < len(recs) <= MAX_RECORDS, f'send 1-{MAX_RECORDS} records per batch.')
    ids = [r.get('id') if isinstance(r, dict) else None for r in recs]
    need(len(ids) == len(set(ids)), 'a batch names each id once.')
    for r in recs:
        validate_record(r, hashed)
        if decisions is not None and type_of(r['id']) == 'decision' and not r.get('drop'):
            key = r['id'].split(':', 1)[1]
            need(key in decisions, f'{r["id"]}: not an answered decision in .agents/design/decisions.json; '
                                   'record an inferred pattern as an observation.')
    cost = payload.get('cost', {})
    need(isinstance(cost, dict) and set(cost) <= {*COST_KEYS, 'commands'}, 'cost is {files, bytes, commands}.')
    need(all(isinstance(cost.get(k, 0), int) and cost.get(k, 0) >= 0 for k in COST_KEYS),
         'cost files/bytes are non-negative integers.')
    need(isinstance(cost.get('commands', []), list) and all(isinstance(c, str) for c in cost.get('commands', [])),
         'cost.commands lists the exact commands run.')
    if payload.get('carried_from') is not None:
        need(isinstance(payload['carried_from'], str), 'carried_from names the predecessor snapshot.')
    json.dumps(payload, allow_nan=False)
