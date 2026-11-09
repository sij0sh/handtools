"""Bounded, read-only collectors. They produce candidates for the agent to verify, never records.

orient: inventory of the files that usually reveal boundaries (manifests, entrypoints, config,
schemas, migrations, CI, infrastructure, decision sources) and the languages present.
candidates: a small pattern table for contract hints. Supported: Python, SQL, YAML, JSON and
schema files. Other languages are reported as unsupported scope, not as "no contracts".
"""
import fnmatch
import re
from pathlib import Path

from .sources import file_hash, walk

VERSION = 1
LIMITS = {'max_files': 5000, 'max_bytes': 50_000_000}
MAX_READ = 1_000_000  # bytes read per file by `candidates`

CATEGORIES = {
    'manifests': ['package.json', 'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements*.txt', 'go.mod',
                  'Cargo.toml', 'Gemfile', 'pom.xml', 'build.gradle', 'build.gradle.kts', 'composer.json',
                  'mix.exs', 'deno.json'],
    'entrypoints': ['**/__main__.py', '**/main.py', '**/app.py', '**/wsgi.py', '**/asgi.py', '**/manage.py',
                    'Procfile', '**/cmd/*/main.go', '**/src/main.rs', '**/index.js', '**/server.js', 'bin/*'],
    'config': ['*.toml', '*.ini', '*.cfg', '.env.example', '.env.sample', '**/config/*', '**/settings*.py'],
    'schemas': ['**/*.avsc', '**/*.proto', '**/*.graphql', '**/openapi*.y*ml', '**/openapi*.json',
                '**/swagger*.y*ml', '**/swagger*.json', '**/schemas/**', '**/*.schema.json'],
    'migrations': ['**/migrations/**', 'db/migrate/**', 'prisma/schema.prisma', 'alembic.ini', 'atlas.hcl',
                   'flyway.conf'],
    'ci': ['.github/workflows/*', '.gitlab-ci.yml', '.circleci/config.yml', 'azure-pipelines.yml', 'Jenkinsfile',
           '.buildkite/*'],
    'infrastructure': ['Dockerfile', '**/Dockerfile', 'compose.y*ml', 'docker-compose*.y*ml', '**/*.tf',
                       '**/k8s/**', '**/kubernetes/**', '**/helm/**', '**/deploy/**', 'crontab', '**/*.cron',
                       'serverless.y*ml', 'fly.toml', 'render.yaml', 'app.yaml'],
    'decisions': ['.agents/design/decisions.json', 'docs/adr/**', 'docs/decisions/**', 'ARCHITECTURE.md',
                  'docs/architecture*', 'AGENTS.md', 'CLAUDE.md', 'CONTRIBUTING*'],
}
LANG = {'.py': 'python', '.ts': 'typescript', '.tsx': 'typescript', '.js': 'javascript', '.mjs': 'javascript',
        '.go': 'go', '.rs': 'rust', '.java': 'java', '.kt': 'kotlin', '.cs': 'csharp', '.rb': 'ruby',
        '.php': 'php', '.ex': 'elixir', '.sql': 'sql', '.c': 'c', '.cc': 'cpp', '.cpp': 'cpp', '.swift': 'swift',
        '.scala': 'scala'}
SUPPORTED = {'python', 'sql'}
TEXT = {'.py', '.sql', '.yaml', '.yml', '.json', '.toml', '.cron', '.avsc', '.proto', '.graphql', ''}

_Q = r'''['"]'''
PATTERNS = [
    # (kind, direction hint, suffixes, regex, how the channel is built from the match)
    ('http', 'inbound', {'.py'}, re.compile(
        r'@\w+\.(route|get|post|put|patch|delete)\(\s*' + _Q + r'([^\'"]+)' + _Q + r'(?:[^)]*methods\s*=\s*\[([^\]]*)\])?'),
     lambda m: (m.group(3).replace("'", '').replace('"', '').split(',')[0].strip().upper() if m.group(3)
                else ('GET' if m.group(1) == 'route' else m.group(1).upper())) + ' ' + m.group(2)),
    ('http', 'outbound', {'.py', '.yaml', '.yml', '.json', '.toml'}, re.compile(_Q + r'(https?://[^\'"\s]+)' + _Q),
     lambda m: m.group(1)),
    ('queue', 'outbound', {'.py'}, re.compile(
        r'\.(?:send|publish|produce|send_message|basic_publish|publish_message)\(\s*(?:topic\s*=\s*)?' + _Q
        + r'([\w.\-/:]+)' + _Q), lambda m: m.group(1)),
    ('queue', 'inbound', {'.py'}, re.compile(
        r'\.(?:subscribe|consume|basic_consume|receive_messages)\(\s*\[?\s*(?:topics?\s*=\s*\[?\s*)?' + _Q
        + r'([\w.\-/:]+)' + _Q), lambda m: m.group(1)),
    ('schedule', 'inbound', {'.yaml', '.yml', '.json', '.toml'}, re.compile(
        r'\bschedule\s*[:=]\s*' + _Q + r'?([^\'"\n#]+?)' + _Q + r'?\s*(?:#.*)?$', re.M), lambda m: m.group(1).strip()),
    ('schedule', 'inbound', {'.cron', ''}, re.compile(r'^\s*((?:[\d*/,\-]+\s+){4}[\d*/,\-]+)\s+\S', re.M),
     lambda m: m.group(1)),
    ('schema', 'both', {'.py', '.yaml', '.yml', '.json', '.toml'}, re.compile(
        _Q + r'([\w./\-]+\.(?:avsc|proto|graphql|schema\.json|v\d+\.json))' + _Q), lambda m: m.group(1)),
    ('table', 'internal', {'.sql', '.py'}, re.compile(
        r'\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?([\w.]+)', re.I), lambda m: m.group(1).lower()),
]


def _match(rel, patterns):
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch('/' + rel, '*/' + p.lstrip('*/'))
               for p in patterns)


def _roots(roots):
    """{label: path}; the primary root is '.'."""
    return {label: Path(path).resolve() for label, path in roots.items()}


def orient(roots, exclude=(), limits=None):
    limits = dict(LIMITS, **(limits or {}))
    out, gaps = {}, []
    for label, root in _roots(roots).items():
        files, truncated = walk(root, exclude, limits['max_files'], limits['max_bytes'])
        cats = {c: [rel for rel, _ in files if _match(rel, pats)] for c, pats in CATEGORIES.items()}
        langs = {}
        for rel, _ in files:
            lang = LANG.get(Path(rel).suffix.lower())
            if lang:
                langs[lang] = langs.get(lang, 0) + 1
        out[label] = {'root': str(root), 'files': len(files), 'bytes': sum(s for _, s in files),
                      'categories': {c: v for c, v in cats.items() if v}, 'languages': langs}
        if truncated:
            gaps.append({'root': label, 'gap': f'orient stopped: {truncated}', 'next_lookup': 'raise the limit or '
                         'exclude generated/vendored paths'})
    return {'collector': 'orient', 'version': VERSION, 'roots': out, 'gaps': gaps}


def candidates(roots, exclude=(), limits=None):
    limits = dict(LIMITS, **(limits or {}))
    found, gaps, unsupported = [], [], {}
    for label, root in _roots(roots).items():
        files, truncated = walk(root, exclude, limits['max_files'], limits['max_bytes'])
        if truncated:
            gaps.append({'root': label, 'gap': f'candidates stopped: {truncated}'})
        for rel, size in files:
            suffix = Path(rel).suffix.lower()
            lang = LANG.get(suffix)
            if lang and lang not in SUPPORTED:
                unsupported.setdefault(lang, []).append(f'{label}:{rel}')
                continue
            if suffix not in TEXT:
                continue
            if size > MAX_READ:
                gaps.append({'root': label, 'gap': f'{rel} larger than {MAX_READ} bytes; not scanned'})
                continue
            text = (root / rel).read_text(encoding='utf-8', errors='replace')
            if '\0' in text[:8192]:
                continue
            sha = file_hash(root, rel)
            if rel.endswith(('.avsc', '.proto', '.graphql')) or (suffix == '.json' and '"$schema"' in text):
                found.append({'kind': 'schema', 'direction': 'both', 'channel': Path(rel).name, 'source': label,
                              'path': rel, 'line': 1, 'sha256': sha, 'match': 'schema file'})
            for kind, direction, suffixes, rx, channel in PATTERNS:
                if suffix not in suffixes:
                    continue
                for m in rx.finditer(text):
                    line = text[text.rfind('\n', 0, m.start()) + 1:text.find('\n', m.end()) % (len(text) + 1)]
                    if kind == 'http' and '$schema' in line:
                        continue  # a JSON Schema meta-schema URI, not a network call
                    found.append({'kind': kind, 'direction': direction, 'channel': channel(m), 'source': label,
                                  'path': rel, 'line': text.count('\n', 0, m.start()) + 1, 'sha256': sha,
                                  'match': m.group(0).strip()[:200]})
    for lang, paths in sorted(unsupported.items()):
        gaps.append({'gap': f'no contract patterns for {lang}; {len(paths)} file(s) not scanned',
                     'examples': paths[:5], 'next_lookup': 'trace these files by hand during map'})
    return {'collector': 'candidates', 'version': VERSION, 'candidates': found, 'gaps': gaps,
            'note': 'Candidates are hints. Verify each in the source and cite it before recording a contract.'}
