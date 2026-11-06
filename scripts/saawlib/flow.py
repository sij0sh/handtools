"""Commands: start, done, status, abandon."""
from .config import DONE_MSG
from .prompts import render, summary
from .sessions import active, close, find, load_registry, save_registry, select_active, timestamp
from .stages import PHASES
from .storage import base_dir, lock


def cmd_start(root, launcher):
    with lock(base_dir(root)):
        state = load_registry(root, allow_missing=True)
        number = max((int(s['id'][1:]) for s in state['sessions']), default=0) + 1
        now = timestamp()
        session = {'id': f's{number}', 'status': 'active', 'phase': 'ground',
                   'created': now, 'updated': now, 'completed': None}
        state['sessions'].append(session)
        save_registry(root, state)
    return render(root, session, launcher)


def cmd_done(root, sid, payload, launcher):
    payload = {} if payload is None else payload
    if not isinstance(payload, dict):
        raise ValueError('Payload must be a JSON object.')
    with lock(base_dir(root)):
        state = load_registry(root)
        s = select_active(state, sid)
        PHASES[s['phase']](root, state, s, payload)
        s['updated'] = timestamp()
        save_registry(root, state)
    if s['status'] == 'complete':
        return f'{summary(root, s)}\n\n{DONE_MSG}'
    return render(root, s, launcher)


def cmd_status(root, sid, show_all, launcher):
    if sid is not None and show_all:
        raise ValueError('Use either --session or --all, not both.')
    state = load_registry(root)
    if sid is None:
        listed = state['sessions'] if show_all else active(state)
        if not listed:
            return 'No sessions.' if show_all else 'No active sessions.'
        return '\n'.join(f'{s["id"]}  {s["status"]:<9} {s["phase"]:<9} {s.get("target") or "-"}' for s in listed)
    s = find(state, sid)
    if s['status'] == 'active':
        return render(root, s, launcher)
    return f'STATUS: {s["status"]}\n{summary(root, s)}'


def cmd_abandon(root, sid):
    with lock(base_dir(root)):
        state = load_registry(root)
        s = find(state, sid)
        if s['status'] != 'active':
            raise ValueError(f'Session {sid} is {s["status"]}; it is already closed.')
        close(s, 'abandoned')
        save_registry(root, state)
    return f'Session {sid} abandoned; record kept; target untouched.'
