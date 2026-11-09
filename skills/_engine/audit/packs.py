"""Check packs: named, versioned check sets (packs/*.json), their applicability, and the languages
an audit cannot cover. A check says when it applies, what evidence it needs, what would falsify a
claim, how to validate within limits. Workflows choose packs; obligations name one check each.
"""
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent / 'packs'
ANY = '*'
MODES = ('diff', 'subsystem', 'bug')
# Kinds of system boundary an obligation targets; where they overlap they match recon contract kinds.
BOUNDARIES = ('http', 'queue', 'schedule', 'db', 'file', 'subprocess', 'config', 'cli', 'library', 'test')
LANG = {'.py': 'python', '.ts': 'typescript', '.tsx': 'typescript', '.mts': 'typescript', '.js': 'javascript',
        '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript', '.go': 'go', '.rs': 'rust',
        '.java': 'java', '.cs': 'csharp', '.c': 'c', '.h': 'c', '.cc': 'cpp', '.cpp': 'cpp', '.cxx': 'cpp',
        '.hpp': 'cpp', '.hh': 'cpp', '.sql': 'sql', '.rb': 'ruby', '.php': 'php', '.kt': 'kotlin',
        '.swift': 'swift', '.scala': 'scala'}
FIELDS = ('id', 'title', 'applies', 'evidence_required', 'falsifiers', 'validation_methods', 'limits')


def need(cond, msg):
    if not cond:
        raise ValueError(msg)


def validate(pack, name):
    need(isinstance(pack, dict) and pack.get('pack') == name, f'pack {name}: `pack` must be "{name}".')
    need(isinstance(pack.get('version'), int) and pack['version'] >= 1, f'pack {name}: `version` >= 1.')
    need(isinstance(pack.get('checks'), list) and pack['checks'], f'pack {name}: list its checks.')
    for c in pack['checks']:
        need(isinstance(c, dict) and all(k in c for k in FIELDS), f'pack {name}: each check has {", ".join(FIELDS)}.')
        need(c['id'].startswith(name + '/'), f'pack {name}: check id {c["id"]} must start with "{name}/".')
        a = c['applies']
        need(isinstance(a, dict) and set(a) == {'languages', 'boundaries', 'modes'},
             f'{c["id"]}: applies has languages, boundaries, modes.')
        need(all(x == ANY or x in BOUNDARIES for x in a['boundaries']), f'{c["id"]}: unknown boundary.')
        need(all(x == ANY or x in MODES for x in a['modes']), f'{c["id"]}: unknown mode.')
        for key in ('evidence_required', 'falsifiers', 'validation_methods'):
            need(isinstance(c[key], list) and c[key], f'{c["id"]}: `{key}` lists at least one item.')
    return pack


def load(names):
    """{check id: check} for the named packs, each tagged with its pack and version."""
    out = {}
    for name in names:
        path = DIR / f'{name}.json'
        need(path.is_file(), f'unknown check pack {name}.')
        pack = validate(json.loads(path.read_text(encoding='utf-8')), name)
        for c in pack['checks']:
            need(c['id'] not in out, f'duplicate check {c["id"]}.')
            out[c['id']] = dict(c, pack=name, version=pack['version'])
    return out


def available():
    return sorted(p.stem for p in DIR.glob('*.json'))


def language(path):
    return LANG.get(Path(path).suffix.lower())


def applies(check, lang, boundary, mode):
    a = check['applies']
    def ok(values, value):
        return ANY in values or value in values
    # Language-specific checks need a file of that language; language-neutral ones (*) apply anywhere.
    return ok(a['languages'], lang) and ok(a['boundaries'], boundary) and ok(a['modes'], mode)


def unsupported(files, catalog):
    """Languages present in `files` that no loaded check covers specifically: a coverage gap to report."""
    covered = {lang for c in catalog.values() for lang in c['applies']['languages'] if lang != ANY}
    return sorted({language(f) for f in files} - covered - {None})
