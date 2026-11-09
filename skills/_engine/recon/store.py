"""Recon snapshots in the engine journal: start, record, close, refresh, read.

Journal: <state root>/recon/<project key>/events.sqlite3; one run per snapshot, `snap-N`.
The recorder, not the agent, hashes cited files, so every accepted record pins the content it
rests on. A closed snapshot never advances; `refresh` starts a successor that carries forward
records whose evidence is unchanged and marks the rest stale.
"""
import json
import re
from pathlib import Path

from .. import events, storage
from . import records, reduce, sources

AREA = 'recon'
BUDGETS = {'max_files': 200, 'max_bytes': 2_000_000, 'max_depth': 3, 'allowed_commands': []}
RUN = re.compile(r'^snap-(\d+)$')
ADR_LOG = Path('.agents') / 'design' / 'decisions.json'


def need(cond, msg):
    if not cond:
        raise ValueError(msg)


def base(root):
    return storage.state_dir(AREA, Path(root))


def journal(root):
    return events.Journal(base(root) / 'events.sqlite3', reduce.REDUCERS)


def runs(root):
    """Snapshot runs, oldest first."""
    if not (storage.state_root() / AREA / storage.project_key(Path(root)) / 'events.sqlite3').exists():
        return []
    return sorted((r for r in journal(root).runs() if RUN.match(r)), key=lambda r: int(RUN.match(r).group(1)))


def read(root, run):
    """(state, chain, closed) of one snapshot run."""
    chain = journal(root).history(run)
    need(chain, f'No recon snapshot {run}; run `status` to list snapshots.')
    state, chain = events.replay(chain, reduce.REDUCERS)
    return state, chain, chain[-1]['kind'] == 'run.closed'


def newest(root, closed_only=False):
    for run in reversed(runs(root)):
        if not closed_only or read(root, run)[2]:
            return run
    return None


def adopted(root):
    path = Path(root) / ADR_LOG
    return records.adopted(json.loads(path.read_text(encoding='utf-8'))) if path.is_file() else set()


def _roots(root, related):
    out = {sources.PRIMARY: Path(root).resolve()}
    for label, path in (related or {}).items():
        need(re.match(r'^[A-Za-z0-9][\w.-]*$', label) and label != sources.PRIMARY,
             f'related label `{label}`: letters, digits, dot, dash, underscore.')
        need(Path(path).is_dir(), f'related root `{label}` = {path} is not a directory.')
        out[label] = Path(path).resolve()
    return out


def _budgets(given):
    out = dict(BUDGETS, **(given or {}))
    need(set(out) == set(BUDGETS), f'budgets are {", ".join(BUDGETS)}.')
    need(all(isinstance(out[k], int) and out[k] > 0 for k in ('max_files', 'max_bytes', 'max_depth')),
         'max_files, max_bytes and max_depth are positive integers.')
    need(isinstance(out['allowed_commands'], list) and all(isinstance(c, str) and c for c in out['allowed_commands']),
         'allowed_commands lists exact command strings (default none: static inspection only).')
    return out


def _snapshot(run, root, related, exclude, depth, budgets, predecessor):
    need(depth in records.DEPTHS, f'depth is one of {", ".join(records.DEPTHS)}.')
    roots = {label: dict(path=str(path), **sources.fingerprint(path, exclude if label == sources.PRIMARY else ()))
             for label, path in _roots(root, related).items()}
    return {'id': run, 'workspace': {'project_key': storage.project_key(Path(root)), 'root': str(Path(root).resolve())},
            'roots': roots, 'exclude': list(exclude), 'depth': depth, 'budgets': _budgets(budgets),
            'schema': records.SCHEMA, 'schema_version': records.VERSION, 'predecessor': predecessor}


def _by_request(store, request_id):
    for run in store.runs():
        first = store.history(run)[:1]
        if first and first[0]['request_id'] == request_id:
            return first[0]
    return None


def start(root, request_id, related=None, exclude=(), depth='map', budgets=None, predecessor=None):
    need(request_id, '--request-id is required for retry safety.')
    store = journal(root)
    with storage.lock(base(root)):
        prior = _by_request(store, request_id)
        if prior:
            return prior
        taken = [int(RUN.match(r).group(1)) for r in store.runs() if RUN.match(r)]
        run = f'snap-{max(taken, default=0) + 1}'
        snap = _snapshot(run, root, related, exclude, depth, budgets, predecessor)
        return store.append(run, 'run.started', {'snapshot': snap}, 0, request_id, snap['workspace']['project_key'])


def _envelope(payload):
    need(isinstance(payload, dict), 'Send a JSON object: {"records": [...], "cost": {...}}.')
    if 'schema' not in payload:
        payload = dict(payload, schema=records.SCHEMA, version=records.VERSION)
    return payload


def _hash_evidence(state, rec):
    roots = state['snapshot']['roots']
    for ref in rec.get('evidence', []):
        need(ref['source'] in roots, f'{rec["id"]}: evidence source `{ref["source"]}` is not a snapshot root '
                                     f'({", ".join(roots)}).')
        sha = sources.file_hash(roots[ref['source']]['path'], ref['path'])
        need(sha, f'{rec["id"]}: {ref["source"]}:{ref["path"]} does not exist in that root.')
        need(ref.get('sha256') in (None, sha), f'{rec["id"]}: {ref["path"]} changed since it was read; re-read it.')
        ref['sha256'] = sha


def record(root, run, payload, expect, request_id):
    need(request_id, '--request-id is required for retry safety.')
    need(expect is not None, '--expect-revision is required.')
    store = journal(root)
    state, chain, closed = read(root, run)
    if any(c['request_id'] == request_id for c in chain):
        return store.append(run, 'record.accepted', _prepare(state, root, payload), expect, request_id)
    need(not closed, f'{run} is closed; run `refresh --run {run}` to start a successor.')
    payload = _prepare(state, root, payload)
    cost, budget = state.get('cost') or {'files': 0, 'bytes': 0, 'commands': []}, state['snapshot']['budgets']
    add = payload.get('cost', {})
    need(cost['files'] + add.get('files', 0) <= budget['max_files'] and
         cost['bytes'] + add.get('bytes', 0) <= budget['max_bytes'],
         f'{run}: this batch exceeds the snapshot budget (files {cost["files"]}+{add.get("files", 0)}/'
         f'{budget["max_files"]}, bytes {cost["bytes"]}+{add.get("bytes", 0)}/{budget["max_bytes"]}). Close it and '
         'ask the user for a larger budget on a successor (`refresh --budget ...`).')
    bad = [c for c in add.get('commands', []) if c not in budget['allowed_commands']]
    need(not bad, f'{run}: commands not allowed by the snapshot budget: {bad}.')
    return store.append(run, 'record.accepted', payload, expect, request_id, state['snapshot']['workspace']['project_key'])


def _prepare(state, root, payload):
    payload = _envelope(payload)
    records.validate_envelope(payload, hashed=False, decisions=adopted(root))
    payload = json.loads(json.dumps(payload))
    for rec in payload['records']:
        need(rec.get('status') in (None, 'current'), f'{rec["id"]}: only refresh marks records stale.')
        for key in ('reused_from', 'stale_reason'):
            need(key not in rec, f'{rec["id"]}: `{key}` is set by refresh, not by record.')
        _hash_evidence(state, rec)
    records.validate_envelope(payload)
    return payload


def close(root, run, expect, request_id):
    need(request_id and expect is not None, '--request-id and --expect-revision are required.')
    state, _, _ = read(root, run)
    return journal(root).append(run, 'run.closed', {'closed': True}, expect, request_id,
                                state['snapshot']['workspace']['project_key'])


def invalidate(state, now_roots, decisions):
    """{id: reason} for every record of `state` that is stale against the roots as they are now."""
    old_roots = state['snapshot']['roots']
    changed = sorted(label for label in old_roots
                     if now_roots.get(label, {}).get('fingerprint') != old_roots[label]['fingerprint'])
    recs = state.get('records', {})
    stale = {}
    for rid, rec in recs.items():
        if rec['status'] == 'stale':
            stale[rid] = rec.get('stale_reason') or 'stale in predecessor'
        elif rec['type'] == 'decision':
            if rid.split(':', 1)[1] not in decisions:
                stale[rid] = 'no longer an answered decision in the ADR log'
        elif rec.get('evidence'):
            for ref in rec['evidence']:
                path = now_roots.get(ref['source'], {}).get('path')
                if not path or sources.file_hash(path, ref['path']) != ref['sha256']:
                    stale[rid] = f'evidence changed: {ref["source"]}:{ref["path"]}'
                    break
        elif not records.references(rec) and changed:
            stale[rid] = f'no evidence dependencies; scope changed in {", ".join(changed)}'
    grew = True
    while grew:  # dependents of stale records are stale
        grew = False
        for rid, rec in recs.items():
            if rid not in stale:
                hit = [r for r in records.references(rec) if r in stale]
                if hit:
                    stale[rid], grew = f'depends on stale {", ".join(hit)}', True
    return stale


def refresh(root, run, request_id, budgets=None, related=None):
    """Start a successor of a closed snapshot; carry forward unchanged records, mark the rest stale."""
    need(request_id, '--request-id is required for retry safety.')
    state, chain, closed = read(root, run)
    need(closed, f'{run} is still open; keep recording into it, or `close` it first.')
    snap = state['snapshot']
    keep = {label: r['path'] for label, r in snap['roots'].items() if label != sources.PRIMARY}
    keep.update(related or {})
    started = start(root, request_id, keep, snap['exclude'], snap['depth'], dict(snap['budgets'], **(budgets or {})),
                    f'{run}@{len(chain)}')
    new = started['run_id']
    now = journal(root).read(new)['snapshot']['roots']
    stale = invalidate(state, now, adopted(root))
    carried = []
    for rid, rec in sorted(state.get('records', {}).items()):
        out = {k: v for k, v in rec.items() if k not in ('accepted', 'supersedes', 'type', 'status', 'stale_reason',
                                                         'reused_from')}
        out['reused_from'] = f'{run}@{rec["accepted"]["revision"]}'
        if rid in stale:
            out.update(status='stale', stale_reason=stale[rid])
        carried.append(out)
    store = journal(root)
    for i in range(0, len(carried), records.MAX_RECORDS):
        payload = {'schema': records.SCHEMA, 'version': records.VERSION, 'records': carried[i:i + records.MAX_RECORDS],
                   'carried_from': f'{run}@{len(chain)}'}
        store.append(new, 'record.accepted', payload, None, f'{request_id}:carry:{i}',
                     snap['workspace']['project_key'])
    return {'run': new, 'predecessor': f'{run}@{len(chain)}', 'reused': len(carried) - len(stale),
            'stale': [{'id': k, 'reason': v} for k, v in sorted(stale.items())],
            'revision': len(store.history(new))}


def status(root, run=None):
    run = run or newest(root)
    if run is None:
        return {'snapshots': [], 'note': 'No recon snapshot yet; run `orient`, then `start`.'}
    state, chain, closed = read(root, run)
    snap = state['snapshot']
    changed = []
    for label, old in snap['roots'].items():
        path = Path(old['path'])
        if not path.is_dir() or sources.fingerprint(path, snap['exclude'] if label == sources.PRIMARY else ())[
                'fingerprint'] != old['fingerprint']:
            changed.append(label)
    recs = state.get('records', {}).values()
    return {'snapshots': runs(root), 'run': run, 'revision': len(chain), 'head': chain[-1]['event_id'],
            'closed': closed, 'depth': snap['depth'], 'roots': {k: v['path'] for k, v in snap['roots'].items()},
            'predecessor': snap.get('predecessor'), 'fresh': not changed, 'changed_roots': changed,
            'records': len(recs), 'stale': sum(1 for r in recs if r['status'] == 'stale'),
            'cost': state.get('cost'), 'budgets': snap['budgets']}


def successors(root, run):
    """Snapshot runs descended from `run`, oldest first."""
    out, frontier = [], {run}
    for r in runs(root):
        pred = (read(root, r)[0]['snapshot'].get('predecessor') or '').split('@')[0]
        if pred in frontier:
            out.append(r)
            frontier.add(r)
    return out


BOOKKEEPING = ('accepted', 'supersedes', 'reused_from', 'status', 'stale_reason')


def _content(rec):
    """What a record claims, without the bookkeeping that changes when it is carried forward."""
    return {k: v for k, v in rec.items() if k not in BOOKKEEPING}


def changed_refs(root, old_run, new_run, ids):
    """{id: reason} for ids a conclusion cited under snapshot `old_run` that are stale, gone, or
    re-recorded with different content in snapshot `new_run`."""
    pinned = read(root, old_run)[0].get('records', {}) if old_run else {}
    state = read(root, new_run)[0]
    recs = state.get('records', {})
    out = {}
    for rid in ids:
        if rid in state.get('dropped', {}):
            out[rid] = f'dropped in {new_run}: {state["dropped"][rid]["reason"]}'
        elif rid not in recs:
            out[rid] = f'not recorded in {new_run}'
        elif recs[rid]['status'] == 'stale':
            out[rid] = f'stale in {new_run}: {recs[rid].get("stale_reason", "")}'
        elif rid in pinned and _content(recs[rid]) != _content(pinned[rid]):
            out[rid] = f're-recorded in {new_run} with different content'
    return out


def stale_refs(root, run, ids):
    """changed_refs against the newest snapshot descended from the pinned `run`."""
    return changed_refs(root, run, (successors(root, run) or [run])[-1], ids)
