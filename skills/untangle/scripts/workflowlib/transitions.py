"""State changes per accepted stage; each returns the next stage, or None after publishing."""
import time

from .ledger import (cover_lines, expand_specs, find_drift, find_root, in_scope_files, is_excluded, load_policy,
    need, unit_fingerprint, walk_tree)
from .work import all_items, budget, checkpoint_to, coverage_summary, next_work, reopen_items
from .exports import publish
from . import reconview


def on_inventory(state, payload):
    root = find_root()
    need(state.get('root', str(root)) == str(root), f'INVENTORY: this run belongs to {state.get("root")}.')
    state.setdefault('audit_id', time.strftime('audit-%Y%m%d-%H%M%S'))
    state.update(root=str(root), limits=payload['limits'], exclude=payload.get('exclude', []),
                 policy=load_policy())
    state['ledger'] = walk_tree(root, state['exclude'], state['limits'])
    state.setdefault('units', {})
    state.setdefault('flows', {})
    state.setdefault('findings', {})
    state.setdefault('counters', {'dissect': 0, 'units': 0, 'synth': 0, 'challenge': 0})
    return 'map'


def on_map(state, payload):
    old, kept = state['units'], set()
    chosen = reconview.pin(state, payload)
    refs = {}
    for f in state['findings'].values():
        refs.setdefault(f['item'], set()).update(f.get('recon_refs', []))
    units = {}
    for u in payload['units']:
        u = dict(u, paths=expand_specs(state, u['paths'], payload.get('exclusions', [])))
        fp = unit_fingerprint(state, cover_lines(state, u['paths'], 'MAP'))
        prior = old.get(u['id'], {})
        keep = prior.get('fingerprint') == fp and prior.get('status') == 'reviewed' and not prior.get('children')
        # A reviewed unit whose findings cite recon records that changed needs another pass.
        keep = keep and reconview.fresh_refs(state, sorted(refs.get(u['id'], ())), chosen)
        if keep:
            kept.add(u['id'])
        units[u['id']] = {'kind': 'unit', 'responsibility': u['responsibility'], 'paths': u['paths'],
                          'contracts': u.get('contracts', ''), 'depth': 0, 'fingerprint': fp,
                          'status': 'reviewed' if keep else 'pending', 'passes': prior.get('passes', 0) if keep else 0}
    state['units'] = units
    state['flows'] = {e['id']: {'kind': 'flow', 'where': e['where'], 'flow': e['flow'], 'status': 'pending'}
                      for e in payload['entry_points'] if e.get('flow')}
    state['findings'] = {k: f for k, f in state['findings'].items() if f['item'] in kept}
    state['counters']['units'] = max(state['counters']['units'], len(units))
    state['map'] = {k: payload.get(k, []) for k in ('conventions', 'observables', 'entry_points', 'exclusions')}
    state['recon'] = chosen
    state['map_rev'] = state['rev']
    state.pop('revise', None)
    return 'scope'


def on_scope(state, payload):
    if payload.get('revise'):
        state['revise'] = payload['revise']
        return 'map'
    for p in in_scope_files(state):
        reason = is_excluded(p, state['map']['exclusions'])
        if reason:
            state['ledger'][p].update(disposition='excluded', reason=f'{reason} (approved at SCOPE)')
    state['scope'] = {'budgets': payload['budgets'], 'allowed_commands': payload['allowed_commands'],
                      'approved_map_rev': state['map_rev']}
    state['queue'] = [i for i, it in all_items(state).items() if it['status'] == 'pending']
    return next_work(state)


def on_dissect(state, payload):
    head = state['queue'].pop(0)
    it = all_items(state)[head]
    state['counters']['dissect'] += 1
    state.setdefault('commands_run', []).extend(payload.get('commands_run', []))
    state['findings'] = {k: f for k, f in state['findings'].items() if f['item'] != head}
    for f in payload['findings']:
        state['findings'][f['id']] = dict(f, item=head)
    if 'children' in payload:
        it['children'] = [k['id'] for k in payload['children']]
        for k in payload['children']:
            k = dict(k, paths=expand_specs(state, k['paths']))
            state['units'][k['id']] = {'kind': 'unit', 'responsibility': k['responsibility'], 'paths': k['paths'],
                                       'contracts': k.get('contracts', ''), 'depth': it['depth'] + 1,
                                       'parent': head, 'status': 'pending', 'passes': 0,
                                       'fingerprint': unit_fingerprint(state,
                                                                       cover_lines(state, k['paths'], 'DISSECT'))}
        state['counters']['units'] += len(payload['children'])
        state['queue'][:0] = it['children'] + [head]
        return next_work(state)
    it['passes'] = it.get('passes', 0) + 1
    if 'blocked' in payload:
        it.update(status='blocked', blocked=payload['blocked'])
    else:
        it['status'] = 'reviewed'
        for k in ('trace', 'interactions'):
            if k in payload:
                it[k] = payload[k]
    return next_work(state)


def on_synthesize(state, payload):
    for k in ('recommendations', 'dismissed', 'waves'):
        state[k] = payload.get(k, [])
    reopen = payload.get('reopen', [])
    if not reopen:
        return 'challenge'
    reopen_items(state, reopen, 'SYNTHESIZE')
    state['counters']['synth'] += 1
    if state['counters']['synth'] > budget(state, 'synth_reopens'):
        return checkpoint_to(state, 'dissect', 'synth_reopens budget used')
    return next_work(state)


def on_challenge(state, payload):
    state['reviewer'] = payload['reviewer']
    state['objections'] = state.get('objections', []) + payload['objections']
    targets = [t for o in payload['objections'] if o['verdict'] == 'accepted' for t in o['reopen']]
    if targets:
        units = [t for t in targets if t != 'synthesize']
        reopen_items(state, units, 'CHALLENGE')
        state['counters']['challenge'] += 1
        resume = 'dissect' if units else 'synthesize'
        if state['counters']['challenge'] > budget(state, 'challenge_rounds'):
            return checkpoint_to(state, resume, 'challenge_rounds budget used')
        return next_work(state) if units else 'synthesize'
    diffs = find_drift(state)
    need(not diffs, 'CHALLENGE: source or policy changed since INVENTORY; a complete report is blocked: '
                     + '; '.join(diffs[:20]) + '. Send {"checkpoint": "drift"}.')
    gone = reconview.stale(state)
    need(not gone, 'CHALLENGE: cited recon records changed since MAP; a complete report is blocked: '
                   + '; '.join(f'{k}: {v}' for k, v in sorted(gone.items())[:20])
                   + '. Send {"checkpoint": "recon stale"}, then reinventory and pin the refreshed snapshot.')
    c = coverage_summary(state)
    reasons = [f'blocked: {", ".join(c["blocked"])}'] if c['blocked'] else []
    reasons += [f'pending: {", ".join(c["pending"])}'] if c['pending'] else []
    reasons += [f'{len(c["unreviewed"])} in-scope files unreviewed'] if c['unreviewed'] else []
    return publish(state, not reasons, reasons)


def _resume(state):
    target = state['checkpoint']['resume']
    nxt = next_work(state) if target == 'dissect' else target
    need(nxt != 'checkpoint', f'CHECKPOINT: the extension does not cover: {state["checkpoint"]["reason"]}.')
    return nxt


def on_checkpoint(state, payload):
    d = payload['decision']
    if d == 'reinventory':
        return 'inventory'
    if d == 'publish_incomplete':
        return publish(state, False, [f'published at checkpoint: {state["checkpoint"]["reason"]}'])
    state['scope']['budgets'].update(payload.get('budgets', {}))
    state['scope']['allowed_commands'] += [c for c in payload.get('allowed_commands', [])
                                           if c not in state['scope']['allowed_commands']]
    return _resume(state)
