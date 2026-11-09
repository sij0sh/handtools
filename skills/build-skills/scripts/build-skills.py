#!/usr/bin/env python3
"""build-skills: create or revise a skill: a saved prompt (ground, draft, review) or a staged skill (ground, design, draft, review).

Run from the project root. Python 3.9+; standard library only. The engine is handtools' skills/_engine/.
`done` reads each stage's payload as JSON on stdin. Logic lives in build_skills/; this file owns the command line only.

State under ~/.agents/state/build-skills/<project-key>/ ($HANDTOOLS_STATE replaces ~/.agents/state;
the script owns all of it; the agent edits only sN/draft/):
  events.sqlite3             authoritative session and application events
  workflow.lock              short-lived lock directory around writes
  design/review views         rendered from session state on demand
  sN/draft/<name>/           working copy, written to the target at finish
  sN/backup/<name>/          revise: the original skill
"""
import argparse
import json
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
from build_skills import flow  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', help='project root (default: git top level, else cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start', help='add a new session; keep earlier sessions')
    status = commands.add_parser('status', help='list active sessions or show one')
    status.add_argument('--session', help='show this session (sN)')
    status.add_argument('--all', action='store_true', help='include closed sessions')
    for command in ('show', 'history'):
        view = commands.add_parser(command, help='read plan/findings or event history without advancing')
        view.add_argument('--session', required=True)
    done = commands.add_parser('done', help='apply the stdin JSON payload, verify, advance')
    done.add_argument('--session', help='session to advance; required when several are active')
    done.add_argument('--expect-revision', type=int)
    done.add_argument('--request-id')
    abandon = commands.add_parser('abandon', help='close a session; keep its record')
    abandon.add_argument('--session', required=True, help='session to close (sN)')
    args = parser.parse_args()
    root = storage.project_root(args.root)
    launch = cli.launcher(__file__, root)
    def view(history=False):
        from build_skills import sessions
        if not history:
            return json.dumps(sessions.find(sessions.load_registry(root), args.session), indent=2)
        items = storage.journal(sessions.base_dir(root)).history('workflow.json')
        result = []
        for item in items:
            state = item.get('payload', {}).get('state', {})
            selected = [s for s in state.get('sessions', []) if s['id'] == args.session]
            if selected:
                result.append({'event_id': item['event_id'], 'revision': item['revision'], 'session': selected[0]})
        return json.dumps(result, indent=2)
    actions = {
        'show': lambda: view(), 'history': lambda: view(True),
        'start': lambda: flow.cmd_start(root, launch),
        'status': lambda: flow.cmd_status(root, args.session, args.all, launch),
        'abandon': lambda: flow.cmd_abandon(root, args.session),
        'done': lambda: flow.cmd_done(root, args.session, cli.read_payload(), launch, args.expect_revision, args.request_id),
    }
    return cli.run(actions[args.command])


if __name__ == '__main__':
    sys.exit(main())
