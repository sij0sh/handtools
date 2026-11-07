#!/usr/bin/env python3
"""Read-only checks on changed foundation files. Prints JSON {checks, failed}; exits 1 when any check fails.

Checks only files changed vs HEAD plus untracked files, so pre-existing problems do not mask new ones.
Parses config syntax and checks for committed secrets. Never executes project code.
Python 3.9+; TOML needs 3.11+ (else skipped); YAML needs PyYAML (else skipped).
"""
import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

ENV_OK = ('.env.example', '.env.sample', '.env.template', '.envrc')
JSONC = ('tsconfig*.json', 'jsconfig*.json', '.vscode/*', 'devcontainer.json', '.devcontainer/*')


def git(root, *args):
    out = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root), *args],
                         capture_output=True, text=True, timeout=30)
    return out.stdout.splitlines() if out.returncode == 0 else []


def parse_json(text):
    json.loads(text)


def parse_toml(text):
    import tomllib
    tomllib.loads(text)


def parse_yaml(text):
    import yaml
    list(yaml.safe_load_all(text))


PARSERS = [
    (('*.json',), parse_json, 'json'),
    (('*.toml',), parse_toml, 'tomllib (Python 3.11+)'),
    (('*.yml', '*.yaml'), parse_yaml, 'PyYAML'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.', help='project root')
    root = Path(parser.parse_args().root).resolve()
    checks = []

    def record(name, status, detail=''):
        checks.append({'name': name, 'status': status, 'detail': detail})

    try:
        changed = sorted(set(git(root, 'diff', '--name-only', 'HEAD') or git(root, 'diff', '--name-only', '--cached'))
                         | set(git(root, 'ls-files', '--others', '--exclude-standard')))
        tracked = git(root, 'ls-files')
    except (OSError, subprocess.TimeoutExpired):
        changed, tracked = [], []
        record('git', 'skipped', 'git unavailable')

    for name in changed:
        path = root / name
        if not path.is_file() or any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(path.name, p) for p in JSONC):
            continue
        for patterns, parse, need in PARSERS:
            if not any(fnmatch.fnmatch(path.name, p) for p in patterns):
                continue
            try:
                parse(path.read_text(encoding='utf-8'))
                record(name, 'pass')
            except ImportError:
                record(name, 'skipped', f'needs {need}')
            except Exception as error:  # any read or parse error is a failure to report
                record(name, 'fail', (str(error).splitlines() or [''])[0][:200])
        if fnmatch.fnmatch(name, 'docs/adr/*.md') or fnmatch.fnmatch(name, 'docs/decisions/*.md'):
            try:
                ok = any(line.startswith('# ') for line in path.read_text(encoding='utf-8').splitlines()[:20])
            except (OSError, UnicodeDecodeError):
                ok = False
            record(f'{name} has a title', 'pass' if ok else 'fail')

    envs = [f for f in tracked + changed if Path(f).name.startswith('.env') and Path(f).name not in ENV_OK]
    record('no committed .env files', 'fail' if envs else 'pass', ', '.join(sorted(set(envs))))

    failed = [c['name'] for c in checks if c['status'] == 'fail']
    print(json.dumps({'changed': changed, 'checks': checks, 'failed': failed}, indent=2))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
