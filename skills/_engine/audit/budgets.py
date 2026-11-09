"""Named finite budgets for a run: approval, spending and the checkpoint a spent budget forces.

State keys: state['budgets'] (approved limits), state['counters'] (spent), state['checkpoint']
({'resume': stage, 'reason': text}) when a budget stops the run.
"""


def need(cond, msg):
    if not cond:
        raise ValueError(msg)


def approve(given, names, where, partial=False):
    """Validate a {name: positive int} dict; all `names` unless `partial`."""
    need(isinstance(given, dict), f'{where}: `budgets` must be an object.')
    unknown = sorted(set(given) - set(names))
    need(not unknown, f'{where}: unknown budget(s) {", ".join(unknown)}; budgets are {", ".join(names)}.')
    missing = [] if partial else [n for n in names if n not in given]
    need(not missing, f'{where}: budgets need {", ".join(missing)}.')
    need(all(type(v) is int and v > 0 for v in given.values()), f'{where}: budgets are positive integers.')
    return dict(given)


def spent(state, name):
    return state.setdefault('counters', {}).get(name, 0)


def spend(state, name, amount=1):
    state.setdefault('counters', {})[name] = spent(state, name) + amount


def exhausted(state, name):
    return spent(state, name) >= state['budgets'][name]


def checkpoint_to(state, resume, reason):
    state['checkpoint'] = {'resume': resume, 'reason': reason}
    return 'checkpoint'
