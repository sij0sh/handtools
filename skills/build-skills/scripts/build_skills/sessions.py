"""Session registry: load, save, add, find, select, close."""
from datetime import datetime, timezone
from pathlib import Path

from .config import AREA
from .storage import read_json, state_dir, write_json


def base_dir(root):
    return state_dir(AREA, root)


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')



def load_registry(root, allow_missing=False):
    path = base_dir(root) / 'workflow.json'
    if not path.exists():
        if allow_missing:
            return {'version': 1, 'root': str(root), 'sessions': []}
        raise ValueError('No sessions for this project. Run `start`.')
    state = read_json(path)
    if not isinstance(state, dict) or state.get('version') != 1 or not isinstance(state.get('sessions'), list):
        raise ValueError(f'{path} is not a version-1 registry.')
    return state



def save_registry(root, state):
    write_json(base_dir(root) / 'workflow.json', state)



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



def close(session, status):
    now = timestamp()
    session.update(status=status, phase='closed', completed=now, updated=now)


def work_dir(root, s, kind):
    """sN/<kind>/<skill name>: `draft` (working copy) or `backup` (revise: original)."""
    return base_dir(root) / s['id'] / kind / Path(s['target']).name
