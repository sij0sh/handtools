"""Paths and constants."""
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
REFS = SKILL_DIR / 'references'
TEMPLATE = SKILL_DIR / 'templates' / 'workflow' / 'scripts'  # launcher workflow.py and example steps.py
ENGINE = SKILL_DIR.parent / '_engine'  # handtools' one engine, vendored into each workflow skill
# Run state: <state root>/build-skills/<project key>/ (_engine/storage.py).
AREA = 'build-skills'
KINDS = ('prompt', 'staged')
MODELS = ('stateless', 'stateful')
GROUND_FIELDS = ['mode', 'kind', 'target', 'purpose', 'trigger', 'gap', 'pass_condition']
# Labels defined in references/execution.md.
STAGE_LABELS = ('focus', 'gate', 'isolate', 'enforce')
STATE_LABELS = ('resume', 'inspect', 'loop', 'recover')
ROUTER_LABELS = ('conditional',)
EXCLUDE_DIRS = {'state', '.agents', '.git', '__pycache__', '.pytest_cache', '.venv'}
DESCRIPTION_MAX = 100
REVIEW_LIMIT = 3
DONE_MSG = 'DONE: present this summary to the user and stop.'
