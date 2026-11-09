"""Multi-session registry: <state root>/<area>/<project key>/workflow.json = {version: 1, sessions: [...]}.

Generic fields only: id (sN), status (active|complete|abandoned|...), created, updated, completed.
A skill adds its own fields through add(..., **fields) and keeps any validation of them.
"""
import re
from datetime import datetime, timezone

from . import storage


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def base(area, root):
    return storage.state_dir(area, root)


def path(area, root):
    return base(area, root) / 'workflow.json'


def empty():
    return {'version': 1, 'sessions': []}


def load(area, root, allow_missing=False):
    """The raw registry; callers validate their own fields."""
    file = path(area, root)
    if not file.exists():
        if allow_missing:
            return empty()
        raise ValueError('No sessions for this project. Run `start`.')
    return storage.read_json(file)


def save(area, root, state):
    storage.write_json(path(area, root), state)


def add(state, **fields):
    """Append an active session with the next sN id and the given fields; return it."""
    seen = [int(s['id'][1:]) for s in state['sessions'] if re.fullmatch(r's\d+', str(s.get('id')))]
    now = timestamp()
    session = {'id': f's{max(seen, default=0) + 1}', **fields, 'status': 'active',
               'created': now, 'updated': now, 'completed': None}
    state['sessions'].append(session)
    return session


def find(state, sid):
    for session in state['sessions']:
        if session['id'] == sid:
            return session
    raise ValueError(f'Session {sid} not found.')


def active(state):
    return [s for s in state['sessions'] if s['status'] == 'active']


def select_active(state, sid):
    if sid is not None:
        session = find(state, sid)
        if session['status'] != 'active':
            raise ValueError(f'Session {sid} is {session["status"]}; it cannot advance.')
        return session
    running = active(state)
    if not running:
        raise ValueError('No active session. Run `start`.')
    if len(running) > 1:
        raise ValueError(f'Several active sessions ({", ".join(s["id"] for s in running)}); pass --session sN.')
    return running[0]


def close(session, status, phase):
    """Mark a session finished: status, the skill's closed phase name, and completion time."""
    now = timestamp()
    session.update(status=status, phase=phase, completed=now, updated=now)
