#!/usr/bin/env python3
"""Read-only project foundation scan. Prints JSON: repo facts and file evidence per baseline capability.

Never executes project code. Python 3.9+; standard library only.
"""
import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

SKIP = {'.git', 'node_modules', '.venv', 'venv', 'vendor', 'target', 'dist', 'build', '__pycache__', '.terraform'}
MANIFESTS = {
    'package.json': 'node', 'pyproject.toml': 'python', 'requirements.txt': 'python', 'go.mod': 'go',
    'Cargo.toml': 'rust', 'Gemfile': 'ruby', 'pom.xml': 'java', 'build.gradle': 'java', 'build.gradle.kts': 'java',
    'composer.json': 'php', 'mix.exs': 'elixir', 'deno.json': 'deno',
}
# capability id -> glob patterns that count as evidence
EVIDENCE = {
    'runtime-versions': ['mise.toml', '.mise.toml', '.tool-versions', '.nvmrc', '.node-version', '.python-version',
                         'rust-toolchain.toml', 'flake.nix', '.devcontainer/devcontainer.json'],
    'lockfiles': ['package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'bun.lockb', 'uv.lock', 'poetry.lock',
                  'Pipfile.lock', 'go.sum', 'Cargo.lock', 'Gemfile.lock', 'composer.lock', 'mise.lock'],
    'one-command-setup': ['mise.toml', 'Makefile', 'justfile', 'Taskfile.yml', 'compose.yaml', 'compose.yml',
                          'docker-compose.yml', 'docker-compose.yaml', '.devcontainer/devcontainer.json'],
    'tests-lint': ['tests', 'test', '__tests__', 'spec', '.eslintrc*', 'eslint.config.*', 'ruff.toml', '.golangci.*',
                   'biome.json', '.pre-commit-config.yaml', 'pytest.ini', 'vitest.config.*', 'jest.config.*'],
    'ci-checks': ['.github/workflows/*.y*ml', '.gitlab-ci.yml', '.circleci/config.yml', 'azure-pipelines.yml',
                  'Jenkinsfile', '.buildkite/*'],
    'dependency-updates': ['renovate.json', 'renovate.json5', '.renovaterc*', '.github/renovate.json*',
                           '.github/dependabot.yml'],
    'architecture-doc': ['docs/architecture*', 'ARCHITECTURE.md', 'docs/**/*.mmd', '**/*.dsl', '**/*.puml'],
    'adrs': ['.agents/design/decisions.json'],
    'db-migrations': ['**/migrations/*', 'prisma/schema.prisma', 'atlas.hcl', 'flyway.conf', 'alembic.ini',
                      'db/migrate/*'],
    'secrets-excluded': ['.gitignore', '.env.example', '.env.sample', '.sops.yaml', '.gitleaks.toml'],
    'deployment-doc': ['docs/deploy*', 'DEPLOY*.md', '.github/workflows/deploy*', 'Procfile', 'fly.toml',
                       'render.yaml', 'vercel.json', 'app.yaml', 'Dockerfile'],
    'logging-health': [],
    'declarative-infra': ['**/*.tf', '**/*.tofu', 'Pulumi.yaml', 'cdk.json', '**/Chart.yaml', '**/kustomization.yaml'],
}
LEGACY_ADRS = ['docs/adr/*', 'docs/decisions/*', 'adr/*', 'doc/adr/*']
ADR_LOG = '.agents/design/decisions.json'
LIMIT = 10
ENV_OK = ('.env.example', '.env.sample', '.env.template', '.envrc')


def git(root, *args):
    try:
        out = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(root), *args], capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def walk(root):
    """Relative posix paths of files and dirs, pruning SKIP dirs before descending."""
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        rel = Path(dirpath).relative_to(root)
        paths += [(rel / n).as_posix() for n in dirnames + filenames]
    return paths


def matches(paths, pattern):
    """Paths matching a glob; `**/x` also matches `x` at the root."""
    pats = [pattern, pattern[3:]] if pattern.startswith('**/') else [pattern]
    return [p for p in paths if any(fnmatch.fnmatch(p, q) for q in pats)][:LIMIT]


def adr_log(root, paths):
    """The ADR log (simple-by-design's decisions.json) and any legacy Markdown ADRs."""
    path = root / ADR_LOG
    info = {'path': ADR_LOG, 'exists': path.is_file(), 'resolved': 0, 'committed': None, 'ignored': None,
            'legacy_markdown': sorted({f for p in LEGACY_ADRS for f in matches(paths, p)})[:LIMIT]}
    if info['exists']:
        try:
            goals = json.loads(path.read_text(encoding='utf-8')).get('goals', [])
            info['resolved'] = sum(1 for g in goals for d in g.get('decisions', []) if d.get('status') == 'resolved')
        except (OSError, ValueError, AttributeError):
            info['resolved'] = None
    if git(root, 'rev-parse', '--git-dir') is not None:
        info['committed'] = git(root, 'ls-files', '--error-unmatch', ADR_LOG) is not None
        info['ignored'] = git(root, 'check-ignore', '--no-index', ADR_LOG) is not None
    return info


def tracked_env_files(root):
    listing = git(root, 'ls-files')
    if not listing:
        return []
    return [f for f in listing.splitlines()
            if Path(f).name.startswith('.env') and Path(f).name not in ENV_OK]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.', help='project root')
    root = Path(parser.parse_args().root).resolve()
    if not root.is_dir():
        print(json.dumps({'error': f'not a directory: {root}'}))
        return 1
    commits = git(root, 'rev-list', '--count', 'HEAD')
    paths = walk(root)
    stacks = sorted({lang for name, lang in MANIFESTS.items() if matches(paths, f'**/{name}')})
    evidence = {cap: sorted({f for p in pats for f in matches(paths, p)})[:LIMIT] for cap, pats in EVIDENCE.items()}
    source_files = sum(1 for p in paths if (root / p).is_file())
    report = {
        'root': str(root),
        'git': {'repo': git(root, 'rev-parse', '--git-dir') is not None,
                'commits': int(commits) if commits and commits.isdigit() else 0,
                'dirty': bool(git(root, 'status', '--porcelain'))},
        'files': source_files,
        'stacks': stacks,
        'decisions_record': (root / '.agents/foundation.json').is_file(),
        'adr_log': adr_log(root, paths),
        'evidence': evidence,
        'warnings': [f'tracked env file: {f}' for f in tracked_env_files(root)],
        'note': 'Evidence is file presence only; read the files to judge present vs partial. '
                'logging-health has no file signal; inspect source. ADRs live in adr_log.path; '
                'adr_log.legacy_markdown ADRs count as present but legacy.',
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
