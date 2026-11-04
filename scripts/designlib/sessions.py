"""workflow.json: the permanent session registry and the phase order."""
import re
from datetime import datetime, timezone

from . import record, storage

ORDER = ['ground', 'branch', 'decide', 'challenge']
CLOSED_PHASE = 'done'
FIELDS = ['id', 'goal', 'phase', 'cycle', 'status', 'baseline', 'created', 'updated', 'completed']


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def validate(state):
    if not isinstance(state, dict) or state.get('version') != 1:
        raise ValueError('Unsupported workflow version; expected version 1.')
    sessions = state.get('sessions')
    if not isinstance(sessions, list):
        raise ValueError('workflow.json sessions must be a list.')
    ids = set()
    active_goals = {}
    for session in sessions:
        if not isinstance(session, dict):
            raise ValueError('Each workflow session must be an object.')
        missing = [key for key in FIELDS if key not in session]
        if missing:
            raise ValueError(f'Workflow session is missing {missing}.')
        sid = session['id']
        if not isinstance(sid, str) or not re.fullmatch(r's\d+', sid) or sid in ids:
            raise ValueError(f'Session id {sid!r} must be unique s#.')
        ids.add(sid)
        status = session['status']
        phase = session['phase']
        if status not in ('active', 'complete', 'abandoned'):
            raise ValueError(f'{sid}.status must be active, complete, or abandoned.')
        if status == 'active':
            if phase not in ORDER:
                raise ValueError(f'{sid}.phase must be one of {ORDER} while active.')
            gid = session['goal']
            if gid is not None:
                if gid in active_goals:
                    raise ValueError(f'Goal {gid} is held by both {active_goals[gid]} and {sid}.')
                active_goals[gid] = sid
        elif phase != CLOSED_PHASE:
            raise ValueError(f'{sid}.phase must be {CLOSED_PHASE} after it closes.')
        if not isinstance(session['cycle'], int) or session['cycle'] < 1:
            raise ValueError(f'{sid}.cycle must be a positive integer.')
        if session['goal'] is not None and not isinstance(session['goal'], str):
            raise ValueError(f'{sid}.goal must be a string or null.')
        if session['baseline'] is not None and not isinstance(session['baseline'], str):
            raise ValueError(f'{sid}.baseline must be a string or null.')


def _normalize(root, raw):
    """Upgrade an old single-run state to a version-1 session list."""
    if isinstance(raw, dict) and 'sessions' in raw:
        state = {'version': raw.get('version'), 'sessions': raw['sessions']}
        validate(state)
        return state
    if not isinstance(raw, dict):
        raise ValueError('workflow.json must be an object.')
    phase = raw.get('phase')
    if phase not in ORDER + ['handoff']:
        raise ValueError(f'Old workflow phase {phase!r} is not recognized.')
    rec = record.load(root) if record.exists(root) else None
    now = timestamp()
    closed = phase == 'handoff'
    session = {
        'id': 's1',
        'goal': raw.get('goal'),
        'phase': CLOSED_PHASE if closed else phase,
        'cycle': raw.get('cycle', 1),
        'status': 'complete' if closed else 'active',
        'baseline': record.goal_hash(rec, raw.get('goal')),
        'created': now,
        'updated': now,
        'completed': now if closed else None,
    }
    state = {'version': 1, 'sessions': [session]}
    validate(state)
    return state


def load(root, allow_missing=False, persist_migration=False):
    path = root / storage.STATE
    if not path.exists():
        if allow_missing:
            return {'version': 1, 'sessions': []}
        raise ValueError('No workflow found. Run `start`.')
    raw = storage.read_json(path)
    state = _normalize(root, raw)
    if persist_migration and isinstance(raw, dict) and 'sessions' not in raw:
        with storage.lock(root):
            state = _normalize(root, storage.read_json(path))
            save(root, state)
    return state


def save(root, state):
    storage.write_json(root / storage.STATE, state)


def add(state):
    """Append a fresh session in ground and return it."""
    seen = [int(s['id'][1:]) for s in state['sessions'] if re.fullmatch(r's\d+', s['id'])]
    now = timestamp()
    session = {
        'id': f's{max(seen, default=0) + 1}',
        'goal': None,
        'phase': 'ground',
        'cycle': 1,
        'status': 'active',
        'baseline': None,
        'created': now,
        'updated': now,
        'completed': None,
    }
    state['sessions'].append(session)
    return session


def find(state, sid):
    for session in state['sessions']:
        if session['id'] == sid:
            return session
    raise ValueError(f'Session {sid} not found.')


def active(state):
    return [s for s in state['sessions'] if s['status'] == 'active']


def holders(state):
    """Map each goal held by an active session to that session's id."""
    return {s['goal']: s['id'] for s in active(state) if s['goal']}


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
        names = ', '.join(s['id'] for s in running)
        raise ValueError(f'Several active sessions ({names}); pass --session ID.')
    return running[0]


def close(session, status, now):
    session['phase'] = CLOSED_PHASE
    session['status'] = status
    session['completed'] = now
    session['updated'] = now
