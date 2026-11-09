"""Commands and phase transitions. Owns the order of reads, checks, and writes."""
from _engine import storage

from . import config, gitcheck, record, sessions, steps


def _step(state, rec, session, launcher, limit):
    return steps.render_step(session, rec, sessions.holders(state), launcher, limit, config.references())


def start(root, launcher):
    """Add a fresh session; keep decisions.json and every earlier session."""
    limit = config.max_challenges()
    with storage.lock(sessions.base(root)):
        if record.exists(root):
            rec = record.load(root)
        else:
            rec = {'goals': []}
            record.save(root, rec)
        state = sessions.load(root, allow_missing=True)
        session = sessions.add(state)
        sessions.save(root, state)
    return _step(state, rec, session, launcher, limit)


def done(root, sid, payload, launcher):
    """Apply the payload, verify the step, and advance; on any error write nothing."""
    with storage.lock(sessions.base(root)):
        limit = config.max_challenges()
        state = sessions.load(root)
        session = sessions.select_active(state, sid)
        phase = session['phase']
        rec = record.load(root)
        now = sessions.timestamp()

        if payload is not None:
            gid = record.apply_payload(rec, payload, session['goal'], phase == 'ground')
        elif phase == 'ground':
            raise ValueError('Ground requires a payload with `goal` (new set) or `id` (reuse).')
        else:
            gid = session['goal']
        current_hash = record.goal_hash(rec, gid)
        changed = current_hash != session['baseline']
        final = session['cycle'] >= limit

        if phase == 'ground':
            held = sessions.holders(state).get(gid)
            if held and held != session['id']:
                raise ValueError(f'{gid} is held by active session {held}; choose another goal or run `status`.')
            session['goal'] = gid
            session['phase'] = 'branch'
        elif phase == 'decide' and session['cycle'] > limit:
            sessions.close(session, 'complete')
        elif phase in ('branch', 'decide'):
            if not changed:
                raise ValueError(f'{phase} requires a change to goal {gid}; send it as the payload.')
            session['phase'] = 'decide' if phase == 'branch' else 'challenge'
        else:
            # Changed with open rows: decide (final one past the limit). Changed and
            # settled: fresh challenge below the limit. Otherwise close.
            unresolved = record.open_rows(record.find_goal(rec, gid))
            if changed and (unresolved or not final):
                session['phase'] = 'decide' if unresolved else 'challenge'
                session['cycle'] += 1
            elif unresolved and not final:
                raise ValueError(f'{len(unresolved)} open decision(s) remain: {", ".join(unresolved)}; '
                                 'resolve them or send new gaps as the payload.')
            else:
                sessions.close(session, 'complete')
        session['baseline'] = current_hash
        session['updated'] = now

        if payload is not None:
            record.save(root, rec)
        sessions.save(root, state)
    if session['status'] == 'complete':
        return _with_warning(root, steps.done_message(rec, session))
    return _step(state, rec, session, launcher, limit)


def _with_warning(root, text):
    warning = gitcheck.warning(root)
    return f'{text}\n\n{warning}' if warning else text


def record_goal(root, gid, payload):
    """Upsert one goal without a session (used by other skills, e.g. foundation's ADRs).

    Rows without an `id` get the next D#. Refuses a goal an active session holds.
    """
    if not isinstance(payload, dict):
        raise ValueError('record needs a JSON object on stdin.')
    if 'id' in payload:
        raise ValueError('record: pass an existing goal with --goal G#, not `id` in the payload.')
    with storage.lock(sessions.base(root)):
        rec = record.load_or_empty(root)
        state = sessions.load(root, allow_missing=True)
        if gid is not None:
            goal = record.find_goal(rec, gid)
            held = sessions.holders(state).get(gid)
            if held:
                raise ValueError(f'{gid} is held by active session {held}; finish or abandon it first.')
            existing = list(goal['decisions'])
        else:
            existing = []
        rows = payload.get('decisions', [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and 'id' not in row:
                    row['id'] = record.next_id(existing, 'D')
                if isinstance(row, dict):
                    existing.append({'id': row['id']})
        gid = record.apply_payload(rec, payload, gid, ground=gid is None)
        record.save(root, rec)
    goal = record.find_goal(rec, gid)
    return _with_warning(root, f'Recorded {gid}: {len(goal["decisions"])} decision(s). '
                               f'View with `show --goal {gid}`.')


def show(root, gid):
    """Read-only Markdown view of decisions.json."""
    return steps.show(record.load_or_empty(root), gid)


def abandon(root, sid):
    with storage.lock(sessions.base(root)):
        state = sessions.load(root)
        session = sessions.find(state, sid)
        if session['status'] != 'active':
            raise ValueError(f'Session {sid} is {session["status"]}; it is already closed.')
        sessions.close(session, 'abandoned')
        sessions.save(root, state)
    return f'Session {sid} abandoned; {session["goal"] or "no goal"} released.'


def status(root, sid, show_all, launcher):
    if sid is not None and show_all:
        raise ValueError('Use either --session or --all, not both.')
    state = sessions.load(root, persist_migration=True)
    rec = record.load_or_empty(root)
    if sid is None:
        listed = state['sessions'] if show_all else sessions.active(state)
        return steps.session_list(rec, listed, show_all)
    session = sessions.find(state, sid)
    if session['status'] == 'complete':
        return steps.summary(rec, session)
    if session['status'] == 'abandoned':
        return steps.abandoned(rec, session)
    return _step(state, rec, session, launcher, config.max_challenges())
