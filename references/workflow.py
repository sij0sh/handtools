#!/usr/bin/env python3
"""Workflow skill template: the script owns state and order; the agent does one step at a time.

Example flow: do X, then Y; if Y's result is A, do Z, else finish.
Copy into <skill>/scripts/, rename NAME, edit ORDER, PROMPTS, CHECKS, and advance().
Run from the project root. Python 3.9+; standard library only.
"""
import argparse
import json
import shlex
import sys
from pathlib import Path

NAME = 'workflow'
STATE = Path('.agents') / NAME / 'workflow.json'

ORDER = ['x', 'y', 'z']

# Each prompt ends on a criterion the matching check verifies.
PROMPTS = {
    'x': 'Do X. Done when X is complete.',
    'y': 'Do Y. Then run `done --result R`, where R is Y\'s outcome (A or other).',
    'z': 'Y gave A, so do Z. Done when Z is complete.',
}

DONE_MSG = 'DONE: workflow complete.'


def check_y(state, result):
    if not result:
        raise ValueError('Step y requires `done --result R`.')


# Per-step verification; raise ValueError to refuse `done`.
CHECKS = {'y': check_y}


def advance(state, result):
    """Return the next step, or None to finish."""
    phase = state['phase']
    if phase == 'y':
        state['result'] = result
        return 'z' if result == 'A' else None
    if phase == 'z':
        return None
    return ORDER[ORDER.index(phase) + 1]


# --- state ------------------------------------------------------------------

def write_state(root, state):
    path = root / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def load_state(root):
    path = root / STATE
    if not path.exists():
        raise ValueError('No workflow in progress. Run `start`.')
    return json.loads(path.read_text(encoding='utf-8'))


def show(root, state):
    phase = state['phase']
    print(f'STEP: {phase.upper()}')
    print(PROMPTS[phase])
    flag = ' --result R' if phase == 'y' else ''
    launcher = f'{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))}'
    if root != Path.cwd().resolve():
        launcher += f' --root {shlex.quote(str(root))}'
    print(f'\nThen run: {launcher} done{flag}')
    print('Do NOT skip ahead or edit the state file.')


def start(root):
    state = {'phase': ORDER[0]}
    write_state(root, state)
    return state


def complete(root, state, result):
    phase = state['phase']
    if result is not None and phase != 'y':
        raise ValueError('`--result` is only valid in step y.')
    if phase in CHECKS:
        CHECKS[phase](state, result)
    nxt = advance(state, result)
    if nxt is None:
        (root / STATE).unlink()
        print(DONE_MSG)
        return
    state['phase'] = nxt
    write_state(root, state)
    show(root, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='project root (default: cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start', help='begin a fresh workflow (replaces any current one)')
    commands.add_parser('status', help='show the current step without changing it')
    done = commands.add_parser('done', help='verify the step and advance')
    done.add_argument('--result', help="outcome of step y")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == 'start':
            show(root, start(root))
        elif args.command == 'status':
            show(root, load_state(root))
        else:
            complete(root, load_state(root), args.result)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
