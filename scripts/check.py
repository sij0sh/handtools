#!/usr/bin/env python3
"""Report installed handtools copies that are behind origin. Read-only apart from `git fetch`.

Claude Code flags plugin updates itself; pi and Codex do not for a skills-only package, so this
script is their update flag. It finds git clones of handtools (the dev checkout this file is in,
pi's package clone, Codex's and Claude's marketplace clones), fetches each, and prints the command
that applies the update. It never pulls or reinstalls anything.

Python 3.9+; standard library only. Exit 0 when everything is current, 1 when an update is
available, 2 when a clone could not be checked.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

NAME = 'handtools'
HOME = Path.home()
# (label, directory to search, depth, how to apply an update)
PLACES = [
    ('pi', HOME / '.pi' / 'agent' / 'git', 3, 'pi update git:github.com/sij0sh/handtools'),
    ('codex', HOME / '.codex', 6, 'codex plugin marketplace upgrade'),
    ('claude', HOME / '.claude' / 'plugins', 3, 'claude: /plugin marketplace update handtools, then /plugin'),
]


def git(repo, *args):
    out = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True,
                         timeout=60, stdin=subprocess.DEVNULL)
    return out.stdout.strip() if out.returncode == 0 else None


def is_handtools(repo):
    url = git(repo, 'remote', 'get-url', 'origin') or ''
    return url.rstrip('/').removesuffix('.git').endswith('/' + NAME)


def find_clones(base, depth):
    """Git work trees under base, at most `depth` levels down, whose origin is handtools."""
    found = []
    if not base.is_dir():
        return found
    start = len(base.parts)
    for top, dirs, _files in os.walk(base):
        here = Path(top)
        if (here / '.git').exists():
            dirs[:] = []
            if is_handtools(here):
                found.append(here)
            continue
        if len(here.parts) - start >= depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', 'sessions', 'logs')]
    return found


def behind(repo):
    """Commits on the upstream (or origin's default branch) that the clone lacks; None if unknown."""
    if git(repo, 'fetch', '--quiet', 'origin') is None:
        return None
    upstream = git(repo, 'rev-parse', '--abbrev-ref', '@{u}') or git(repo, 'rev-parse', '--abbrev-ref', 'origin/HEAD')
    if not upstream:
        return None
    count = git(repo, 'rev-list', '--count', f'HEAD..{upstream}')
    return int(count) if count and count.isdigit() else None


def version(repo):
    path = repo / 'VERSION'
    return path.read_text(encoding='utf-8').strip() if path.is_file() else '?'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()
    dev = Path(__file__).resolve().parents[1]
    targets = [('checkout', dev, 'git pull --ff-only')] if (dev / '.git').exists() and is_handtools(dev) else []
    for label, base, depth, command in PLACES:
        targets += [(label, repo, command) for repo in find_clones(base, depth) if repo.resolve() != dev]
    if not targets:
        print('No handtools git clones found (none installed from git yet, or no origin remote).')
        return 0
    updates = errors = 0
    for label, repo, command in targets:
        n = behind(repo)
        if n is None:
            errors += 1
            print(f'{label}: {repo} ({version(repo)}): could not check (no origin or fetch failed)')
        elif n:
            updates += 1
            print(f'{label}: {repo} ({version(repo)}): update available, {n} commit(s) behind; run: {command}')
        else:
            print(f'{label}: {repo} ({version(repo)}): up to date')
    return 1 if updates else 2 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
