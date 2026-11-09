"""Per-user state: root, project key, state dirs, JSON files, and the lock around writes.

Layout: <state root>/<area>/<project key>/, state root = $HANDTOOLS_STATE or ~/.agents/state
(%USERPROFILE%\\.agents\\state on Windows). Each skill names its area in one constant (AREA).
Nothing is written inside the installed skill, whose folder a plugin update replaces.
"""
import hashlib
import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

ENV = 'HANDTOOLS_STATE'
LOCK_TIMEOUT = 5.0
LOCK_STALE = 30.0


def state_root():
    """`$HANDTOOLS_STATE` when set, else ~/.agents/state."""
    override = os.environ.get(ENV)
    return Path(override).expanduser().resolve() if override else Path.home() / '.agents' / 'state'


def project_root(arg):
    """`--root`, else the git top level, else cwd."""
    if arg:
        return Path(arg).resolve()
    try:
        out = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True)
        return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd().resolve()


def project_key(root):
    """<dirname>-<sha8 of the resolved root path>; stable for one checkout, distinct per clone."""
    digest = hashlib.sha256(os.path.normcase(str(root)).encode('utf-8')).hexdigest()[:8]
    name = re.sub(r'[^A-Za-z0-9._-]', '-', root.name) or 'root'
    return f'{name}-{digest}'


def state_dir(area, root):
    """<state root>/<area>/<key>/, created with project.json naming the project it belongs to."""
    path = state_root() / area / project_key(root)
    if not (path / 'project.json').exists():
        write_json(path / 'project.json', {'root': str(root)})
    return path


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    """Write atomically: a reader sees the old file or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


@contextmanager
def lock(base):
    """Hold <base>/workflow.lock; break it when older than LOCK_STALE seconds."""
    path = base / 'workflow.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_TIMEOUT
    while True:
        try:
            path.mkdir()
            break
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            if age > LOCK_STALE:
                try:
                    path.rmdir()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise ValueError(f'Workflow is locked by {path}; retry shortly.')
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            path.rmdir()
        except FileNotFoundError:
            pass
