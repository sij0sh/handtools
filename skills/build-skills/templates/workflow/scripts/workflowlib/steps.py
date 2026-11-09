"""The workflow itself: the only file a skill author edits.

Example flow: do X, then Y; if Y's result is A, do Z, else finish.
Each prompt ends on a criterion its check verifies. Payloads arrive as JSON on stdin.
MODE: 'stateful' tracks one run per project; 'stateless' saves nothing and `done --stage S` names the step.
AREA: this skill's folder under the per-user state root (see storage.py); set it to the skill's name.
"""
MODE = 'stateful'
AREA = 'workflow'
ORDER = ['x', 'y', 'z']

PROMPTS = {
    'x': 'Do X. Done when X is complete.',
    'y': 'Do Y. Send `{"result": "R"}`, where R is Y\'s outcome (A or other).',
    'z': 'Y gave A, so do Z. Done when Z is complete.',
}

DONE_MSG = 'DONE: workflow complete.'


def check_y(state, payload):
    if not isinstance(payload.get('result'), str) or not payload['result']:
        raise ValueError('Step y needs `{"result": "R"}`.')


# Per-step verification; raise ValueError to refuse `done`.
CHECKS = {'y': check_y}


def advance(state, payload):
    """Return the next step, or None to finish."""
    phase = state['phase']
    if phase == 'y':
        state['result'] = payload['result']
        return 'z' if payload['result'] == 'A' else None
    if phase == 'z':
        return None
    return ORDER[ORDER.index(phase) + 1]
