"""Warn when the ADR log (decisions.json) would not be committed.

Read-only: runs `git check-ignore` and `git ls-files`; never edits .gitignore.
No git, or a root outside a work tree, means nothing to warn about.
"""
import subprocess

from . import record

PATTERN = ('.agents/*\n'
           '!.agents/design/\n'
           '.agents/design/*\n'
           '!.agents/design/decisions.json')


def _git(root, *args):
    try:
        return subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True).returncode
    except OSError:
        return None


def warning(root):
    """Return a warning when decisions.json is ignored or untracked in git, else None."""
    if _git(root, 'rev-parse', '--is-inside-work-tree') != 0:
        return None
    path = record.RECORD.as_posix()
    if _git(root, 'ls-files', '--error-unmatch', path) == 0:
        return None
    if _git(root, 'check-ignore', '-q', '--no-index', path) == 0:
        problem = 'is ignored by git'
    else:
        problem = 'is not tracked by git yet'
    return (f'WARNING: {path} {problem}. It is the project\'s decision record (ADR log) and should be '
            f'committed. A .gitignore that keeps it while ignoring other agent files:\n{PATTERN}')
