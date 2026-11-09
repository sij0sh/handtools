#!/usr/bin/env python3
"""foundation: discover -> interview -> assess -> [apply -> validate]; stateless (`done --stage S`).

The stages are workflowlib/steps.py; the engine is handtools' skills/_engine/. Python 3.9+; standard library only.
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
    commands.add_parser('record', help='persist accepted/declined foundation bookkeeping from stdin')
    commands.add_parser('show', help='read foundation bookkeeping')
    commands.add_parser('start', help='begin a run (refuses while one is unfinished)')
    commands.add_parser('status', help='show the current step without changing it')
    commands.add_parser('abandon', help='discard the unfinished run')
    done = commands.add_parser('done', help='verify the step (JSON payload on stdin) and advance')
    done.add_argument('--stage', help='stateless only: the step just finished')
    args = parser.parse_args()
    root = storage.project_root(args.root)
    launch = cli.launcher(__file__, root)
    def record():
        payload = cli.read_payload()
        if not isinstance(payload, dict) or not all(k in payload for k in ('goal', 'accepted', 'declined', 'updated')):
            raise ValueError('record needs goal, accepted, declined, updated')
        with storage.lock(storage.state_dir(steps.AREA, root)):
            storage.write_state(steps.decisions(root), payload)
        return 'Foundation bookkeeping recorded.'
    actions = {'record': record, 'show': lambda: json.dumps(storage.read_state(steps.decisions(root)), indent=2), 'start': lambda: flow.start(steps, root, launch), 'status': lambda: flow.status(steps, root, launch),
               'abandon': lambda: flow.abandon(steps, root),
               'done': lambda: flow.done(steps, root, cli.read_payload(), launch, args.stage)}
    return cli.run(actions[args.command])


if __name__ == '__main__':
    sys.exit(main())
