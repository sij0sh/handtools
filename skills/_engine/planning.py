"""Shared, pure planning contract; a library, never an implicitly invoked skill."""
import hashlib
import json
from pathlib import Path

VERSION = '1'
POLICY = Path(__file__).resolve().parent / 'policy'
CONTRACT = """Ground the goal, constraints, current evidence and observable acceptance criteria.
List only material unanswered questions and their dependencies. Decide from requirements and adopted
choices, suitable project conventions, shared defaults, relevant references, then the simplest adequate
choice. Challenge gaps, assumptions and simpler alternatives. A no-material-choices plan is valid.
Ready means no blocking unknowns, a verification plan and authority for the specific scope. An answered
question is not user approval. A loop limit with blocking issues means needs_input, never ready.
Use a compact pass for obvious work. Reopen affected choices when evidence or scope changes.
Read policy/defaults.md, policy/contract.md, policy/instructions.md and policy/languages/<language>.md
under the printed policy directory as relevant. Never invoke another skill to use this contract."""


def prompt():
    return CONTRACT + '\nPolicy: ' + str(POLICY)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate(plan):
    if not isinstance(plan, dict):
        raise ValueError('plan must be an object')
    for key in ('goal', 'verification'):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError('plan needs nonempty ' + key)
    for key in ('constraints', 'criteria', 'decisions', 'blocking'):
        if not isinstance(plan.get(key), list):
            raise ValueError('plan needs list ' + key)
    if not plan['criteria'] or any(not isinstance(x, str) or not x.strip() for x in plan['criteria']):
        raise ValueError('plan needs observable criteria')
    if any(not isinstance(x, str) or not x.strip() for x in plan['constraints'] + plan['blocking']):
        raise ValueError('constraints and blocking entries must be nonempty text')
    ids = set()
    for d in plan['decisions']:
        if not isinstance(d, dict) or not all(isinstance(d.get(k), str) and d[k].strip()
                                              for k in ('id', 'question', 'answer')):
            raise ValueError('decision needs id, question and answer')
        if d['id'] in ids:
            raise ValueError('duplicate decision id')
        ids.add(d['id'])
    graph = {d['id']: d.get('after', []) for d in plan['decisions']}
    def visit(key, trail):
        if key in trail:
            raise ValueError('decision dependency cycle')
        deps = graph[key]
        if not isinstance(deps, list) or any(not isinstance(x, str) or x not in ids for x in deps):
            raise ValueError('unknown decision dependency')
        for dep in deps:
            visit(dep, trail | {key})
    for key in graph:
        visit(key, set())
    if plan.get('challenged') is not True:
        raise ValueError('plan must be challenged')
    return 'needs_input' if plan['blocking'] else 'ready'


def require_ready(plan):
    if validate(plan) != 'ready':
        raise ValueError('needs_input: ' + '; '.join(plan['blocking']))
    return digest(plan)
