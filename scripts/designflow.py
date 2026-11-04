#!/usr/bin/env python3
"""State machine that drives the simple-by-design loop.

Run from the project root. Requires Python 3.9+; standard library only.

Files (under .agents/design/):
  decisions.json  ongoing record, one set per goal (source of truth)
  workflow.json   permanent session registry; owned by the script
  workflow.lock   short-lived lock directory around workflow.json writes
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DESIGN = Path('.agents/design')
RECORD = DESIGN / 'decisions.json'
STATE = DESIGN / 'workflow.json'
LOCK = DESIGN / 'workflow.lock'

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULTS = SKILL_DIR / 'references' / 'defaults.md'
CONTRACT = SKILL_DIR / 'references' / 'contract.md'
SCHEMA = SKILL_DIR / 'references' / 'decisions.schema.json'
LANGUAGES = SKILL_DIR / 'languages'
SKILLS = LANGUAGES / 'skills.md'

ORDER = ['ground', 'branch', 'decide', 'challenge']
CLOSED_PHASE = 'done'
LOCK_TIMEOUT = 5.0
LOCK_STALE = 30.0

PROMPTS = {
    'ground': (
        'Establish the goal, constraints, success criteria, and relevant existing '
        'decisions or code. In decisions.json, add a new goal set with the next G#, '
        'or reuse the earlier set for the same goal. Choose a goal that no other '
        'active session holds. Schema: {schema}\n'
        'Then run `done --goal G#`.\n\n'
        'Defaults ({defaults}):\n\n{defaults_text}'
    ),
    'branch': (
        'In goal {goal}, list open material questions as decisions with status '
        '`open` and stable D# IDs. Link a dependency with `after` when one answer '
        'requires another. Update decisions.json.'
    ),
    'decide': (
        'In goal {goal}, resolve questions whose dependencies are settled. Settle '
        'each question from the first source that answers it:\n'
        '1. Requirements and adopted decisions.\n'
        '2. Existing project conventions that fit the goal. Replace one only '
        'through an explicit decision.\n'
        '3. Defaults: {defaults} (re-read if not in context).\n'
        '4. The relevant reference:\n'
        '   - Ownership, contracts, dependencies, boundaries, or failures: {contract}\n'
        '   - Language-specific design, types, errors, or concurrency: '
        '{languages}/<language>.md (available: {language_list})\n'
        '   - Skill design or structure: {skills}\n'
        '5. The simplest adequate choice.\n'
        'Ask the user when essential intent, permissions, or a consequential '
        'tradeoff stays unanswered by all five.\n'
        'Set resolved rows to status `resolved` with an `answer`; add a `rationale` '
        'for each non-obvious choice. Add questions the answers raise; drop '
        'questions that became irrelevant. Update decisions.json.'
    ),
    'challenge': (
        'Imagine two competent SWEs following every decision in goal {goal}. If '
        'they could make materially different choices, add the missing questions '
        'as open decisions with dependencies. Update decisions.json. Then run '
        '`done --gaps N`, where N is the count of remaining material gaps; N is 0 '
        'only when no two SWEs could implement a materially different solution '
        'following the decisions.'
    ),
}

DONE_MSG = 'DONE: present this summary to the user and stop; do not implement without approval.'


def prompt(session):
    phase = session['phase']
    names = sorted(p.stem for p in LANGUAGES.glob('*.md') if p != SKILLS)
    text = PROMPTS[phase].format(
        goal=session.get('goal'),
        schema=SCHEMA,
        defaults=DEFAULTS,
        defaults_text=DEFAULTS.read_text(encoding='utf-8').strip() if phase == 'ground' else '',
        contract=CONTRACT,
        languages=LANGUAGES,
        language_list=', '.join(names),
        skills=SKILLS,
    )
    if phase == 'ground':
        text += '\nRead decisions.json before editing. Add or reuse only this session\'s goal; leave every other goal unchanged.'
    else:
        text += f'\nRead decisions.json before editing. Edit only goal {session["goal"]}; leave every other goal unchanged.'
    return text


# --- decisions.json -------------------------------------------------------

def _strings(value, where):
    if not isinstance(value, list) or not all(isinstance(s, str) and s for s in value):
        raise ValueError(f'{where} must be a list of nonempty strings.')


def _keys(obj, where, required, optional):
    if not isinstance(obj, dict):
        raise ValueError(f'{where} must be an object.')
    missing = [k for k in required if k not in obj]
    extra = [k for k in obj if k not in required + optional]
    if missing or extra:
        raise ValueError(f'{where}: missing {missing}, unknown {extra}.')


def validate(record):
    """Check record against references/decisions.schema.json, plus cross-references."""
    _keys(record, 'record', ['goals'], [])
    if not isinstance(record['goals'], list):
        raise ValueError('goals must be a list.')
    goal_ids = set()
    for g in record['goals']:
        _keys(g, 'goal', ['id', 'goal', 'decisions'], ['constraints', 'criteria'])
        gid = g['id']
        if not isinstance(gid, str) or not re.fullmatch(r'G\d+', gid) or gid in goal_ids:
            raise ValueError(f'goal id {gid!r} must be unique G#.')
        goal_ids.add(gid)
        if not isinstance(g['goal'], str) or not g['goal']:
            raise ValueError(f'{gid}.goal must be a nonempty string.')
        for key in ('constraints', 'criteria'):
            if key in g:
                _strings(g[key], f'{gid}.{key}')
        if not isinstance(g['decisions'], list):
            raise ValueError(f'{gid}.decisions must be a list.')
        ids = []
        for d in g['decisions']:
            _keys(d, f'{gid} decision', ['id', 'question', 'status'], ['answer', 'after', 'rationale'])
            did = d['id']
            if not isinstance(did, str) or not re.fullmatch(r'D\d+', did) or did in ids:
                raise ValueError(f'{gid}: decision id {did!r} must be unique D#.')
            ids.append(did)
            where = f'{gid}.{did}'
            if not isinstance(d['question'], str) or not d['question']:
                raise ValueError(f'{where}.question must be a nonempty string.')
            if d['status'] not in ('open', 'resolved'):
                raise ValueError(f'{where}.status must be "open" or "resolved".')
            if d['status'] == 'resolved' and not d.get('answer'):
                raise ValueError(f'{where} is resolved but has no answer.')
            for key in ('answer', 'rationale'):
                if key in d and (not isinstance(d[key], str) or not d[key]):
                    raise ValueError(f'{where}.{key} must be a nonempty string.')
            if 'after' in d:
                _strings(d['after'], f'{where}.after')
        for d in g['decisions']:
            for dep in d.get('after', []):
                if dep == d['id'] or dep not in ids:
                    raise ValueError(f'{gid}.{d["id"]}.after: {dep} is not another decision in {gid}.')


def load_record(root):
    record = json.loads((root / RECORD).read_text(encoding='utf-8'))
    validate(record)
    return record


def find_goal(record, gid):
    for g in record['goals']:
        if g['id'] == gid:
            return g
    raise ValueError(f'Goal {gid} not found in decisions.json.')


def goal_hash(record, gid):
    """Return a hash of one goal, or None when the goal is absent."""
    if record is None or gid is None:
        return None
    for g in record['goals']:
        if g['id'] == gid:
            data = json.dumps(g, sort_keys=True, separators=(',', ':')).encode('utf-8')
            return hashlib.sha256(data).hexdigest()
    return None


# --- workflow.json --------------------------------------------------------

def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def next_session_id(state):
    seen = 0
    for session in state['sessions']:
        match = re.fullmatch(r's(\d+)', session['id'])
        if match:
            seen = max(seen, int(match.group(1)))
    return f's{seen + 1}'


def validate_sessions(state):
    if not isinstance(state, dict) or state.get('version') != 1:
        raise ValueError('Unsupported workflow version; expected version 1.')
    sessions = state.get('sessions')
    if not isinstance(sessions, list):
        raise ValueError('workflow.json sessions must be a list.')
    ids = set()
    active_goals = {}
    fields = ['id', 'goal', 'phase', 'cycle', 'status', 'baseline',
              'created', 'updated', 'completed']
    for session in sessions:
        if not isinstance(session, dict):
            raise ValueError('Each workflow session must be an object.')
        missing = [key for key in fields if key not in session]
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


def normalize_workflow(root, raw):
    """Upgrade an old single-run state to a version-1 session list."""
    if isinstance(raw, dict) and 'sessions' in raw:
        state = {'version': raw.get('version'), 'sessions': raw['sessions']}
        validate_sessions(state)
        return state

    if not isinstance(raw, dict):
        raise ValueError('workflow.json must be an object.')
    phase = raw.get('phase')
    if phase not in ORDER + ['handoff']:
        raise ValueError(f'Old workflow phase {phase!r} is not recognized.')
    record = load_record(root) if (root / RECORD).exists() else None
    now = timestamp()
    closed = phase == 'handoff'
    session = {
        'id': 's1',
        'goal': raw.get('goal'),
        'phase': CLOSED_PHASE if closed else phase,
        'cycle': raw.get('cycle', 1),
        'status': 'complete' if closed else 'active',
        'baseline': goal_hash(record, raw.get('goal')),
        'created': now,
        'updated': now,
        'completed': now if closed else None,
    }
    state = {'version': 1, 'sessions': [session]}
    validate_sessions(state)
    return state


def load_workflow(root, allow_missing=False, persist_migration=False):
    path = root / STATE
    if not path.exists():
        if allow_missing:
            return {'version': 1, 'sessions': []}
        raise ValueError('No workflow found. Run `start`.')
    raw = json.loads(path.read_text(encoding='utf-8'))
    state = normalize_workflow(root, raw)
    if persist_migration and isinstance(raw, dict) and 'sessions' not in raw:
        with workflow_lock(root):
            raw = json.loads(path.read_text(encoding='utf-8'))
            state = normalize_workflow(root, raw)
            save_workflow(root, state)
    return state


def save_workflow(root, state):
    write_json(root / STATE, state)


@contextmanager
def workflow_lock(root):
    lock = root / LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue
            if age > LOCK_STALE:
                try:
                    lock.rmdir()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise ValueError(f'Workflow is locked by {lock}; retry shortly.')
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock.rmdir()
        except FileNotFoundError:
            pass


def find_session(state, sid):
    for session in state['sessions']:
        if session['id'] == sid:
            return session
    raise ValueError(f'Session {sid} not found.')


def active_sessions(state):
    return [s for s in state['sessions'] if s['status'] == 'active']


def select_active(state, sid):
    if sid is not None:
        session = find_session(state, sid)
        if session['status'] != 'active':
            raise ValueError(f'Session {sid} is {session["status"]}; it cannot advance.')
        return session
    active = active_sessions(state)
    if not active:
        raise ValueError('No active session. Run `start`.')
    if len(active) > 1:
        names = ', '.join(s['id'] for s in active)
        raise ValueError(f'Several active sessions ({names}); pass --session ID.')
    return active[0]


def quote(text):
    """Quote one argument for the shell that will run the printed command."""
    if os.name == 'nt':
        return subprocess.list2cmdline([text])
    return shlex.quote(text)


def render_step(root, session):
    flag = {'ground': ' --goal G#', 'challenge': ' --gaps N'}.get(session['phase'], '')
    launcher = f'{quote(sys.executable)} {quote(str(Path(__file__).resolve()))}'
    if root != Path.cwd().resolve():
        launcher += f' --root {quote(str(root))}'
    lines = [
        f'SESSION: {session["id"]}',
        f'PHASE: {session["phase"].upper()}  |  LOOP: {session["cycle"]}',
        prompt(session),
        f'\nEdit {root / RECORD}; then run: {launcher} done --session {session["id"]}{flag}',
        'Do NOT jump to another phase or implement yet.',
    ]
    return '\n'.join(lines)


def summary(record, session):
    goal = find_goal(record, session['goal'])
    lines = [f'# {goal["goal"]}', '', f'Session {session["id"]}.']
    if goal.get('constraints'):
        lines += ['', '## Constraints'] + [f'- {item}' for item in goal['constraints']]
    if goal.get('criteria'):
        lines += ['', '## Success criteria'] + [f'- {item}' for item in goal['criteria']]
    if goal['decisions']:
        lines += ['', '## Decisions']
        for decision in goal['decisions']:
            lines += ['', f'### {decision["question"]}', decision.get('answer', '')]
            if decision.get('rationale'):
                lines += ['', f'Reason: {decision["rationale"]}']
    index = next(i for i, item in enumerate(record['goals']) if item['id'] == goal['id'])
    earlier = record['goals'][:index]
    if earlier:
        lines += ['', '## Earlier goals'] + [f'- {item["goal"]}' for item in earlier]
    return '\n'.join(lines)


def goal_label(record, gid):
    if gid is None:
        return '-'
    for goal in record['goals']:
        if goal['id'] == gid:
            return f'{gid}  {goal["goal"]}'
    return gid


def render_sessions(root, sessions, show_all):
    if not sessions:
        return 'No sessions.' if show_all else 'No active sessions.'
    record = load_record(root) if (root / RECORD).exists() else {'goals': []}
    lines = []
    for session in sessions:
        lines.append(
            f'{session["id"]}  {session["status"]:<9} {session["phase"]:<9}  '
            f'{goal_label(record, session["goal"])}'
        )
    return '\n'.join(lines)


# --- commands -------------------------------------------------------------

def start(root):
    """Add a fresh session; keep decisions.json and every earlier session."""
    record_path = root / RECORD
    with workflow_lock(root):
        if record_path.exists():
            load_record(root)
        else:
            write_json(record_path, {'goals': []})
        state = load_workflow(root, allow_missing=True)
        now = timestamp()
        session = {
            'id': next_session_id(state),
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
        save_workflow(root, state)
        return session


def done(root, sid, goal, gaps):
    with workflow_lock(root):
        state = load_workflow(root)
        session = select_active(state, sid)
        phase = session['phase']
        if goal is not None and phase != 'ground':
            raise ValueError('`--goal` is only valid in the ground phase.')
        if gaps is not None and phase != 'challenge':
            raise ValueError('`--gaps` is only valid in the challenge phase.')

        record = load_record(root)
        now = timestamp()

        if phase == 'ground':
            if goal is None:
                raise ValueError('Ground requires `done --goal G#`.')
            find_goal(record, goal)
            for other in active_sessions(state):
                if other['id'] != session['id'] and other.get('goal') == goal:
                    raise ValueError(f'{goal} is held by active session {other["id"]}; choose another goal or run `status`.')
            session['goal'] = goal
            session['phase'] = 'branch'
            session['baseline'] = goal_hash(record, goal)
        elif phase in ('branch', 'decide'):
            find_goal(record, session['goal'])
            current_hash = goal_hash(record, session['goal'])
            if current_hash == session['baseline']:
                raise ValueError(f'{phase} requires an edit to goal {session["goal"]} in decisions.json; that goal has not changed.')
            session['phase'] = ORDER[ORDER.index(phase) + 1]
            session['baseline'] = current_hash
        else:
            if gaps is None or gaps < 0:
                raise ValueError('Challenge requires `done --gaps N` (N >= 0).')
            current = find_goal(record, session['goal'])
            open_rows = [d['id'] for d in current['decisions'] if d['status'] == 'open']
            current_hash = goal_hash(record, session['goal'])
            if gaps == 0:
                if open_rows:
                    raise ValueError(f'{len(open_rows)} open decision(s) remain: {", ".join(open_rows)}.')
                session['phase'] = CLOSED_PHASE
                session['status'] = 'complete'
                session['completed'] = now
            else:
                if not open_rows:
                    raise ValueError(f'Add the discovered gaps as open decisions in {session["goal"]}.')
                if current_hash == session['baseline']:
                    raise ValueError(f'challenge requires an edit to goal {session["goal"]} in decisions.json; that goal has not changed.')
                session['phase'] = 'branch'
                session['cycle'] += 1
                session['baseline'] = current_hash

        session['updated'] = now
        save_workflow(root, state)
        if session['status'] == 'complete':
            return f'{summary(record, session)}\n\n{DONE_MSG}'
        return render_step(root, session)


def abandon(root, sid):
    with workflow_lock(root):
        state = load_workflow(root)
        session = find_session(state, sid)
        if session['status'] != 'active':
            raise ValueError(f'Session {sid} is {session["status"]}; it is already closed.')
        now = timestamp()
        goal = session['goal'] or 'no goal'
        session['phase'] = CLOSED_PHASE
        session['status'] = 'abandoned'
        session['completed'] = now
        session['updated'] = now
        save_workflow(root, state)
        return f'Session {sid} abandoned; {goal} released.'


def status(root, sid, show_all):
    if sid is not None and show_all:
        raise ValueError('Use either --session or --all, not both.')
    state = load_workflow(root, persist_migration=True)
    if sid is not None:
        session = find_session(state, sid)
        if session['status'] == 'complete':
            return summary(load_record(root), session)
        if session['status'] == 'abandoned':
            record = load_record(root) if (root / RECORD).exists() else {'goals': []}
            return (
                f'SESSION: {session["id"]}\n'
                f'STATUS: abandoned\n'
                f'GOAL: {goal_label(record, session["goal"])}'
            )
        return render_step(root, session)
    sessions = state['sessions'] if show_all else active_sessions(state)
    return render_sessions(root, sessions, show_all)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='project root (default: cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start', help='begin a new session; keep earlier sessions')
    status_cmd = commands.add_parser('status', help='list sessions or show one session')
    status_cmd.add_argument('--session', help='show this session (s#)')
    status_cmd.add_argument('--all', action='store_true', help='include closed sessions')
    done_cmd = commands.add_parser('done', help='verify the step and advance one phase')
    done_cmd.add_argument('--session', help='session to advance (s#); required when several are active')
    done_cmd.add_argument('--goal', help='goal set ID chosen in ground (G#)')
    done_cmd.add_argument('--gaps', type=int, help='remaining material gaps after challenge')
    abandon_cmd = commands.add_parser('abandon', help='close an active session without a summary')
    abandon_cmd.add_argument('--session', required=True, help='session to close (s#)')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == 'start':
            print(render_step(root, start(root)))
        elif args.command == 'status':
            print(status(root, args.session, args.all))
        elif args.command == 'abandon':
            print(abandon(root, args.session))
        else:
            print(done(root, args.session, args.goal, args.gaps))
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
