"""Commands and phase transitions. Owns the order of reads, checks, and writes."""
from . import config, record, sessions, steps, storage


def _step(state, rec, session, launcher, limit):
    return steps.render_step(session, rec, sessions.holders(state), launcher, limit, config.references())


def start(root, launcher):
    """Add a fresh session; keep decisions.json and every earlier session."""
    limit = config.max_challenges()
    with storage.lock(root):
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
    with storage.lock(root):
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
            sessions.close(session, 'complete', now)
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
                sessions.close(session, 'complete', now)
        session['baseline'] = current_hash
        session['updated'] = now

        if payload is not None:
            record.save(root, rec)
        sessions.save(root, state)
    if session['status'] == 'complete':
        return steps.done_message(rec, session)
    return _step(state, rec, session, launcher, limit)


def abandon(root, sid):
    with storage.lock(root):
        state = sessions.load(root)
        session = sessions.find(state, sid)
        if session['status'] != 'active':
            raise ValueError(f'Session {sid} is {session["status"]}; it is already closed.')
        sessions.close(session, 'abandoned', sessions.timestamp())
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
