"""Stages: ground, design, draft, review (loops until confirmed, then finish)."""
import re
from pathlib import Path

from .config import GROUND_FIELDS, MODELS, REVIEW_LIMIT, ROUTER_LABELS, STAGE_LABELS, STATE_LABELS
from .payload import text_field
from .sessions import active, close, work_dir
from .skill import check_files, check_model, copy_skill, install_engine, overlay, tree_hash
from .storage import base_dir

ACTIONS = ('applied', 'rejected')


def artifact(root, s, name, text):
    """Write an agent-readable stage artifact under sN/; return its path."""
    path = base_dir(root) / s['id'] / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return str(path)


def confirmed(payload, where):
    if payload.get('confirmed') is not True:
        raise ValueError(f'{where}: confirm with the user, then send `"confirmed": true`.')


def done_ground(root, state, s, payload):
    values = {key: text_field(payload, key, 'GROUND') for key in GROUND_FIELDS}
    confirmed(payload, 'GROUND')
    if values['mode'] not in ('new', 'revise'):
        raise ValueError('GROUND: `mode` must be new or revise.')
    target = Path(values['target'])
    target = (target if target.is_absolute() else root / target).resolve()
    if not re.fullmatch(r'[a-z0-9-]{1,64}', target.name):
        raise ValueError(f'Target directory name `{target.name}` must match [a-z0-9-], 1-64 characters.')
    held = [o['id'] for o in active(state) if o['id'] != s['id'] and o.get('target') == str(target)]
    if held:
        raise ValueError(f'{target} is held by active session {held[0]}; run `status`.')
    exists = (target / 'SKILL.md').is_file()
    if values['mode'] == 'new' and exists:
        raise ValueError(f'{target / "SKILL.md"} exists; use `"mode": "revise"`.')
    if values['mode'] == 'revise' and not exists:
        raise ValueError(f'{target / "SKILL.md"} does not exist; use `"mode": "new"`.')
    values['target'] = str(target)
    s.update(values, reviews=[])
    if values['mode'] == 'revise':
        copy_skill(target, work_dir(root, s, 'backup'))
        copy_skill(target, work_dir(root, s, 'draft'))
        s['target_hash'] = tree_hash(target)
    else:
        work_dir(root, s, 'draft').mkdir(parents=True, exist_ok=True)
    s['phase'] = 'design'


def check_criteria(model, router, criteria):
    """Labels from execution.md must fit the chosen model and router."""
    labels = STAGE_LABELS + STATE_LABELS + ROUTER_LABELS
    if not isinstance(criteria, list) or any(c not in labels for c in criteria):
        raise ValueError(f'DESIGN: `criteria` must be a list of labels from execution.md: {", ".join(labels)}.')
    has = lambda group: any(c in group for c in criteria)
    if model == 'semantic' and (has(STAGE_LABELS) or has(STATE_LABELS)):
        raise ValueError('DESIGN: semantic carries no stage labels; pick a staged model or drop them.')
    if model != 'semantic' and not has(STAGE_LABELS):
        raise ValueError(f'DESIGN: {model} needs one of {", ".join(STAGE_LABELS)}; else use semantic.')
    if model == 'stateful' and not has(STATE_LABELS):
        raise ValueError(f'DESIGN: stateful needs one of {", ".join(STATE_LABELS)}; else use stateless.')
    if model == 'stateless' and has(STATE_LABELS):
        raise ValueError('DESIGN: a state label (resume, inspect, loop, recover) requires stateful.')
    if router != has(ROUTER_LABELS):
        raise ValueError('DESIGN: `router: true` and the `conditional` label go together.')


def check_stages(model, criteria, stages):
    """Staged models list each stage's output and check; `loop` needs a loop_limit."""
    if model == 'semantic':
        if stages:
            raise ValueError('DESIGN: semantic has no `stages`; omit it.')
        return []
    if not isinstance(stages, list) or not stages:
        raise ValueError('DESIGN: `stages` must list {name, output, check} for each stage.')
    for index, st in enumerate(stages):
        where = f'stages[{index}]'
        for key in ('name', 'output', 'check'):
            text_field(st, key, where)
        limit = st.get('loop_limit')
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 1):
            raise ValueError(f'{where}: `loop_limit` must be an integer >= 1.')
    if ('loop' in criteria) != any('loop_limit' in st for st in stages):
        raise ValueError('DESIGN: `loop` in criteria and a stage `loop_limit` go together.')
    names = [st['name'].strip() for st in stages]
    if len(set(names)) != len(names):
        raise ValueError('DESIGN: stage names must be unique.')
    return [dict(st, name=st['name'].strip()) for st in stages]


def done_design(root, state, s, payload):
    model = payload.get('model')
    if model not in MODELS:
        raise ValueError(f'DESIGN: `model` must be one of {", ".join(MODELS)}.')
    if not isinstance(payload.get('router'), bool):
        raise ValueError('DESIGN: `router` must be true or false.')
    criteria = payload.get('criteria', [])
    check_criteria(model, payload['router'], criteria)
    stages = check_stages(model, criteria, payload.get('stages'))
    design = {'model': model, 'router': payload['router'], 'criteria': criteria, 'stages': stages,
              'why': text_field(payload, 'why', 'DESIGN')}
    confirmed(payload, 'DESIGN')
    lines = [f'# Design: {Path(s["target"]).name}', '', f'Model: {model}', f'Router: {"yes" if design["router"] else "no"}',
             f'Criteria: {", ".join(criteria) or "none"}', f'Why: {design["why"]}']
    if stages:
        lines += ['', 'Stages:'] + [
            f'- {st["name"]}: output {st["output"]}; check {st["check"]}'
            + (f'; loop limit {st["loop_limit"]}' if 'loop_limit' in st else '') for st in stages]
    design['artifact'] = artifact(root, s, 'design.md', '\n'.join(lines) + '\n')
    s['design'] = design
    if model != 'semantic':
        install_engine(work_dir(root, s, 'draft'), model)
    s['phase'] = 'draft'


def check_draft(root, s):
    draft = work_dir(root, s, 'draft')
    check_files(draft)
    check_model(draft, s['design']['model'], s['design']['router'], [st['name'] for st in s['design'].get('stages', [])])
    return draft


def done_draft(root, state, s, payload):
    check_draft(root, s)
    s['phase'] = 'review'


def done_review(root, state, s, payload):
    findings = payload.get('findings')
    if not isinstance(findings, list) or not all(isinstance(f, dict) for f in findings):
        raise ValueError('REVIEW: `findings` must be a list of objects.')
    if not findings and payload.get('none_found') is not True:
        raise ValueError('REVIEW: no findings; send `"none_found": true` to confirm.')
    for index, f in enumerate(findings):
        where = f'findings[{index}]'
        for key in ('file', 'finding', 'why'):
            text_field(f, key, where)
        if f.get('action') not in ACTIONS:
            raise ValueError(f'{where}: `action` must be applied or rejected.')
    n = len(s['reviews']) + 1
    applied = sum(f['action'] == 'applied' for f in findings)
    done = payload.get('confirmed') is True
    if not done and n >= REVIEW_LIMIT:
        raise ValueError(f'REVIEW: loop {n}/{REVIEW_LIMIT} is the last; confirm with the user and send '
                         '`"confirmed": true`, or `abandon`.')
    if not done and not applied:
        raise ValueError('REVIEW: nothing applied; confirm the draft with the user and send `"confirmed": true`, '
                         'or record the edits they ask for as applied findings.')
    check_draft(root, s)
    if done:
        check_target(s)
    lines = [f'# Review {n}: {Path(s["target"]).name}', ''] + \
            [f'- {f["file"]} [{f["action"]}]: {f["finding"]} ({f["why"]})' for f in findings] + \
            ([] if findings else ['- none found'])
    s['reviews'].append({'n': n, 'findings': len(findings), 'applied': applied,
                         'artifact': artifact(root, s, f'review-{n}.md', '\n'.join(lines) + '\n')})
    if done:
        overlay(work_dir(root, s, 'draft'), Path(s['target']))
        close(s, 'complete')


def check_target(s):
    """Refuse to write a target that changed outside this session."""
    target = Path(s['target'])
    if s['mode'] == 'new' and (target / 'SKILL.md').exists():
        raise ValueError(f'{target / "SKILL.md"} appeared during the session; move it or use revise.')
    if s['mode'] == 'revise' and tree_hash(target) != s['target_hash']:
        raise ValueError(f'{target} changed since GROUND; abandon and start again from the current target.')


PHASES = {'ground': done_ground, 'design': done_design, 'draft': done_draft, 'review': done_review}
