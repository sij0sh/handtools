"""Versioned event journal and deterministic replay. No filesystem effects in reducers."""
import copy
from contextlib import contextmanager
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .planning import digest

PROTOCOL = 'handtools.workflow'
VERSION = 1


def event(run, revision, parent, kind, payload, request_id=None, workspace=None):
    item = dict(protocol=PROTOCOL, schema_version=VERSION, event_id=str(uuid.uuid4()),
                request_id=request_id or str(uuid.uuid4()), workspace_id=workspace,
                run_id=run, revision=revision, parent_event_id=parent, kind=kind,
                workflow_version='1', policy_version='1', payload=payload,
                timestamp=datetime.now(timezone.utc).isoformat())
    validate(item)
    return item


def validate(item):
    if not isinstance(item, dict) or item.get('protocol') != PROTOCOL or item.get('schema_version') != VERSION:
        raise ValueError('unsupported workflow protocol/schema')
    for key in ('event_id', 'request_id', 'run_id', 'kind'):
        if not isinstance(item.get(key), str) or not item[key]:
            raise ValueError('event needs ' + key)
    if type(item.get('revision')) is not int or item['revision'] < 1:
        raise ValueError('invalid revision')
    if item.get('workflow_version') != '1' or item.get('policy_version') != '1':
        raise ValueError('unsupported workflow/policy version')
    if item.get('kind') not in ('state.changed', 'state.deleted', 'run.started', 'stage.completed',
                                'plan.revised', 'authorization.recorded', 'run.closed'):
        raise ValueError('unsupported event kind')
    if not isinstance(item.get('payload'), dict):
        raise ValueError('event payload must be an object')
    json.dumps(item, allow_nan=False)


def replay(items):
    """Order by predecessor, reject gaps/forks/identity collisions; never infer latest by time."""
    unique, requests = {}, {}
    for raw in items:
        item = copy.deepcopy(raw)
        item.pop('source_ref', None)
        validate(item)
        eid = item['event_id']
        if eid in unique and unique[eid] != item:
            raise ValueError('event identity collision')
        rid = item['request_id']
        if rid in requests and requests[rid] != eid:
            raise ValueError('request identity collision')
        unique[eid], requests[rid] = item, eid
    ordered = sorted(unique.values(), key=lambda x: x['revision'])
    state, parent, run = {}, None, None
    closed = False
    for rev, item in enumerate(ordered, 1):
        run = run or item['run_id']
        if item['run_id'] != run or item['revision'] != rev or item['parent_event_id'] != parent:
            raise ValueError('incomplete or conflicting event chain')
        if closed:
            raise ValueError('closed run cannot advance')
        if item['kind'] == 'run.closed':
            closed = True
        if item['kind'] == 'state.deleted':
            state = None
        elif item['kind'] == 'state.changed':
            state = copy.deepcopy(item['payload']['state'])
        else:
            if state is None:
                raise ValueError('closed/deleted run cannot advance')
            state = {**state, **copy.deepcopy(item['payload'])}
        parent = item['event_id']
    return state, ordered


class Journal:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE IF NOT EXISTS events (run TEXT, revision INTEGER, event_id TEXT UNIQUE, '
                   'request_id TEXT, body TEXT, PRIMARY KEY(run, revision), UNIQUE(run, request_id))')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def history(self, run):
        if not self.path.exists():
            return []
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM events WHERE run=? ORDER BY revision', (run,))]

    def read(self, run):
        items = self.history(run)
        return replay(items)[0] if items else None

    def append(self, run, kind, payload, expected=None, request_id=None, workspace=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = [json.loads(r[0]) for r in db.execute('SELECT body FROM events WHERE run=? ORDER BY revision', (run,))]
            _, rows = replay(rows)
            if request_id:
                previous = next((r for r in rows if r['request_id'] == request_id), None)
                if previous:
                    if previous['kind'] != kind or digest(previous['payload']) != digest(payload):
                        raise ValueError('request reused with different payload')
                    return previous
            revision = len(rows)
            if expected is not None and expected != revision:
                raise ValueError('stale revision: expected %s, current %s' % (expected, revision))
            item = event(run, revision + 1, rows[-1]['event_id'] if rows else None,
                         kind, payload, request_id, workspace)
            replay(rows + [item])
            db.execute('INSERT INTO events VALUES (?,?,?,?,?)',
                       (run, item['revision'], item['event_id'], item['request_id'], json.dumps(item)))
            return item

    def put(self, run, state):
        return self.append(run, 'state.changed', {'state': state})
