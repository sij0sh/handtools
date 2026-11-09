#!/usr/bin/env python3
"""untangle: a resumable whole-codebase audit, one run per project.

The stages are workflowlib/ (steps and its helpers); the engine is handtools' skills/_engine/.
Run state and exports: ~/.agents/state/untangle/<project-key>/. Python 3.9+; standard library only.
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

from workflowlib import steps  # noqa: E402
from _engine import cli, flow, storage  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', help='project root (default: git top level, else cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('start', help='begin a run (refuses while one is unfinished)')
    start.add_argument('--continue', dest='predecessor', metavar='AUDIT_ID',
                       help='successor of a closed audit: its unchanged reviews carry over')
    commands.add_parser('status', help='show the current step without changing it')
    show = commands.add_parser('show', help='print run state from the journal as JSON')
    show.add_argument('part', nargs='?', help=', '.join(steps.SHOW_PARTS))
    commands.add_parser('abandon', help='discard the unfinished run')
    done = commands.add_parser('done', help='verify the step (JSON payload on stdin) and advance')
    done.add_argument('--stage', help='stateless only: the step just finished')
    args = parser.parse_args()
    root = storage.project_root(args.root)
    launch = cli.launcher(__file__, root)
    def begin():
        if args.predecessor and args.predecessor not in steps.closed_audits(root):
            raise ValueError(f'No closed audit {args.predecessor}; nothing started.')
        text = flow.start(steps, root, launch)
        return text if not args.predecessor else steps.continue_from(root, args.predecessor) + '\n' + text

    def show():
        return json.dumps(steps.show(root, args.part), indent=1, sort_keys=True)

    actions = {'start': begin, 'status': lambda: flow.status(steps, root, launch), 'show': show,
               'abandon': lambda: flow.abandon(steps, root),
               'done': lambda: flow.done(steps, root, cli.read_payload(), launch, args.stage)}
    return cli.run(actions[args.command])


if __name__ == '__main__':
    sys.exit(main())
