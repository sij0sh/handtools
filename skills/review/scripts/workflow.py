#!/usr/bin/env python3
"""review: report-only diff, subsystem and reported-bug review, one run per project.

The stages are reviewlib/; the engine, audit bookkeeping and recon are handtools' skills/_engine/.
Run state and report.md: ~/.agents/state/review/<project-key>/. Python 3.9+; standard library only.
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

from reviewlib import steps  # noqa: E402
from _engine import cli, flow, storage  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', help='project root (default: git top level, else cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start', help='begin a run (refuses while one is unfinished)')
    commands.add_parser('status', help='show the current step without changing it')
    show = commands.add_parser('show', help='print run state from the journal as JSON')
    show.add_argument('part', nargs='?', help=', '.join(steps.SHOW_PARTS))
    commands.add_parser('abandon', help='cancel the unfinished run (writes a CANCELLED report after FRAME)')
    commands.add_parser('done', help='verify the step (JSON payload on stdin) and advance')
    args = parser.parse_args()
    root = storage.project_root(args.root)
    launch = cli.launcher(__file__, root)

    def show():
        return json.dumps(steps.show(root, args.part), indent=1, sort_keys=True)

    actions = {'start': lambda: flow.start(steps, root, launch), 'show': show,
               'status': lambda: flow.status(steps, root, launch),
               'abandon': lambda: flow.abandon(steps, root),
               'done': lambda: flow.done(steps, root, cli.read_payload(), launch)}
    return cli.run(actions[args.command])


if __name__ == '__main__':
    sys.exit(main())
