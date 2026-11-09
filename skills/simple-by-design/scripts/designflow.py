#!/usr/bin/env python3
"""State machine that drives the simple-by-design loop.

Run from the project root. Requires Python 3.9+; standard library only. The engine is handtools' skills/_engine/.
`done` reads each step's edits as JSON on stdin; the agent never opens the files.
Logic lives in designlib/; this file owns the command line only.

Files, all owned by this script:
  <root>/.agents/design/decisions.json  the project's decision record (ADR log), one set per goal; commit it
  ~/.agents/state/decisions/<project key>/events.sqlite3  permanent session registry (per user)
  ~/.agents/state/decisions/<project key>/workflow.lock  short-lived lock directory around writes
  ($HANDTOOLS_STATE replaces ~/.agents/state.)
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ENGINE = next((p for p in (HERE, *HERE.parents) if (p / '_engine' / '__init__.py').is_file()), None)
if ENGINE is None:
    print('ERROR: engine not found; install the handtools bundle.', file=sys.stderr)
    sys.exit(2)
for path in (str(HERE), str(ENGINE)):
    if path not in sys.path:
        sys.path.insert(0, path)

from _engine import cli, storage  # noqa: E402
from designlib import flow  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', help='project root (default: git top level, else cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start', help='begin a new session; keep earlier sessions')
    status_cmd = commands.add_parser('status', help='list sessions or show one session')
    status_cmd.add_argument('--session', help='show this session (s#)')
    status_cmd.add_argument('--all', action='store_true', help='include closed sessions')
    done_cmd = commands.add_parser('done', help='apply the stdin JSON payload, verify, advance one phase')
    done_cmd.add_argument('--session', help='session to advance (s#); required when several are active')
    abandon_cmd = commands.add_parser('abandon', help='close an active session without a summary')
    abandon_cmd.add_argument('--session', required=True, help='session to close (s#)')
    record_cmd = commands.add_parser('record', help='upsert one goal and its decisions from stdin, without a session')
    record_cmd.add_argument('--goal', help='existing goal to update (G#); omit to add a new goal')
    show_cmd = commands.add_parser('show', help='print the decision record (ADR log) as Markdown; read-only')
    show_cmd.add_argument('--goal', help='show only this goal (G#)')
    args = parser.parse_args()
    root = storage.project_root(args.root)
    launch = cli.launcher(__file__, root)
    actions = {
        'start': lambda: flow.start(root, launch),
        'status': lambda: flow.status(root, args.session, args.all, launch),
        'abandon': lambda: flow.abandon(root, args.session),
        'record': lambda: flow.record_goal(root, args.goal, cli.read_payload()),
        'show': lambda: flow.show(root, args.goal),
        'done': lambda: flow.done(root, args.session, cli.read_payload(), launch),
    }
    return cli.run(actions[args.command])

if __name__ == '__main__':
    sys.exit(main())
