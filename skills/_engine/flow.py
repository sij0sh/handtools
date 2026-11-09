"""Single-run workflow commands: start, status, done, abandon.

`steps` is the skill's own module. It defines MODE ('stateful': one run per project, saved in
<state root>/<AREA>/<project key>/workflow.json; 'stateless': nothing saved, `done --stage S`
names the finished step), AREA, ORDER, PROMPTS (text, or a function of the project root),
CHECKS, advance(state, payload) and DONE_MSG, and optionally on_abandon(state, root) -> note.
Every state passed to a check, to advance or to on_abandon carries 'phase' and 'root'.
"""
from . import storage, planning


def _base(steps, root):
    return storage.state_dir(steps.AREA, root)


def _path(steps, root):
    return _base(steps, root) / 'workflow.json'


def _load(steps, root):
    if not storage.has_state(_path(steps, root)):
        raise ValueError('No workflow in progress. Run `start`.')
    return storage.read_state(_path(steps, root))


def show(steps, phase, root, launcher):
    prompt = steps.PROMPTS[phase]
    text = prompt(root) if callable(prompt) else prompt
    text += '\n\n' + planning.prompt()
    stage = f' --stage {phase}' if steps.MODE == 'stateless' else ''
    return (f'STEP: {phase.upper()}\n{text}\n\n'
            f'Then run: {launcher} done{stage}  (pipe a JSON payload on stdin when the step asks for one)')


def start(steps, root, launcher):
    if steps.MODE == 'stateless':
        return show(steps, steps.ORDER[0], root, launcher)
    with storage.lock(_base(steps, root)):
        if storage.has_state(_path(steps, root)):
            raise ValueError('A run is unfinished; run `status` to resume or `abandon` to discard it.')
        state = {'phase': steps.ORDER[0], 'root': str(root)}
        storage.write_state(_path(steps, root), state)
    return show(steps, state['phase'], root, launcher)


def status(steps, root, launcher):
    if steps.MODE == 'stateless':
        raise ValueError('Stateless: nothing saved; run `start`, or `done --stage S` for the step you finished.')
    return show(steps, _load(steps, root)['phase'], root, launcher)


def _step(steps, state, payload):
    payload = {} if payload is None else payload
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object.')
    if getattr(steps, 'PLANNING', False) and state['phase'] == steps.ORDER[0]:
        state['plan_digest'] = planning.require_ready(payload.get('plan'))
        state['plan'] = payload['plan']
    check = steps.CHECKS.get(state['phase'])
    if check:
        check(state, payload)
    return steps.advance(state, payload)


def done(steps, root, payload, launcher, stage=None):
    if steps.MODE == 'stateless':
        if stage not in steps.ORDER:
            raise ValueError(f'Stateless: pass `--stage S`, S one of {", ".join(steps.ORDER)}.')
        nxt = _step(steps, {'phase': stage, 'root': str(root)}, payload)
        return steps.DONE_MSG if nxt is None else show(steps, nxt, root, launcher)
    if stage:
        raise ValueError('Stateful: omit `--stage`; the script tracks the step.')
    with storage.lock(_base(steps, root)):
        state = _load(steps, root)
        state.setdefault('root', str(root))
        nxt = _step(steps, state, payload)
        if nxt is None:
            storage.delete_state(_path(steps, root))
            return steps.DONE_MSG
        state['phase'] = nxt
        storage.write_state(_path(steps, root), state)
    return show(steps, nxt, root, launcher)


def abandon(steps, root):
    if steps.MODE == 'stateless':
        raise ValueError('Stateless: nothing saved, nothing to abandon.')
    with storage.lock(_base(steps, root)):
        state = _load(steps, root)
        state.setdefault('root', str(root))
        # Optional hook: a skill records what the cancelled run covered before its state is closed.
        hook = getattr(steps, 'on_abandon', None)
        note = hook(state, root) if hook else None
        storage.delete_state(_path(steps, root))
    return 'Run abandoned.' + (f' {note}' if note else '')
