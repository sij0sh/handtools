"""build-skills' sessions on the engine's registry (handtools' _engine/sessions.py).

The registry also records the project `root`; each session adds `phase` and, from GROUND, `target`.
"""
from pathlib import Path

from _engine import sessions as registry

from .config import AREA

timestamp = registry.timestamp
find = registry.find
active = registry.active
select_active = registry.select_active


def base_dir(root):
    return registry.base(AREA, root)


def load_registry(root, allow_missing=False):
    state = registry.load(AREA, root, allow_missing)
    if not isinstance(state, dict) or state.get('version') != 1 or not isinstance(state.get('sessions'), list):
        raise ValueError(f'{registry.path(AREA, root)} is not a version-1 registry.')
    state.setdefault('root', str(root))
    return state


def save_registry(root, state):
    registry.save(AREA, root, state)


def add(state):
    return registry.add(state, phase='ground', revision=0, requests={})


def close(session, status):
    registry.close(session, status, 'closed')


def work_dir(root, s, kind):
    """sN/<kind>/<skill name>: `draft` (working copy) or `backup` (revise: original)."""
    return base_dir(root) / s['id'] / kind / Path(s['target']).name
