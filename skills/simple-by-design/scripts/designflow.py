#!/usr/bin/env python3
"""State machine that drives the simple-by-design loop.

Run from the project root. Requires Python 3.9+; standard library only.
`done` reads each step's edits as JSON on stdin; the agent never opens the files.
Logic lives in designlib/; this file owns the command line only.

Files, all owned by this script:
  <root>/.agents/design/decisions.json  the project's decision record (ADR log), one set per goal; commit it
  ~/.agents/state/decisions/<project key>/workflow.json  permanent session registry (per user)
  ~/.agents/state/decisions/<project key>/workflow.lock  short-lived lock directory around writes
  ($HANDTOOLS_STATE replaces ~/.agents/state.)
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from designlib import flow  # noqa: E402


def quote(text):
    """Quote one argument for the shell that will run the printed command."""
    if os.name == 'nt':
        return subprocess.list2cmdline([text])
    return shlex.quote(text)


def launcher(root):
    """Command prefix that reruns this script for the same project root."""
    command = f'{quote(sys.executable)} {quote(str(Path(__file__).resolve()))}'
    if root != Path.cwd().resolve():
        command += f' --root {quote(str(root))}'
    return command


def read_payload():
    """Return stdin parsed as JSON, or None when stdin is a terminal or blank."""
    if sys.stdin is None or sys.stdin.isatty():
        return None
    data = sys.stdin.buffer.read()
    if data[:2] in (b'\xff\xfe', b'\xfe\xff'):
        text = data.decode('utf-16')
    else:
        text = data.decode('utf-8-sig')
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f'Payload is not valid JSON: {error}') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='project root (default: cwd)')
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
    root = args.root.resolve()
    try:
        if args.command == 'start':
            print(flow.start(root, launcher(root)))
        elif args.command == 'status':
            print(flow.status(root, args.session, args.all, launcher(root)))
        elif args.command == 'abandon':
            print(flow.abandon(root, args.session))
        elif args.command == 'record':
            print(flow.record_goal(root, args.goal, read_payload()))
        elif args.command == 'show':
            print(flow.show(root, args.goal))
        else:
            print(flow.done(root, args.session, read_payload(), launcher(root)))
    except (ValueError, OSError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
