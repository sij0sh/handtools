#!/usr/bin/env python3
"""build-skills: create or revise a skill: a saved prompt (ground, draft, review) or a staged skill (ground, design, draft, review).

Run from the project root. Python 3.9+; standard library only.
`done` reads each stage's payload as JSON on stdin. Logic lives in build_skills/; this file owns the command line only.

State under <skill>/state/<project-key>/ (script owns all of it; the agent edits only sN/draft/):
  workflow.json              session registry {version, root, sessions[]}
  workflow.lock              short-lived lock directory around writes
  sN/design.md, sN/review-N.md  stage artifacts
  sN/draft/<name>/           working copy, written to the target at finish
  sN/backup/<name>/          revise: the original skill
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from build_skills import cli, flow, storage  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', help='project root (default: git top level, else cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start', help='add a new session; keep earlier sessions')
    status = commands.add_parser('status', help='list active sessions or show one')
    status.add_argument('--session', help='show this session (sN)')
    status.add_argument('--all', action='store_true', help='include closed sessions')
    done = commands.add_parser('done', help='apply the stdin JSON payload, verify, advance')
    done.add_argument('--session', help='session to advance; required when several are active')
    abandon = commands.add_parser('abandon', help='close a session; keep its record')
    abandon.add_argument('--session', required=True, help='session to close (sN)')
    args = parser.parse_args()
    root = storage.project_root(args.root)
    launch = cli.launcher(__file__, root)
    actions = {
        'start': lambda: flow.cmd_start(root, launch),
        'status': lambda: flow.cmd_status(root, args.session, args.all, launch),
        'abandon': lambda: flow.cmd_abandon(root, args.session),
        'done': lambda: flow.cmd_done(root, args.session, cli.read_payload(), launch),
    }
    return cli.run(actions[args.command])


if __name__ == '__main__':
    sys.exit(main())
