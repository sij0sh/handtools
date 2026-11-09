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
        path.mkdir(parents=True, exist_ok=True)
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
            (path / 'owner').write_text(str(os.getpid()))
            break
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            alive = False
            try:
                pid = int((path / 'owner').read_text())
                os.kill(pid, 0)
                alive = True
            except PermissionError:
                alive = True
            except (OSError, ValueError):
                pass
            if age > LOCK_STALE and not alive:
                try:
                    (path / 'owner').unlink(missing_ok=True)
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
            (path / 'owner').unlink(missing_ok=True)
            path.rmdir()
        except FileNotFoundError:
            pass


# State documents are logical stream names, not independently maintained files.
def journal(base):
    from .events import Journal
    return Journal(Path(base) / 'events.sqlite3')


def has_state(path):
    path = Path(path)
    history = journal(path.parent).history(path.name)
    return journal(path.parent).read(path.name) is not None if history else path.exists()


def read_state(path):
    path = Path(path)
    history = journal(path.parent).history(path.name)
    if history:
        from .events import replay
        value = replay(history)[0]
        if value is None:
            raise ValueError('No workflow in progress. Run `start`.')
        return value
    # Read-only legacy fallback; the next accepted mutation writes one imported baseline.
    return read_json(path)


def write_state(path, data):
    path = Path(path)
    store = journal(path.parent)
    if not store.history(path.name) and path.exists():
        store.put(path.name, read_json(path))
    store.put(path.name, data)
    # Keep legacy input as a migration backup, never as a second active authority.
    if path.exists():
        path.rename(path.with_suffix(path.suffix + '.migrated'))


def delete_state(path):
    path = Path(path)
    journal(path.parent).append(path.name, 'state.deleted', {})
    if path.exists():
        path.rename(path.with_suffix(path.suffix + '.migrated'))
