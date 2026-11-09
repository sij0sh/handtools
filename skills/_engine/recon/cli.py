#!/usr/bin/env python3
"""Recon commands. JSON on stdout; `start`, `record` and `close` print the accepted journal event
(a structured receipt). Read-only: orient, candidates, status, query. Never runs project code.

  orient | candidates  [--related label=path] [--exclude glob] [--max-files N] [--max-bytes N]
  start   --request-id ID [--depth orient|map|deepen] [--related label=path] [--exclude glob] [--budget k=v]
  record  --run snap-N --expect-revision R --request-id ID   < {"records": [...], "cost": {...}}
  close   --run snap-N --expect-revision R --request-id ID
  refresh --run snap-N --request-id ID [--budget k=v] [--related label=path]
  status  [--run snap-N]
  query   summary|contracts|consumers|neighbors|evidence|gaps|stale|observations|decisions
          [--run snap-N] [--id X] [--direction upstream|downstream|both] [--depth N]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _engine import storage  # noqa: E402
from _engine.recon import collect, guide, query, records, store  # noqa: E402

COMMANDS = ('orient', 'candidates', 'start', 'record', 'close', 'refresh', 'status', 'query', 'guide')


def pairs(values, what):
    out = {}
    for v in values:
        key, sep, val = v.partition('=')
        if not sep or not key:
            raise ValueError(f'{what} is key=value: {v!r}')
        out[key] = val
    return out


def budgets(values):
    out = {}
    for key, val in pairs(values, '--budget').items():
        out[key] = [c for c in val.split(';') if c] if key == 'allowed_commands' else int(val)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--root', help='project root (default: git top level, else cwd)')
    p.add_argument('command', choices=COMMANDS)
    p.add_argument('name', nargs='?', help='query name')
    p.add_argument('--run')
    p.add_argument('--request-id')
    p.add_argument('--expect-revision', type=int)
    p.add_argument('--related', action='append', default=[])
    p.add_argument('--exclude', action='append', default=[])
    p.add_argument('--depth', default=None)
    p.add_argument('--budget', action='append', default=[])
    p.add_argument('--max-files', type=int)
    p.add_argument('--max-bytes', type=int)
    p.add_argument('--id')
    p.add_argument('--direction', default='both')
    a = p.parse_args(argv)
    root = storage.project_root(a.root)
    related = {k: str(Path(v).expanduser().resolve()) for k, v in pairs(a.related, '--related').items()}
    if a.command == 'guide':
        return guide.prompt()
    if a.command in ('orient', 'candidates'):
        limits = {k: v for k, v in (('max_files', a.max_files), ('max_bytes', a.max_bytes)) if v}
        return getattr(collect, a.command)({'.': root, **related}, a.exclude, limits)
    if a.command == 'start':
        return store.start(root, a.request_id, related, a.exclude, a.depth or 'map', budgets(a.budget))
    if a.command == 'record':
        return store.record(root, need_run(a), json.load(sys.stdin), a.expect_revision, a.request_id)
    if a.command == 'close':
        return store.close(root, need_run(a), a.expect_revision, a.request_id)
    if a.command == 'refresh':
        return store.refresh(root, need_run(a), a.request_id, budgets(a.budget), related)
    if a.command == 'status':
        return store.status(root, a.run)
    run = a.run or store.newest(root)
    if not run:
        raise ValueError('No recon snapshot yet; run `start` first.')
    state = store.read(root, run)[0]
    name = a.name or 'summary'
    if name not in query.NAMES:
        raise ValueError(f'query is one of {", ".join(query.NAMES)}.')
    if name in ('consumers', 'evidence'):
        return getattr(query, name)(state, need_id(a))
    if name == 'neighbors':
        return query.neighbors(state, need_id(a), a.direction, int(a.depth or 1))
    return getattr(query, name)(state)


def need_run(a):
    if not a.run:
        raise ValueError('--run snap-N is required.')
    return a.run


def need_id(a):
    if not records.is_id(a.id):
        raise ValueError('--id <record id> is required.')
    return a.id


if __name__ == '__main__':
    try:
        value = main()
        print(value if isinstance(value, str) else json.dumps(value, sort_keys=True))
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(2)
