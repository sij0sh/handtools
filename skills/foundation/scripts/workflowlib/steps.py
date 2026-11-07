"""foundation stages: discover -> interview -> assess -> [apply -> validate].

Stateless: nothing saved; `done --stage S` names the finished stage and the orchestrator carries results.
Checks that run scripts use the cwd as the project root (run from the project root).
"""
import json
import subprocess
import sys
from pathlib import Path

MODE = 'stateless'
ORDER = ['discover', 'interview', 'assess', 'apply', 'validate']

SCRIPTS = Path(__file__).resolve().parents[1]
SKILL = SCRIPTS.parent
# The ADR log and its one definition belong to simple-by-design, beside this skill in the handtools bundle.
DESIGN = SKILL.parent / 'simple-by-design'
ADR_LOG = '.agents/design/decisions.json'
RECORD_CMD = f'python3 {DESIGN / "scripts" / "designflow.py"} --root . record'
DECISIONS = '.agents/foundation.json'
RECORD = 'decisions-record'
STATUSES = ['present', 'partial', 'missing', 'n/a', 'unknown']
CAPABILITIES = {
    'runtime-versions': 'Runtime and tool versions pinned in a committed config (e.g. mise.toml)',
    'lockfiles': 'Dependency lockfiles committed',
    'one-command-setup': 'One command installs tools/deps and starts local dev; README setup steps match config',
    'tests-lint': 'Automated tests and linting runnable locally',
    'ci-checks': 'CI runs the same checks on every pull request',
    'dependency-updates': 'Automated dependency and tool update PRs',
    'architecture-doc': 'Architecture overview documented (diagram as code)',
    'adrs': f'Important decisions recorded in {ADR_LOG} (the ADR log) and committed',
    'db-migrations': 'Database schema changes versioned as migrations',
    'secrets-excluded': 'Secrets kept out of Git; .env.example documents variables',
    'deployment-doc': 'Deployment process documented and automated where it exists',
    'logging-health': 'Structured logging and a health check',
    'declarative-infra': 'Infrastructure managed declaratively where infrastructure exists',
}
BASELINE = '\n'.join(f'- `{k}`: {v}' for k, v in CAPABILITIES.items())

PROMPTS = {
    'discover': (
        f'Run `python3 {SCRIPTS / "audit.py"} --root .` (read-only) and read the files it lists. Do not run project code. '
        'Classify the project: `kind` greenfield (little or no code/history) or brownfield; '
        '`maturity` prototype, mvp, or production; `mode` from the user\'s request (the orchestrator passes it): audit (report only) '
        'or plan (report, then offer to apply approved items; the default for bootstrap/reassess). '
        'Pass the audit JSON and your classification to the next stages. '
        'Send `{"kind": "...", "maturity": "...", "mode": "..."}`.'
    ),
    'interview': (
        f'Read `{DECISIONS}` if it exists; treat its decisions as settled. From the audit, list the '
        'high-impact decisions still open (what is being built, prototype/MVP/production, where it runs, '
        'solo or team, cost/security/compliance limits, what must not change in a brownfield repo). '
        'Ask only the ones the repo and recorded decisions cannot answer, in one batch of at most 5. '
        'If recorded maturity is below what the audit now shows, ask whether to reassess. '
        'Send `{"questions_asked": N, "decisions": {"topic": "answer", ...}}` with every decision, recorded and new.'
    ),
    'assess': (
        f'Read `{SKILL / "references" / "greenfield.md"}` or `{SKILL / "references" / "brownfield.md"}` per `kind`. '
        'For `adrs`, use the audit\'s `adr_log`: if it exists but `ignored` or not `committed`, the gap is the '
        '.gitignore fix; legacy Markdown ADRs count as present, and converting them into the log is a separate '
        'item to offer. Classify every baseline capability as present, partial, missing, n/a, or unknown, each with '
        'evidence (file path, or what was searched and not found):\n'
        f'{BASELINE}\n\n'
        'Report: current-state summary; the classification table; for each gap the smallest fix, its '
        'impact and effort, ordered by priority; proposed file-level changes; risks and tradeoffs. '
        'Recommend nothing the decisions make unnecessary; do not re-propose ids in the record\'s `declined` unless the user asks to reassess. '
        'Ask the user which items to apply (plan mode) and, in any mode, whether to record the decisions '
        f'(`{RECORD}`, writes only `{DECISIONS}`), and which project tests/linters `validate` may run. '
        'Send `{"mode": "audit|plan", "capabilities": {"<id>": {"status": "...", "evidence": "..."}, ...}, '
        '"approved": ["<id>", ...], "run": ["command", ...]}`; `approved` lists only ids the user approved, else [].'
    ),
    'apply': (
        f'Read `{SKILL / "references" / "greenfield.md"}` or `{SKILL / "references" / "brownfield.md"}` per `kind`. '
        'Implement only the approved items, as small reviewable changes that keep existing conventions; '
        f'start from `{SKILL / "assets"}` templates where one fits and adapt it to the project. Do not touch unrelated '
        f'config. ADRs (`adrs`): record decisions only by piping a payload into `{RECORD_CMD}` (shape: '
        f'`{DESIGN / "references" / "decisions.schema.json"}`; send rows without `id` or `status`); never edit '
        f'{ADR_LOG} directly and never write Markdown ADRs. Convert legacy Markdown ADRs only if the user approved '
        'that conversion. Write `{DECISIONS}` with `kind`, `maturity`, `decisions`, `accepted` (approved ids), '
        '`declined` (proposed but not approved ids), and `updated` (ISO date), merging any existing record. '
        f'If `{RECORD}` is the only approved item, write only the record. '
        'Done when the files are written; send `{"changed": ["path", ...]}`.'
    ),
    'validate': (
        f'Run `python3 {SCRIPTS / "validate.py"} --root .`, only the test/lint commands the user approved in assess, and review `git diff`. '
        'Report what changed, what passed, and what remains (every failure, skipped check, and unapproved gap). '
        'Send `{"changed": [...], "passed": [...], "remaining": [...]}`.'
    ),
}

DONE_MSG = 'DONE: present the report and stop for review.'


def _enum(payload, key, allowed):
    if payload.get(key) not in allowed:
        raise ValueError(f'`{key}` must be one of: {", ".join(allowed)}.')


def _run(script):
    out = subprocess.run([sys.executable, str(SCRIPTS / script), '--root', '.'], capture_output=True, text=True)
    try:
        return out.returncode, json.loads(out.stdout)
    except json.JSONDecodeError:
        raise ValueError(f'{script} did not print JSON: {out.stderr.strip() or out.stdout[:200]}') from None


def check_discover(state, payload):
    code, _ = _run('audit.py')
    if code != 0:
        raise ValueError('audit.py failed; fix the run before classifying.')
    _enum(payload, 'kind', ['greenfield', 'brownfield'])
    _enum(payload, 'maturity', ['prototype', 'mvp', 'production'])
    _enum(payload, 'mode', ['audit', 'plan'])


def check_interview(state, payload):
    n = payload.get('questions_asked')
    if not isinstance(n, int) or not 0 <= n <= 5:
        raise ValueError('`questions_asked` must be an integer from 0 to 5.')
    if not isinstance(payload.get('decisions'), dict):
        raise ValueError('`decisions` must be an object.')


def check_assess(state, payload):
    _enum(payload, 'mode', ['audit', 'plan'])
    caps = payload.get('capabilities')
    if not isinstance(caps, dict):
        raise ValueError('`capabilities` must be an object keyed by capability id.')
    missing = [k for k in CAPABILITIES if k not in caps]
    if missing:
        raise ValueError(f'Classify every capability; missing: {", ".join(missing)}.')
    for k, v in caps.items():
        if not isinstance(v, dict) or v.get('status') not in STATUSES or not str(v.get('evidence', '')).strip():
            raise ValueError(f'`{k}` needs a status ({", ".join(STATUSES)}) and evidence.')
    approved = payload.get('approved')
    if not isinstance(approved, list) or any(a not in CAPABILITIES and a != RECORD for a in approved):
        raise ValueError(f'`approved` must be a list of capability ids or `{RECORD}`.')
    if payload['mode'] == 'audit' and set(approved) - {RECORD}:
        raise ValueError(f'Audit mode writes only the record; `approved` may hold only `{RECORD}`.')
    if not isinstance(payload.get('run', []), list):
        raise ValueError('`run` must be a list of approved commands.')


def check_apply(state, payload):
    path = Path(DECISIONS)
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f'{DECISIONS} must exist and be valid JSON: {error}') from None
    for key in ('kind', 'maturity', 'decisions', 'accepted', 'declined', 'updated'):
        if key not in record:
            raise ValueError(f'{DECISIONS} is missing `{key}`.')
    if not isinstance(payload.get('changed'), list) or not payload['changed']:
        raise ValueError('`changed` must list the files written.')


def check_validate(state, payload):
    for key in ('changed', 'passed', 'remaining'):
        if not isinstance(payload.get(key), list):
            raise ValueError(f'`{key}` must be a list.')
    _, result = _run('validate.py')
    unreported = [f for f in result.get('failed', []) if not any(f in str(r) for r in payload['remaining'])]
    if unreported:
        raise ValueError(f'validate.py failures missing from `remaining`: {", ".join(unreported)}.')


CHECKS = {'discover': check_discover, 'interview': check_interview, 'assess': check_assess,
          'apply': check_apply, 'validate': check_validate}


def advance(state, payload):
    """Return the next stage, or None to finish. Assess ends the run unless the user approved items."""
    phase = state['phase']
    if phase == 'assess':
        return 'apply' if payload['approved'] else None
    if phase == 'validate':
        return None
    return ORDER[ORDER.index(phase) + 1]
