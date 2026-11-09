"""Source roots: bounded tree walk, file hashes and freshness fingerprints. Reads files and runs
read-only git; never runs project code.

A root is the primary project ('.') or an explicitly supplied related repository (a label).
"""
import fnmatch
import hashlib
import os
import subprocess
from pathlib import Path

SKIP = {'.git', 'node_modules', '.venv', 'venv', 'vendor', 'target', 'dist', 'build', '__pycache__',
        '.terraform', '.mypy_cache', '.pytest_cache', '.ruff_cache'}
PRIMARY = '.'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(root, rel):
    """sha256 of root/rel, or None when the file is gone or escapes the root."""
    base = Path(root).resolve()
    path = (base / rel).resolve()
    if base not in path.parents or not path.is_file():
        return None
    return sha256(path.read_bytes())


def excluded(rel, rules):
    for g in rules:
        g = g.rstrip('/')
        if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(rel, g + '/**') or rel.startswith(g + '/'):
            return True
    return False


def walk(root, exclude=(), max_files=None, max_bytes=None):
    """Sorted relative file paths with sizes; stops at a limit and says so. Symlinks are not followed."""
    root = Path(root)
    files, total, truncated = [], 0, None
    for dirpath, dirs, names in os.walk(root):
        here = Path(dirpath)
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not (here / d).is_symlink()
                         and not excluded((here / d).relative_to(root).as_posix(), exclude))
        for name in sorted(names):
            full = here / name
            rel = full.relative_to(root).as_posix()
            if full.is_symlink() or excluded(rel, exclude):
                continue
            size = full.stat().st_size
            if max_files is not None and len(files) >= max_files:
                return files, f'max_files={max_files} reached'
            if max_bytes is not None and total + size > max_bytes:
                return files, f'max_bytes={max_bytes} reached'
            total += size
            files.append((rel, size))
    return files, truncated


def _git(root, *args):
    try:
        out = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=60,
                             stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def fingerprint(root, exclude=()):
    """Identity and content fingerprint of a root: git HEAD + dirty-file hashes when the root is a
    repository top level, else a hash over every file path and content hash."""
    root = Path(root).resolve()
    top = _git(root, 'rev-parse', '--show-toplevel')
    if top is not None and Path(top.decode().strip()).resolve() == root:
        head = (_git(root, 'rev-parse', 'HEAD') or b'').decode().strip() or None
        status = _git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all') or b''
        dirty, fields = [], iter(status.split(b'\0'))
        for entry in fields:
            if not entry:
                continue
            if entry[:1] in (b'R', b'C'):
                next(fields, None)  # -z puts a rename's original path in the following field
            rel = entry[3:].decode('utf-8', 'surrogateescape')
            if not excluded(rel, exclude):
                dirty.append((rel, file_hash(root, rel)))
        remote = (_git(root, 'config', '--get', 'remote.origin.url') or b'').decode().strip() or None
        digest = sha256(repr((head, sorted(dirty, key=str))).encode())
        return {'kind': 'git', 'head': head, 'remote': remote, 'dirty': len(dirty), 'fingerprint': digest}
    files, _ = walk(root, exclude)
    digest = sha256(repr([(rel, file_hash(root, rel)) for rel, _ in files]).encode())
    return {'kind': 'tree', 'files': len(files), 'fingerprint': digest}
