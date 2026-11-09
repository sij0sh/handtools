#!/usr/bin/env python3
"""Workflow skill template: the script owns order; the agent does one step at a time.

Copy this scripts/ folder into <skill>/scripts/ and edit workflowlib/steps.py only (set MODE and AREA there).
Python 3.9+; standard library only.
Stateful: ~/.agents/state/<AREA>/<project-key>/workflow.json, one run per project (storage.py).
Stateless: nothing saved; `done --stage S` names the finished step.
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from workflowlib import cli, flow, storage  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', help='project root (default: git top level, else cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start', help='begin a run (refuses while one is unfinished)')
    commands.add_parser('status', help='show the current step without changing it')
    commands.add_parser('abandon', help='discard the unfinished run')
    done = commands.add_parser('done', help='verify the step (JSON payload on stdin) and advance')
    done.add_argument('--stage', help='stateless only: the step just finished')
    args = parser.parse_args()
    root = storage.project_root(args.root)
    launch = cli.launcher(__file__, root)
    actions = {'start': lambda: flow.start(root, launch), 'status': lambda: flow.status(root, launch),
               'abandon': lambda: flow.abandon(root),
               'done': lambda: flow.done(root, cli.read_payload(), launch, args.stage)}
    return cli.run(actions[args.command])


if __name__ == '__main__':
    sys.exit(main())
