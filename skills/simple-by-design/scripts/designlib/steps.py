"""Text the agent and user see: step prompts, step output, summaries, listings.

Pure functions: callers pass every value in; nothing here reads or writes files.
"""
import json

from . import record

PROMPTS = {
    'ground': (
        'Establish the goal, constraints, success criteria, and relevant existing '
        'decisions or code. Send a new goal set (`goal`, `constraints`, `criteria`), '
        'or `{{"id": "G#"}}` to reuse an earlier set for the same goal that no '
        'active session holds.\n\n'
        'Defaults ({defaults}):\n\n{defaults_text}'
    ),
    'branch': (
        'List open material questions as new decision rows (no `answer`). Link a '
        'dependency with `after` when one answer requires another.'
    ),
    'decide': (
        'Resolve questions whose dependencies are settled. Settle each question '
        'from the first source that answers it:\n'
        '1. Requirements and adopted decisions.\n'
        '2. Existing project conventions that fit the goal. Replace one only '
        'through an explicit decision.\n'
        '3. Defaults: {defaults} (re-read if not in context).\n'
        '4. The relevant reference:\n'
        '   - Ownership, contracts, dependencies, boundaries, or failures: {contract}\n'
        '   - Language-specific design, types, errors, or concurrency: '
        '{languages}/<language>.md (available: {language_list})\n'
        '   - Agent instructions (skills, prompts, AGENTS.md, CLAUDE.md, system prompts): {instructions}\n'
        '5. The simplest adequate choice.\n'
        'Ask the user when essential intent, permissions, or a consequential '
        'tradeoff stays unanswered by all five.\n'
        'Resolve a row by giving it an `answer`; add a `rationale` for each '
        'non-obvious choice. Add questions the answers raise; drop questions that '
        'became irrelevant.'
    ),
    'challenge': (
        'Assign a subagent this task: '
        '"Analyze this goal and its resolved decisions critically for gaps in omitted questions. '
        'Following all decisions to achieve the goal, could two solutions still be designed differently? '
        'If so how, where, and what significance?" '
        'If no subagent is available, complete the task yourself. '
        'Send the missing questions as rows with dependencies; answer those you '
        'can settle now and leave the rest open. Send no payload when no gaps remain.'
    ),
}

PAYLOAD = (
    'Payload: JSON on stdin; send only changes. Every key is optional:\n'
    '{"goal": "...", "constraints": ["..."], "criteria": ["..."],\n'
    ' "decisions": [{"id": "D#", "question": "...", "answer": "...", '
    '"after": ["D#"], "rationale": "..."}]}\n'
    'Rows upsert by `id`; omitted fields stay; `null` removes a field; '
    '`{"id": "D#", "drop": true}` deletes a row. A row with an `answer` is resolved.'
)

DONE_MSG = 'DONE: present this summary to the user and stop; do not implement without approval.'


def render_step(session, rec, holders, launcher, limit, refs):
    """Current step: prompt, goal (or earlier goals at ground), payload rule, command."""
    if session['goal'] is None:
        rows = [json.dumps({'id': g['id'], 'goal': g['goal'], 'held_by': holders.get(g['id'])})
                for g in rec['goals']]
        current = 'EARLIER GOALS:\n' + ('\n'.join(rows) if rows else '(none)')
    else:
        goal = record.find_goal(rec, session['goal'])
        current = (f'GOAL {goal["id"]} (next row id: {record.next_id(goal["decisions"], "D")}):\n'
                   + json.dumps(record.public_goal(goal), indent=2))
    lines = [
        f'SESSION: {session["id"]}',
        f'PHASE: {session["phase"].upper()}  |  LOOP: {min(session["cycle"], limit)}/{limit}',
        PROMPTS[session['phase']].format(**refs),
        '',
        current,
        '',
        PAYLOAD,
        '',
        f"Then run: {launcher} done --session {session['id']} <<'EOF'",
        '<payload>',
        'EOF',
        '(Windows: pipe a JSON file into the same command.)',
        'Do NOT jump to another phase or implement yet.',
    ]
    return '\n'.join(lines)


def render_goal(goal, detail=False):
    """One goal as Markdown. detail adds IDs, dependencies, dates and supersession (for `show`)."""
    lines = [f'# {goal["id"]}. {goal["goal"]}' if detail else f'# {goal["goal"]}']
    if goal.get('constraints'):
        lines += ['', '## Constraints'] + [f'- {item}' for item in goal['constraints']]
    if goal.get('criteria'):
        lines += ['', '## Success criteria'] + [f'- {item}' for item in goal['criteria']]
    shown = [d for d in goal['decisions'] if d['status'] == 'resolved' or (detail and d['status'] == 'superseded')]
    unresolved = [d for d in goal['decisions'] if d['status'] == 'open']
    if shown:
        lines += ['', '## Decisions']
        for decision in shown:
            title = f'{decision["id"]}. {decision["question"]}' if detail else decision['question']
            lines += ['', f'### {title}']
            if detail:
                meta = [f'Status: {decision["status"]}']
                if decision.get('date'):
                    meta.append(f'Date: {decision["date"]}')
                if decision.get('after'):
                    meta.append(f'After: {", ".join(decision["after"])}')
                if decision.get('superseded_by'):
                    meta.append(f'Superseded by: {decision["superseded_by"]}')
                lines.append(' | '.join(meta))
                lines.append('')
            lines.append(decision['answer'])
            if decision.get('rationale'):
                lines += ['', f'Reason: {decision["rationale"]}']
    if unresolved:
        label = (lambda d: f'{d["id"]}. {d["question"]}') if detail else (lambda d: d['question'])
        lines += ['', '## Open questions'] + [f'- {label(d)}' for d in unresolved]
    return lines


def summary(rec, session):
    """Close summary for the user: goal, resolved decisions, open questions."""
    goal = record.find_goal(rec, session['goal'])
    lines = render_goal(goal)
    lines[1:1] = ['', f'Session {session["id"]}.']
    index = next(i for i, item in enumerate(rec['goals']) if item['id'] == goal['id'])
    earlier = rec['goals'][:index]
    if earlier:
        lines += ['', '## Earlier goals'] + [f'- {item["goal"]}' for item in earlier]
    return '\n'.join(lines)


def show(rec, gid=None):
    """Read-only Markdown view of the whole record, or of one goal."""
    goals = [record.find_goal(rec, gid)] if gid else rec['goals']
    if not goals:
        return 'No decisions recorded.'
    return '\n\n'.join('\n'.join(render_goal(goal, detail=True)) for goal in goals)


def done_message(rec, session):
    return f'{summary(rec, session)}\n\n{DONE_MSG}'


def goal_label(rec, gid):
    if gid is None:
        return '-'
    for goal in rec['goals']:
        if goal['id'] == gid:
            return f'{gid}  {goal["goal"]}'
    return gid


def abandoned(rec, session):
    return (f'SESSION: {session["id"]}\n'
            f'STATUS: abandoned\n'
            f'GOAL: {goal_label(rec, session["goal"])}')


def session_list(rec, sessions, show_all):
    if not sessions:
        return 'No sessions.' if show_all else 'No active sessions.'
    return '\n'.join(
        f'{s["id"]}  {s["status"]:<9} {s["phase"]:<9}  {goal_label(rec, s["goal"])}'
        for s in sessions
    )
