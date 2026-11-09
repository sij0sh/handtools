"""Commands: start, status, done, abandon. Stateful: one run per project. Stateless: nothing saved."""
from . import steps, storage


def _base(root):
    return storage.state_dir(steps.AREA, root)


def _path(root):
    return _base(root) / 'workflow.json'


def _load(root):
    if not _path(root).exists():
        raise ValueError('No workflow in progress. Run `start`.')
    return storage.read_json(_path(root))


def show(phase, launcher):
    stage = f' --stage {phase}' if steps.MODE == 'stateless' else ''
    return (f'STEP: {phase.upper()}\n{steps.PROMPTS[phase]}\n\n'
            f'Then run: {launcher} done{stage}  (pipe a JSON payload on stdin when the step asks for one)')


def start(root, launcher):
    if steps.MODE == 'stateless':
        return show(steps.ORDER[0], launcher)
    with storage.lock(_base(root)):
        if _path(root).exists():
            raise ValueError('A run is unfinished; run `status` to resume or `abandon` to discard it.')
        state = {'phase': steps.ORDER[0]}
        storage.write_json(_path(root), state)
    return show(state['phase'], launcher)


def status(root, launcher):
    if steps.MODE == 'stateless':
        raise ValueError('Stateless: nothing saved; run `start`, or `done --stage S` for the step you finished.')
    return show(_load(root)['phase'], launcher)


def _step(state, payload):
    payload = {} if payload is None else payload
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object.')
    check = steps.CHECKS.get(state['phase'])
    if check:
        check(state, payload)
    return steps.advance(state, payload)


def done(root, payload, launcher, stage=None):
    if steps.MODE == 'stateless':
        if stage not in steps.ORDER:
            raise ValueError(f'Stateless: pass `--stage S`, S one of {", ".join(steps.ORDER)}.')
        nxt = _step({'phase': stage}, payload)
        return steps.DONE_MSG if nxt is None else show(nxt, launcher)
    if stage:
        raise ValueError('Stateful: omit `--stage`; the script tracks the step.')
    with storage.lock(_base(root)):
        state = _load(root)
        nxt = _step(state, payload)
        if nxt is None:
            _path(root).unlink()
            return steps.DONE_MSG
        state['phase'] = nxt
        storage.write_json(_path(root), state)
    return show(nxt, launcher)


def abandon(root):
    if steps.MODE == 'stateless':
        raise ValueError('Stateless: nothing saved, nothing to abandon.')
    with storage.lock(_base(root)):
        _load(root)
        _path(root).unlink()
    return 'Run abandoned.'
