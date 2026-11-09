"""State changes per accepted stage. Each validates its payload, changes state, and returns the next
stage, or None after the report is written. A refused payload leaves the saved state untouched."""
import time
from pathlib import Path

from _engine.audit import budgets, candidates, evidence, obligations, packs
from _engine.recon import pin
from . import checks, report, verdicts

need, text = evidence.need, evidence.text


def _list(payload, key, where, cap=None, required=False):
    value = payload.get(key, None if required else [])
    need(isinstance(value, list), f'{where}: `{key}` must be a list.')
    need(cap is None or len(value) <= cap, f'{where}: at most {cap} `{key}` per step.')
    return value


def _commands(state, payload, where):
    for run in _list(payload, 'commands_run', where, cap=evidence.MAX_REFS):
        state['commands'].append(evidence.command_run(run, checks.allowed(state), where))


def _recon_refs(state, items, where):
    snap = pin.snapshot(Path(state['root']), state.get('recon'))
    for item in items:
        pin.check_refs(snap, item.get('recon_refs', []) if isinstance(item, dict) else [], where)


def next_work(state):
    """Open candidates first, then planned obligations, then CHALLENGE; a spent budget forces CHECKPOINT."""
    if candidates.open_ids(state['candidates']):
        if budgets.exhausted(state, 'validate_transitions'):
            return budgets.checkpoint_to(state, 'work', 'validate_transitions budget used')
        return 'validate'
    if obligations.queue(state['obligations']):
        if budgets.exhausted(state, 'hunt_transitions'):
            return budgets.checkpoint_to(state, 'work', 'hunt_transitions budget used')
        return 'hunt'
    return 'challenge'


def reopen(state, changed, why):
    """Reopen exactly the items that cite a changed path; a test gap citing one is withdrawn and its
    obligation reopened. Returns the ids touched."""
    touched = []
    for item_id, (_, paths) in sorted(checks.cited(state).items()):
        if not paths & set(changed):
            continue
        touched.append(item_id)
        if item_id in state['obligations']:
            obligations.reopen(state['obligations'][item_id], why)
        elif item_id in state['candidates']:
            candidates.reopen(state['candidates'][item_id], why)
        else:
            gap = state['test_gaps'].pop(item_id)
            obligations.reopen(state['obligations'][gap['obligation']], f'{why} (withdrew {item_id})')
    return touched


def _rehash(state, root):
    """After reframe: cited working-tree refs take their current hashes (None when the file is gone)."""
    for refs, _ in checks.cited(state).values():
        for r in refs:
            r['sha256'] = evidence.content_hash(root, r['path'])


def guard_drift(state, root):
    """Before applying any payload after FRAME: changed sources reopen what cites them and stop the run."""
    changed = checks.drift(state, root)
    if not changed:
        return None
    touched = reopen(state, changed, 'source changed: ' + ', '.join(changed[:10]))
    return budgets.checkpoint_to(state, 'frame', f'drift: {", ".join(changed[:20])} changed since FRAME; reopened '
                                 f'{", ".join(touched) or "nothing"}. The payload was not applied; reframe.')


def on_frame(state, payload):
    root = Path(state['root'])
    frame, limits = checks.frame(root, payload)
    need(limits['max_obligations'] <= obligations.HARD_CAP, f'FRAME: max_obligations is at most {obligations.HARD_CAP}.')
    again = 'frame' in state
    state.setdefault('run_id', time.strftime('review-%Y%m%d-%H%M%S'))
    state.update(frame=frame, budgets=limits)
    for key, empty in (('obligations', {}), ('candidates', {}), ('test_gaps', {}), ('commands', []),
                       ('objections', []), ('used', []), ('counters', {})):
        state.setdefault(key, empty)
    if again:
        _rehash(state, root)
    state.pop('checkpoint', None)
    return 'recon'


def on_recon(state, payload):
    state['recon'] = pin.choose(Path(state['root']), payload, 'RECON')
    return 'obligations'


def on_obligations(state, payload):
    w = 'OBLIGATIONS'
    items = _list(payload, 'obligations', w)
    _recon_refs(state, items, w)
    used = set(state['used'])
    obligations.add(state['obligations'], items, packs.load(state['frame']['packs']), state['frame']['mode'],
                    state['budgets']['max_obligations'], used, w)
    need(state['obligations'], f'{w}: list at least one obligation.')
    state['used'] = sorted(used)
    return next_work(state)


def on_hunt(state, payload):
    w, root = 'HUNT', Path(state['root'])
    results = _list(payload, 'results', w, cap=checks.HUNT_BATCH, required=True)
    need(results, f'{w}: report at least one obligation in `results`.')
    queue = obligations.queue(state['obligations'])
    ids = [r.get('id') if isinstance(r, dict) else None for r in results]
    need(len(set(ids)) == len(ids) and all(i in queue for i in ids),
         f'{w}: `results` name distinct open obligations; open: {", ".join(queue)}.')
    used, issued = set(state['used']), {i: [] for i in ids}
    new_c = _list(payload, 'candidates', w, cap=evidence.MAX_REFS)
    new_t = _list(payload, 'test_gaps', w, cap=evidence.MAX_REFS)
    _recon_refs(state, new_c, w)
    for c in new_c:
        need(isinstance(c, dict) and c.get('obligation') in issued, f'{w}: each candidate names an `obligation` in results.')
        issued[c['obligation']].append(candidates.propose(state['candidates'], c, c['obligation'], root, used, w))
    for t in new_t:
        need(isinstance(t, dict) and t.get('obligation') in issued, f'{w}: each test gap names an `obligation` in results.')
        issued[t['obligation']].append(verdicts.test_gap(state['test_gaps'], t, t['obligation'], root, used, w))
    for r in results:
        obligations.resolve(state['obligations'][r['id']], r, root, issued[r['id']], f'{w} {r["id"]}')
    _commands(state, payload, w)
    state['used'] = sorted(used)
    budgets.spend(state, 'hunt_transitions')
    return next_work(state)


def on_validate(state, payload):
    w = 'VALIDATE'
    items = _list(payload, 'candidates', w, cap=checks.VALIDATE_BATCH, required=True)
    need(items, f'{w}: handle at least one open candidate.')
    open_ids = candidates.open_ids(state['candidates'])
    judge = verdicts.judge_for(state, Path(state['root']))
    for item in items:
        need(isinstance(item, dict) and item.get('id') in open_ids,
             f'{w}: each entry names an open candidate; open: {", ".join(open_ids)}.')
        need('attempt' in item or 'verdict' in item, f'{w} {item["id"]}: send an `attempt`, a `verdict`, or both.')
        cand = state['candidates'][item['id']]
        cand['state'] = 'validating'
        if 'attempt' in item:
            candidates.attempt(cand, item['attempt'], checks.allowed(state), state['budgets']['attempts_per_candidate'],
                               f'{w} {item["id"]}')
        if 'verdict' in item:
            candidates.settle(cand, item['verdict'], judge, f'{w} {item["id"]}')
    variants = _list(payload, 'variants', w)
    if variants:
        need(budgets.spent(state, 'variant_obligations') + len(variants) <= state['budgets']['variant_obligations'],
             f'{w}: variant_obligations budget would be exceeded; send {{"checkpoint": "reason"}} to ask for more.')
        _recon_refs(state, variants, w)
        used = set(state['used'])
        obligations.add(state['obligations'], variants, packs.load(state['frame']['packs']), state['frame']['mode'],
                        state['budgets']['max_obligations'], used, f'{w} variants')
        state['used'] = sorted(used)
        budgets.spend(state, 'variant_obligations', len(variants))
    _commands(state, payload, w)
    budgets.spend(state, 'validate_transitions')
    return next_work(state)


def _to_report(state, forced=None):
    gone = report.stale_recon(state)
    if gone and not forced:
        for kind, items in ((obligations, state['obligations']), (candidates, state['candidates'])):
            for item in items.values():
                if set(item.get('recon_refs', [])) & set(gone):
                    kind.reopen(item, 'cited recon records changed')
        return budgets.checkpoint_to(state, 'frame', 'recon stale: ' + '; '.join(f'{k}: {v}' for k, v in sorted(gone.items()))
                                     + '. Refresh the snapshot, then reframe and pin it at RECON.')
    report.decide(state, forced)
    return 'report'


def on_challenge(state, payload):
    w = 'CHALLENGE'
    need(payload.get('reviewer') in ('fresh', 'self'), f'{w}: reviewer is fresh|self.')
    objections = _list(payload, 'objections', w, required=True)
    known = {**state['obligations'], **state['candidates'], **state['test_gaps']}
    accepted = []
    for o in objections:
        need(isinstance(o, dict) and o.get('verdict') in ('accepted', 'rejected'),
             f'{w}: each objection has verdict accepted|rejected.')
        text(o, 'claim', w)
        text(o, 'reason', w)
        targets = _list(o, 'reopen', w)
        need(all(t in known for t in targets), f'{w}: `reopen` names obligations, candidates or test gaps.')
        need(o['verdict'] == 'accepted' or not targets, f'{w}: only an accepted objection reopens work.')
        accepted += targets
    state['reviewer'] = payload['reviewer']
    state['objections'] = state['objections'] + [{k: o[k] for k in ('claim', 'verdict', 'reason')}
                                                 | {'reopen': o.get('reopen', [])} for o in objections]
    if not accepted:
        return _to_report(state)
    for t in sorted(set(accepted)):
        if t in state['obligations']:
            obligations.reopen(state['obligations'][t], 'challenge objection accepted')
        elif t in state['candidates']:
            candidates.reopen(state['candidates'][t], 'challenge objection accepted')
        else:
            gap = state['test_gaps'].pop(t)
            obligations.reopen(state['obligations'][gap['obligation']], f'challenge withdrew {t}')
    budgets.spend(state, 'challenge_rounds')
    if budgets.spent(state, 'challenge_rounds') > state['budgets']['challenge_rounds']:
        return budgets.checkpoint_to(state, 'work', 'challenge_rounds budget used')
    return next_work(state)


def on_report(state, payload):
    report.write(state, state['root'])
    return None


def on_checkpoint(state, payload):
    w = 'CHECKPOINT'
    need(payload.get('approved_by_user') is True, f'{w}: needs the user\'s explicit decision: `"approved_by_user": true`.')
    d = payload.get('decision')
    need(d in ('extend', 'reframe', 'publish_incomplete'), f'{w}: decision is extend|reframe|publish_incomplete.')
    reason = state['checkpoint']['reason']
    if d == 'reframe':
        return 'frame'
    if d == 'publish_incomplete':
        state.pop('checkpoint')
        report.decide(state, forced=reason)
        return 'report'
    more = budgets.approve(payload.get('budgets', {}), checks.BUDGETS, w, partial=True)
    state['budgets'].update(more)
    cmds = checks.commands(payload.get('allowed_commands', []), w)
    state['frame']['allowed_commands'] += [c for c in cmds if c['command'] not in checks.allowed(state)]
    if payload.get('scope'):
        checks.extend_scope(state, Path(state['root']), _list(payload, 'scope', w), w)
    resume = state.pop('checkpoint')['resume']
    nxt = 'frame' if resume == 'frame' else next_work(state) if resume == 'work' else resume
    need(nxt != 'checkpoint', f'{w}: the extension does not cover: {reason}.')
    return nxt
