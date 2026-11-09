"""Workflow adapter. Edit domain prompts/checks only; never edit vendored _engine.
Stateful = resumable journal; stateless = ephemeral (no resume/retained approval).
The shared planner is a library. No sibling skill is invoked.
"""
from _engine import planning
MODE = 'stateful'
PLANNING = True
AREA = 'workflow'
ORDER = ['plan', 'work', 'verify']
PROMPTS = {
    'plan': 'Create a proportional plan. Send {"plan": {"goal": "...", "constraints": [], "criteria": ["observable result"], "decisions": [], "blocking": [], "verification": "...", "challenged": true}}. Resolve blocking issues before work.',
    'work': 'Perform only the planned work within existing user authorization. Send {"result": "..."}; report blocked work rather than inventing completion.',
    'verify': 'Verify the observable acceptance criteria. Send {"passed": true, "evidence": "..."}; failed/skipped verification cannot close the run.',
}
DONE_MSG = 'DONE: verified workflow complete.'


def check_plan(state, payload):
    state['plan_digest'] = planning.require_ready(payload.get('plan'))
    state['plan'] = payload['plan']


def check_work(state, payload):
    if not isinstance(payload.get('result'), str) or not payload['result'].strip():
        raise ValueError('work needs result')


def check_verify(state, payload):
    if payload.get('passed') is not True or not isinstance(payload.get('evidence'), str) or not payload['evidence'].strip():
        raise ValueError('verify needs passed=true and evidence')

CHECKS = {'plan': check_plan, 'work': check_work, 'verify': check_verify}


def advance(state, payload):
    if state['phase'] == 'verify':
        return None
    return ORDER[ORDER.index(state['phase']) + 1]
