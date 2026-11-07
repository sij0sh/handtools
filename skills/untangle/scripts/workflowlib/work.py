"""Work queue: units and flows, budgets, checkpoints, coverage accounting."""
from .ledger import cover_lines, in_scope_files, need, parse_spec


def all_items(state):
    return {**state['units'], **state['flows']}


def budget(state, key):
    return state['scope']['budgets'][key]


def checkpoint_to(state, resume, reason):
    state['checkpoint'] = {'resume': resume, 'reason': reason}
    return 'checkpoint'


def next_work(state):
    """After the queue changes: next item, SYNTHESIZE, or CHECKPOINT when a budget is spent."""
    if not state['queue']:
        return 'synthesize'
    head = all_items(state)[state['queue'][0]]
    if state['counters']['dissect'] >= budget(state, 'dissect_transitions'):
        return checkpoint_to(state, 'dissect', 'dissect_transitions budget used')
    if head.get('passes', 0) >= budget(state, 'passes_per_unit'):
        return checkpoint_to(state, 'dissect', f'{state["queue"][0]} reached passes_per_unit')
    return 'dissect'


def reopen_items(state, ids, where):
    items = all_items(state)
    for i in ids:
        need(i in items, f'{where}: reopen `{i}` is not a unit or flow.')
        items[i]['status'] = 'pending'
        if i not in state['queue']:
            state['queue'].insert(0, i)


def coverage_summary(state):
    scope = in_scope_files(state)
    done = {}
    for u in state['units'].values():
        if u['status'] == 'reviewed' and not u.get('children'):
            for p, lines in cover_lines(state, u['paths'], 'coverage').items():
                done.setdefault(p, set()).update(lines)
    reviewed = {p for p in scope if done.get(p, set()) >= (parse_spec(state, p, 'coverage')[1])}
    excluded = {p: e['reason'] for p, e in state['ledger'].items() if e['disposition'] == 'excluded'}
    blocked = [i for i, it in all_items(state).items() if it['status'] == 'blocked']
    pending = [i for i, it in all_items(state).items() if it['status'] == 'pending']
    return {'discovered': len(state['ledger']), 'in_scope': len(scope), 'reviewed': len(reviewed),
            'unreviewed': sorted(scope - reviewed), 'excluded': excluded, 'blocked': blocked, 'pending': pending}
