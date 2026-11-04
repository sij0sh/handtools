#!/usr/bin/env python3
"""State machine that drives the simple-by-design loop.

Run from the project root. Requires Python 3.9+; standard library only.

Files (under .agents/design/):
  decisions.json  ongoing record, one set per goal (source of truth)
  workflow.json   current run; replaced by `start`, removed when finished
  decisions.md    plain-language view; removed and rewritten at handoff
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

DESIGN = Path('.agents/design')
RECORD = DESIGN / 'decisions.json'
VIEW = DESIGN / 'decisions.md'
STATE = DESIGN / 'workflow.json'

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULTS = SKILL_DIR / 'references' / 'defaults.md'
CONTRACT = SKILL_DIR / 'references' / 'contract.md'
SCHEMA = SKILL_DIR / 'references' / 'decisions.schema.json'
LANGUAGES = SKILL_DIR / 'languages'
SKILLS = LANGUAGES / 'skills.md'

ORDER = ['ground', 'branch', 'decide', 'challenge', 'handoff']

PROMPTS = {
    'ground': (
        'Establish the goal, constraints, success criteria, and relevant existing '
        'decisions or code. In decisions.json, add a new goal set with the next G#, '
        'or reuse the earlier set for the same goal. Schema: {schema}\n'
        'Then run `done --goal G#`.\n\n'
        'Defaults ({defaults}):\n\n{defaults_text}'
    ),
    'branch': (
        'In goal {goal}, list open material questions as decisions with status '
        '`open` and stable D# IDs. Link a dependency with `after` when one answer '
        'requires another. Update decisions.json.'
    ),
    'decide': (
        'In goal {goal}, resolve questions whose dependencies are settled. Settle '
        'each question from the first source that answers it:\n'
        '1. Requirements and adopted decisions.\n'
        '2. Existing project conventions that fit the goal. Replace one only '
        'through an explicit decision.\n'
        '3. Defaults: {defaults} (re-read if not in context).\n'
        '4. The relevant reference:\n'
        '   - Ownership, contracts, dependencies, boundaries, or failures: {contract}\n'
        '   - Language-specific design, types, errors, or concurrency: '
        '{languages}/<language>.md (available: {language_list})\n'
        '   - Skill design or structure: {skills}\n'
        '5. The simplest adequate choice.\n'
        'Ask the user when essential intent, permissions, or a consequential '
        'tradeoff stays unanswered by all five.\n'
        'Set resolved rows to status `resolved` with an `answer`; add a `rationale` '
        'for each non-obvious choice. Add questions the answers raise; drop '
        'questions that became irrelevant. Update decisions.json.'
    ),
    'challenge': (
        'Imagine two competent SWEs following every decision in goal {goal}. If '
        'they could make materially different choices, add the missing questions '
        'as open decisions with dependencies. Update decisions.json. Then run '
        '`done --gaps N`, where N is the count of remaining material gaps; N is 0 '
        'only when no two SWEs could implement a materially different solution '
        'following the decisions.'
    ),
    'handoff': (
        'decisions.md was removed. Write it fresh from decisions.json in one step: '
        'goal {goal} in full (goal, constraints, success criteria, decisions with '
        'reasons), then one short line per earlier goal. Write for someone new and '
        'unfamiliar with code. Use ASD-STE100 Simplified Technical English. No '
        'G#/D# IDs, checkboxes, or status words.'
    ),
}

DONE_MSG = 'DONE: design record is ready for user review; do not implement without approval.'


def prompt(state):
    phase = state['phase']
    names = sorted(p.stem for p in LANGUAGES.glob('*.md') if p != SKILLS)
    return PROMPTS[phase].format(
        goal=state.get('goal'),
        schema=SCHEMA,
        defaults=DEFAULTS,
        defaults_text=DEFAULTS.read_text(encoding='utf-8').strip() if phase == 'ground' else '',
        contract=CONTRACT,
        languages=LANGUAGES,
        language_list=', '.join(names),
        skills=SKILLS,
    )


# --- decisions.json -------------------------------------------------------

def _strings(value, where):
    if not isinstance(value, list) or not all(isinstance(s, str) and s for s in value):
        raise ValueError(f'{where} must be a list of nonempty strings.')


def _keys(obj, where, required, optional):
    if not isinstance(obj, dict):
        raise ValueError(f'{where} must be an object.')
    missing = [k for k in required if k not in obj]
    extra = [k for k in obj if k not in required + optional]
    if missing or extra:
        raise ValueError(f'{where}: missing {missing}, unknown {extra}.')


def validate(record):
    """Check record against references/decisions.schema.json, plus cross-references."""
    _keys(record, 'record', ['goals'], [])
    if not isinstance(record['goals'], list):
        raise ValueError('goals must be a list.')
    goal_ids = set()
    for g in record['goals']:
        _keys(g, 'goal', ['id', 'goal', 'decisions'], ['constraints', 'criteria'])
        gid = g['id']
        if not isinstance(gid, str) or not re.fullmatch(r'G\d+', gid) or gid in goal_ids:
            raise ValueError(f'goal id {gid!r} must be unique G#.')
        goal_ids.add(gid)
        if not isinstance(g['goal'], str) or not g['goal']:
            raise ValueError(f'{gid}.goal must be a nonempty string.')
        for key in ('constraints', 'criteria'):
            if key in g:
                _strings(g[key], f'{gid}.{key}')
        if not isinstance(g['decisions'], list):
            raise ValueError(f'{gid}.decisions must be a list.')
        ids = []
        for d in g['decisions']:
            _keys(d, f'{gid} decision', ['id', 'question', 'status'], ['answer', 'after', 'rationale'])
            did = d['id']
            if not isinstance(did, str) or not re.fullmatch(r'D\d+', did) or did in ids:
                raise ValueError(f'{gid}: decision id {did!r} must be unique D#.')
            ids.append(did)
            where = f'{gid}.{did}'
            if not isinstance(d['question'], str) or not d['question']:
                raise ValueError(f'{where}.question must be a nonempty string.')
            if d['status'] not in ('open', 'resolved'):
                raise ValueError(f'{where}.status must be "open" or "resolved".')
            if d['status'] == 'resolved' and not d.get('answer'):
                raise ValueError(f'{where} is resolved but has no answer.')
            for key in ('answer', 'rationale'):
                if key in d and (not isinstance(d[key], str) or not d[key]):
                    raise ValueError(f'{where}.{key} must be a nonempty string.')
            if 'after' in d:
                _strings(d['after'], f'{where}.after')
        for d in g['decisions']:
            for dep in d.get('after', []):
                if dep == d['id'] or dep not in ids:
                    raise ValueError(f'{gid}.{d["id"]}.after: {dep} is not another decision in {gid}.')


def load_record(root):
    record = json.loads((root / RECORD).read_text(encoding='utf-8'))
    validate(record)
    return record


def find_goal(record, gid):
    for g in record['goals']:
        if g['id'] == gid:
            return g
    raise ValueError(f'Goal {gid} not found in decisions.json.')


# --- workflow.json --------------------------------------------------------

def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def load_state(root):
    path = root / STATE
    if not path.exists():
        raise ValueError('No workflow in progress. Run `start`.')
    return json.loads(path.read_text(encoding='utf-8'))


def start(root):
    """Replace any current workflow with a fresh one; keep decisions.json."""
    record = root / RECORD
    if record.exists():
        load_record(root)
    else:
        write_json(record, {'goals': []})
    state = {'phase': 'ground', 'cycle': 1, 'goal': None, 'baseline': checksum(record)}
    write_json(root / STATE, state)
    return state


def quote(text):
    """Quote one argument for the shell that will run the printed command."""
    if os.name == 'nt':
        return subprocess.list2cmdline([text])
    return shlex.quote(text)


def show(root, state):
    print(f'PHASE: {state["phase"].upper()}  |  LOOP: {state["cycle"]}')
    print(prompt(state))
    flag = {'ground': ' --goal G#', 'challenge': ' --gaps N'}.get(state['phase'], '')
    launcher = f'{quote(sys.executable)} {quote(str(Path(__file__).resolve()))}'
    if root != Path.cwd().resolve():
        launcher += f' --root {quote(str(root))}'
    target = VIEW if state['phase'] == 'handoff' else RECORD
    print(f'\nEdit {root / target}; then run: {launcher} done{flag}')
    print('Do NOT jump to another phase or implement yet.')


def complete(root, state, goal, gaps):
    phase = state['phase']
    if goal is not None and phase != 'ground':
        raise ValueError('`--goal` is only valid in the ground phase.')
    if gaps is not None and phase != 'challenge':
        raise ValueError('`--gaps` is only valid in the challenge phase.')

    if phase == 'handoff':
        view = root / VIEW
        if not view.is_file() or not view.read_text(encoding='utf-8').strip():
            raise ValueError(f'Write a nonempty {view} first.')
        (root / STATE).unlink()
        print(DONE_MSG)
        return

    record = load_record(root)
    if phase == 'ground':
        if goal is None:
            raise ValueError('Ground requires `done --goal G#`.')
        find_goal(record, goal)
        state['goal'] = goal
    else:
        if checksum(root / RECORD) == state['baseline']:
            raise ValueError(f'{phase} requires an edit to decisions.json; file has not changed.')
        current = find_goal(record, state['goal'])
        if phase == 'challenge':
            if gaps is None or gaps < 0:
                raise ValueError('Challenge requires `done --gaps N` (N >= 0).')
            open_rows = [d['id'] for d in current['decisions'] if d['status'] == 'open']
            if gaps == 0 and open_rows:
                raise ValueError(f'{len(open_rows)} open decision(s) remain: {", ".join(open_rows)}.')
            if gaps > 0 and not open_rows:
                raise ValueError(f'Add the discovered gaps as open decisions in {state["goal"]}.')
            if gaps > 0:
                state['phase'] = 'branch'
                state['cycle'] += 1

    if phase != 'challenge' or gaps == 0:
        state['phase'] = ORDER[ORDER.index(phase) + 1]
    if state['phase'] == 'handoff':
        (root / VIEW).unlink(missing_ok=True)
    state['baseline'] = checksum(root / RECORD)
    write_json(root / STATE, state)
    show(root, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='project root (default: cwd)')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('start', help='begin a fresh workflow (replaces any current one)')
    commands.add_parser('status', help='show the current step without changing it')
    done = commands.add_parser('done', help='verify the step and advance one phase')
    done.add_argument('--goal', help='goal set ID chosen in ground (G#)')
    done.add_argument('--gaps', type=int, help='remaining material gaps after challenge')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == 'start':
            show(root, start(root))
        elif args.command == 'status':
            show(root, load_state(root))
        else:
            complete(root, load_state(root), args.goal, args.gaps)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
