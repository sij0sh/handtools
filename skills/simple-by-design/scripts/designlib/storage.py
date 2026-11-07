"""Paths under .agents/design, JSON file I/O, and the lock around writes."""
import json
import time
from contextlib import contextmanager
from pathlib import Path

DESIGN = Path('.agents/design')
RECORD = DESIGN / 'decisions.json'
STATE = DESIGN / 'workflow.json'
LOCK = DESIGN / 'workflow.lock'
LOCK_TIMEOUT = 5.0
LOCK_STALE = 30.0


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    """Write atomically: a reader sees the old file or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


@contextmanager
def lock(root):
    """Hold the lock directory; break it when older than LOCK_STALE seconds."""
    path = root / LOCK
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
