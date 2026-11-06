"""Per-stage prompt text, step rendering, and the session summary."""
import json
from pathlib import Path

from .config import REFS, REVIEW_LIMIT
from .sessions import work_dir


LAUNCH = 'From the project root, drive the run with `scripts/workflow.py` (`python3` on Linux/macOS, `python` on Windows):'
RUN_STEPS = {
    'stateful': f"""{LAUNCH}

1. `start`; do the printed stage, then run the printed `done` command, piping JSON when asked.
2. Repeat until `DONE`. Lost the current stage: `status`.""",
    'stateless': f"""{LAUNCH}

1. `start`; run each printed stage as its own execution (fresh subagent when available), passing on the results it needs.
2. Run the printed `done --stage S`, piping JSON when asked; repeat until `DONE`.""",
}
REVIEW_QUESTION = ('Is this skill the least instruction that closes the gap and meets the pass condition? List lines to '
                   'cut (output still passes without them) and missing behavior (output fails without it). '
                   'For each: file:line, change, effect on output.')


def ref(name):
    return str(REFS / name)


def header(s):
    return (f'Target: {s["target"]} ({s["mode"]})\nPurpose: {s["purpose"]}\nTrigger: {s["trigger"]}\n'
            f'Gap: {s["gap"]}\nPass condition: {s["pass_condition"]}')


def ground_prompt(root, s):
    return ('Agree with the user on the skill: purpose, trigger, gap (what the agent does without the skill and '
            'where that fails), and a pass condition observable in its output. '
            "Revise: read the existing skill at the target first; infer them, gap = the existing skill's shortfall. "
            'Done when the user agrees; send `confirmed: true`.',
            {'mode': 'new|revise', 'target': 'skills/release-notes', 'purpose': '...', 'trigger': '...',
             'gap': '...', 'pass_condition': '...', 'confirmed': True})


def design_prompt(root, s):
    read = f'Read the skill at {work_dir(root, s, "draft")}. ' if s['mode'] == 'revise' else ''
    revise = 'Show the user any change from the existing model. ' if s['mode'] == 'revise' else ''
    return (f'{header(s)}\n\n{read}Choose the execution model, stages, and whether to route, per '
            f'{ref("execution.md")}. `criteria`: every label that is yes. Staged models: `stages` in run order; '
            f'semantic omits it. {revise}Done when the user agrees to the design; send `confirmed: true`.',
            {'model': 'semantic|stateless|stateful', 'router': False, 'criteria': ['focus', 'loop'],
             'stages': [{'name': 'plan', 'output': '...', 'check': 'user'},
                        {'name': 'review', 'output': '...', 'check': '...', 'loop_limit': 3}],
             'why': '...', 'confirmed': True})


def draft_prompt(root, s):
    d, draft = s['design'], work_dir(root, s, 'draft')
    if d['model'] == 'semantic':
        engine = (' Remove scripts/workflowlib/: the semantic model ships no engine.'
                  if (draft / 'scripts' / 'workflowlib').exists() else '')
    else:
        order = [st['name'] for st in d['stages']]
        engine = (f" The engine is in scripts/ with MODE = '{d['model']}'. Edit only scripts/workflowlib/steps.py: "
                  f'ORDER = {order}, PROMPTS, CHECKS, advance. SKILL.md body:\n\n{RUN_STEPS[d["model"]]}')
    return (f'{header(s)}\nDesign: {d["artifact"]}\n\nWrite only what closes the gap, in {draft}, per the design '
            f'and {ref("instructions.md")}: frontmatter `name: {Path(s["target"]).name}`, a one-line `description`, '
            f'and `disable-model-invocation: true` unless clearly model-invoked; name '
            f'every references/ leaf in SKILL.md or scripts/.{engine}\n\nDone when `done` passes the shape check.', {})


def review_task(root, s):
    """The reviewer subagent's whole task: self-contained, one question."""
    scope = '' if s['design']['model'] == 'semantic' else \
        (' Review SKILL.md, references/, and PROMPTS and CHECKS in scripts/workflowlib/steps.py; the other '
         "scripts/ files and SKILL.md's run steps are fixed.")
    return (f'Read the skill at {work_dir(root, s, "draft")}. Purpose: {s["purpose"]} Gap: {s["gap"]} Pass condition: '
            f'{s["pass_condition"]} Design: {s["design"]["artifact"]}. Criteria: {ref("instructions.md")}.{scope} '
            f'Do not edit files. {REVIEW_QUESTION} Report design flaws (model, stages, router) separately.')


def review_prompt(root, s):
    n = len(s['reviews']) + 1
    return (f'{header(s)}\nDesign: {s["design"]["artifact"]}\nDraft: {work_dir(root, s, "draft")}\n'
            f'Loop: {n}/{REVIEW_LIMIT}\n\n'
            f'1. Give a fresh subagent this task: "{review_task(root, s)}" Without subagents, answer it yourself.\n'
            '2. Check each finding against the pass condition and the design. '
            'Apply the findings that hold to the draft; reject the rest. Tell the user about design flaws; '
            'review cannot change the design (`abandon` and restart to redesign).\n'
            '3. Show the user the draft. Record edits they ask for as applied findings. '
            '`confirmed: true` writes the draft to the target; otherwise applied findings start the next loop.',
            {'findings': [{'file': 'SKILL.md:3', 'finding': '...', 'action': 'applied|rejected', 'why': '...'}],
             'none_found': False, 'confirmed': True})


PROMPTS = {'ground': ground_prompt, 'design': design_prompt, 'draft': draft_prompt, 'review': review_prompt}


def render(root, s, launcher):
    text, example = PROMPTS[s['phase']](root, s)
    return '\n'.join([
        f'SESSION: {s["id"]}',
        f'PHASE: {s["phase"].upper()}',
        text,
        '',
        'Payload (JSON on stdin), for example:',
        json.dumps(example),
        '',
        f"Then run: {launcher} done --session {s['id']} <<'EOF'",
        '<payload>',
        'EOF',
        '(Windows: pipe a JSON file into the same command.)',
    ])


def summary(root, s):
    lines = [f'# {s.get("target") or "(no target)"}', '', f'Session {s["id"]}, mode {s.get("mode", "-")}.']
    if s.get('purpose'):
        lines.append(f'Purpose: {s["purpose"]}')
    if s.get('design'):
        d = s['design']
        lines.append(f'Model: {d["model"]}{", router" if d["router"] else ""}. '
                     f'Criteria: {", ".join(d.get("criteria", [])) or "none"}. Design: {d["artifact"]}')
    lines += [f'- review {r["n"]}: {r.get("applied", 0)}/{r["findings"]} findings applied. {r["artifact"]}'
              for r in s.get('reviews', [])]
    if s.get('status') == 'complete':
        lines.append(f'Written to {s["target"]}.')
    if s.get('mode') == 'revise':
        lines.append(f'Original backup: {work_dir(root, s, "backup")}')
    return '\n'.join(lines)
