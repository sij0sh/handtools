#!/usr/bin/env python3
"""Explicit event commands. Structured stdout receipts; no skill invocation."""
import argparse
import json
import sys
import sqlite3
import time
from pathlib import Path
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _engine import events, planning, recordings, storage


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root')
    p.add_argument('--backend', choices=('journal', 'transcript'), default='journal')
    p.add_argument('--recording', action='append', default=[])
    p.add_argument('--format', choices=('json', 'table'), default='json')
    p.add_argument('command', choices=('start', 'append', 'status', 'history', 'plan', 'query'))
    p.add_argument('--run')
    p.add_argument('--kind', default='stage.completed')
    p.add_argument('--expect-revision', type=int)
    p.add_argument('--head', help='required expected last event ID for transcript advancement')
    p.add_argument('--request-id')
    p.add_argument('--sql', help='one read-only SELECT over workflow_events')
    a = p.parse_args()
    root = storage.project_root(a.root)
    if a.command == 'plan':
        value = json.load(sys.stdin)
        return {'status': planning.validate(value), 'digest': planning.digest(value)}
    if a.command != 'query' and not a.run:
        raise ValueError('--run required')
    store = events.Journal(storage.state_root() / 'workflow' / storage.project_key(root) / 'events.sqlite3')
    if a.command == 'query':
        if a.backend != 'journal':
            raise ValueError('query uses journal; transcript history is available with --run')
        return query(store, a.sql)
    items = recordings.receipts(a.recording, a.run) if a.backend == 'transcript' else store.history(a.run)
    if a.backend == 'transcript' and any(x.get('workspace_id') != storage.project_key(root) for x in items):
        raise ValueError('recording workspace differs; explicit migration required')
    state, chain = events.replay(items)
    if a.command in ('status', 'history'):
        return {'backend': a.backend, 'capture': 'observed_prefix' if a.backend == 'transcript' else 'committed',
                'revision': len(chain), 'head': chain[-1]['event_id'] if chain else None,
                'state': state, **({'events': items} if a.command == 'history' else {})}
    if not a.request_id:
        raise ValueError('--request-id required for retry safety')
    payload = json.load(sys.stdin)
    kind = 'run.started' if a.command == 'start' else a.kind
    if a.command == 'start' and chain:
        prior = next((x for x in chain if x['request_id'] == a.request_id), None)
        if not prior:
            raise ValueError('run already exists')
    if a.command == 'append' and not chain:
        raise ValueError('run unavailable; provide complete recordings')
    if a.expect_revision is None:
        raise ValueError('--expect-revision required')
    if a.backend == 'journal':
        return store.append(a.run, kind, payload, a.expect_revision, a.request_id, storage.project_key(root))
    prior = next((x for x in chain if x['request_id'] == a.request_id), None)
    if prior:
        if planning.digest(prior['payload']) != planning.digest(payload) or prior['kind'] != kind:
            raise ValueError('request reused with different payload')
        return prior
    if a.command == 'append' and (not a.head or a.head != chain[-1]['event_id']):
        raise ValueError('pending/unknown capture: expected head is unavailable or differs')
    if a.expect_revision != len(chain):
        raise ValueError('stale or incomplete recording revision')
    receipt = events.event(a.run, len(chain) + 1, chain[-1]['event_id'] if chain else None,
                           kind, payload, a.request_id, storage.project_key(root))
    events.replay(chain + [receipt])
    return receipt


def query(store, sql):
    import sqlite3
    if not store.path.exists():
        return []
    with store.connect() as source:
        rows = [json.loads(r[0]) for r in source.execute('SELECT body FROM events')]
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE workflow_events (run_id, revision INTEGER, event_id, kind, payload)')
        db.executemany('INSERT INTO workflow_events VALUES (?,?,?,?,?)',
                       [(r['run_id'], r['revision'], r['event_id'], r['kind'], json.dumps(r['payload'])) for r in rows])
        deadline = time.monotonic() + 2
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        def auth(action, one, two, database, trigger):
            if action == sqlite3.SQLITE_FUNCTION and (two or '').lower() in ('load_extension', 'readfile', 'writefile'):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                                                   sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE) else sqlite3.SQLITE_DENY
        db.set_authorizer(auth)
        cursor = db.execute(sql or 'SELECT * FROM workflow_events')
        return [dict(zip([c[0] for c in cursor.description], row)) for row in cursor]


if __name__ == '__main__':
    try:
        value = main()
        if '--format' in sys.argv and sys.argv[sys.argv.index('--format') + 1] == 'table' and isinstance(value, list):
            for row in value:
                print(' | '.join('%s=%s' % pair for pair in row.items()))
        else:
            print(json.dumps(value, sort_keys=True))
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(2)
