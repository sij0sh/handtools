"""Per-stage prompt text, step rendering, and the session summary."""
import json
from pathlib import Path

from .config import REFS, REVIEW_LIMIT
from .sessions import work_dir


LAUNCH = ("Set `S` to this skill's absolute directory. From the project root, drive the run with "
          '`S/scripts/workflow.py` (`python3` on Linux/macOS, `python` on Windows):')
RUN_STEPS = {
    'stateful': f"""{LAUNCH}

1. `start`; do the printed stage, then run the printed `done` command, piping JSON when asked.
2. Repeat until `DONE`. Lost the current stage: `status`.""",
    'stateless': f"""{LAUNCH}

1. `start`; run each printed stage as its own execution (fresh subagent when available), passing on the results it needs.
2. Run the printed `done --stage S`, piping JSON when asked; repeat until `DONE`.""",
}
CUTS = ('List lines to cut (output still passes without them) and missing behavior (output fails without it). '
        'For each: file:line, change, effect on output.')
REVIEW_QUESTION = f'Is this skill the least instruction that closes the gap and meets the pass condition? {CUTS}'
PROMPT_QUESTION = ("Its body is a saved prompt: the user runs the skill and the agent receives exactly this text as "
                   "the user's prompt. Would an agent given exactly this text produce output that meets the pass "
                   f'condition? {CUTS}')


def ref(name):
    return str(REFS / name)


def plan(s):
    """The skill's shape for prompts: saved prompt, or the staged design artifact."""
    return 'Kind: saved prompt' if s['kind'] == 'prompt' else f'Design: {s["design"]["artifact"]}'


def header(s):
    return (f'Target: {s["target"]} ({s["mode"]}, {s["kind"]})\nPurpose: {s["purpose"]}\nTrigger: {s["trigger"]}\n'
            f'Gap: {s["gap"]}\nPass condition: {s["pass_condition"]}')


def ground_prompt(root, s):
    return ('Agree with the user on the skill: purpose, trigger, gap (what the agent does without the skill and '
            'where that fails), and a pass condition observable in its output. '
            "Revise: read the existing skill at the target first; infer them, gap = the existing skill's shortfall. "
            f'Choose `kind` per {ref("execution.md")} section 1: `prompt` (saved prompt) or `staged` (default); '
            'revise: tell the user when it changes the existing kind. If the user gave the prompt wording, send it '
            'as `wording`; it is used verbatim. Done when the user agrees; send `confirmed: true`.',
            {'mode': 'new|revise', 'kind': 'staged|prompt', 'target': 'skills/release-notes', 'purpose': '...',
             'trigger': '...', 'gap': '...', 'pass_condition': '...', 'wording': '(optional)', 'confirmed': True})


def design_prompt(root, s):
    read = f'Read the skill at {work_dir(root, s, "draft")}. ' if s['mode'] == 'revise' else ''
    revise = 'Show the user any change from the existing model. ' if s['mode'] == 'revise' else ''
    return (f'{header(s)}\n\n{read}Choose the execution model (stateless unless a state label is yes), stages, '
            f'and whether to route, per {ref("execution.md")}. `criteria`: every label that is yes. `stages` in run '
            f'order. {revise}Done when the user agrees to the design; send `confirmed: true`.',
            {'model': 'stateless|stateful', 'router': False, 'criteria': ['focus', 'loop'],
             'stages': [{'name': 'plan', 'output': '...', 'check': 'user'},
                        {'name': 'review', 'output': '...', 'check': '...', 'loop_limit': 3}],
             'why': '...', 'confirmed': True})


def draft_prompt(root, s):
    draft, name = work_dir(root, s, 'draft'), Path(s['target']).name
    if s['kind'] == 'prompt':
        wording = f" Body, verbatim (the user's wording):\n\n{s['wording']}\n\n" if s.get('wording') else ' '
        return (f'{header(s)}\n{plan(s)}\n\nWrite the saved prompt in {draft}/SKILL.md per '
                f'{ref("instructions.md")}: frontmatter `name: {name}`, a one-line `description`, and '
                f'`disable-model-invocation: true`; the body is the prompt itself.{wording}SKILL.md only: remove '
                'scripts/ and references/ if present.\n\nDone when `done` passes the shape check.', {})
    d = s['design']
    order = [st['name'] for st in d['stages']]
    engine = (f"The engine is in scripts/ with MODE = '{d['model']}' and AREA = '{name}'. Edit only scripts/steps.py (scripts/_engine/ is a vendored copy; never edit it): "
              f'ORDER = {order}, PROMPTS, CHECKS, advance. SKILL.md body:\n\n{RUN_STEPS[d["model"]]}')
    return (f'{header(s)}\n{plan(s)}\n\nWrite only what closes the gap, in {draft}, per the design '
            f'and {ref("instructions.md")}: frontmatter `name: {name}`, a one-line `description`, '
            f'and `disable-model-invocation: true` unless clearly model-invoked; name '
            f'every references/ leaf in SKILL.md or scripts/. Cite shared design rules from '
            f'`S/../simple-by-design/` (defaults, contracts, instructions, languages, decision schema) instead of '
            f'copying them; the script writes agents/openai.yaml from the frontmatter. {engine}\n\nDone when `done` passes the shape check.', {})


def review_task(root, s):
    """The reviewer subagent's whole task: self-contained, one question."""
    facts = f'Purpose: {s["purpose"]} Gap: {s["gap"]} Pass condition: {s["pass_condition"]}'
    if s['kind'] == 'prompt':
        return (f'Read {work_dir(root, s, "draft")}/SKILL.md. {PROMPT_QUESTION} {facts} Criteria: '
                f'{ref("instructions.md")}. Do not edit files.')
    return (f'Read the skill at {work_dir(root, s, "draft")}. {facts} {plan(s)}. Criteria: {ref("instructions.md")}. '
            'Review SKILL.md, references/, and PROMPTS and CHECKS in scripts/steps.py; the other '
            "scripts/ files and SKILL.md's run steps are fixed. "
            f'Do not edit files. {REVIEW_QUESTION} Report design flaws (model, stages, router) separately.')


def review_prompt(root, s):
    n = len(s['reviews']) + 1
    verbatim = " Change the user's wording only if they agree." if s.get('wording') else ''
    against = '' if s['kind'] == 'prompt' else ' and the design'
    return (f'{header(s)}\n{plan(s)}\nDraft: {work_dir(root, s, "draft")}\n'
            f'Loop: {n}/{REVIEW_LIMIT}\n\n'
            f'1. Give a fresh subagent this task: "{review_task(root, s)}" Without subagents, answer it yourself.\n'
            f'2. Check each finding against the pass condition{against}. '
            f'Apply the findings that hold to the draft; reject the rest.{verbatim} Tell the user about design flaws; '
            'review cannot change the kind or design (`abandon` and restart to redesign).\n'
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
    if s.get('kind') == 'prompt':
        lines.append('Kind: saved prompt.')
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
