"""Path ledger: project root, tree walk and hashes, policy files, path specs, drift."""
import fnmatch
import hashlib
import json
import os
import sys
from pathlib import Path

from _engine import storage


AREA = 'untangle'  # state and exports: <state root>/untangle/<project key>/ (storage.py)
POLICY_FILES = ('references/defaults.md', 'references/contract.md', 'references/instructions.md')
POLICY_ENV = 'UNTANGLE_POLICY_ROOT'
# untangle and simple-by-design ship together in the handtools bundle: skills/untangle, skills/simple-by-design.
SIBLING = Path(__file__).resolve().parents[3] / 'simple-by-design'
LANG = {'.py': 'python', '.ts': 'typescript', '.tsx': 'typescript', '.mts': 'typescript', '.js': 'javascript',
        '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript', '.go': 'go', '.rs': 'rust',
        '.java': 'java', '.cs': 'csharp', '.c': 'c', '.h': 'c', '.cc': 'cpp', '.cpp': 'cpp', '.cxx': 'cpp',
        '.hpp': 'cpp', '.hh': 'cpp', '.sql': 'sql'}


def find_root():
    """Same root the CLI resolved: `--root`, else git top level, else cwd."""
    arg = None
    for i, a in enumerate(sys.argv):
        if a == '--root' and i + 1 < len(sys.argv):
            arg = sys.argv[i + 1]
        elif a.startswith('--root='):
            arg = a.split('=', 1)[1]
    return storage.project_root(arg)


def need(cond, msg):
    if not cond:
        raise ValueError(msg)


def need_text(obj, key, where):
    need(isinstance(obj.get(key), str) and obj[key].strip(), f'{where}: `{key}` must be non-empty text.')
    return obj[key]


def need_list(obj, key, where, required=True):
    value = obj.get(key, None if required else [])
    need(isinstance(value, list), f'{where}: `{key}` must be a list.')
    return value


def need_approval(payload, where):
    need(payload.get('approved_by_user') is True,
          f'{where}: needs the user\'s explicit approval: `"approved_by_user": true`.')


def file_sha(data):
    return hashlib.sha256(data).hexdigest()


def is_excluded(rel, rules):
    for rule in rules:
        g = rule['glob'].rstrip('/')
        if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(rel, g + '/**') or rel.startswith(g + '/'):
            return rule['reason']
    return None


def walk_tree(root, rules, limits):
    """Ledger of every discovered path: files get sha256, lines, language, and a disposition."""
    rules = [{'glob': '.git', 'reason': 'VCS metadata'}] + rules
    ledger, total = {}, 0
    for dirpath, dirs, files in os.walk(root):
        here = Path(dirpath)
        keep = []
        for d in sorted(dirs):
            full, rel = here / d, (here / d).relative_to(root).as_posix()
            reason = is_excluded(rel, rules)
            if full.resolve() == storage.state_root().resolve():
                continue  # engine state and exports: outside the source denominator
            if full.is_symlink():
                ledger[rel] = {'kind': 'symlink', 'target': os.readlink(full), 'disposition': 'excluded',
                               'reason': 'symlink, not traversed'}
            elif reason:
                ledger[rel] = {'kind': 'dir', 'disposition': 'excluded', 'reason': reason}
            elif (full / '.git').is_file():
                ledger[rel] = {'kind': 'dir', 'disposition': 'excluded', 'reason': 'submodule boundary'}
            else:
                keep.append(d)
        dirs[:] = keep
        for f in sorted(files):
            full, rel = here / f, (here / f).relative_to(root).as_posix()
            need(len(ledger) < limits['max_files'],
                  f'INVENTORY: more than max_files={limits["max_files"]} paths. Ask the user to raise it or '
                  'exclude more.')
            if full.is_symlink():
                ledger[rel] = {'kind': 'symlink', 'target': os.readlink(full), 'disposition': 'excluded',
                               'reason': 'symlink; review its target in place'}
                continue
            reason = is_excluded(rel, rules)
            data = full.read_bytes()
            total += len(data)
            need(total <= limits['max_bytes'],
                  f'INVENTORY: more than max_bytes={limits["max_bytes"]}. Ask the user to raise it or exclude '
                  'more.')
            entry = {'kind': 'file', 'sha256': file_sha(data), 'bytes': len(data),
                     'lines': data.count(b'\n') + (1 if data and not data.endswith(b'\n') else 0),
                     'lang': LANG.get(full.suffix.lower()), 'disposition': 'pending'}
            if reason or b'\0' in data[:8192]:
                entry.update(disposition='excluded', reason=reason or 'binary; review its maintained inputs')
            ledger[rel] = entry
    return ledger


def policy_root():
    """simple-by-design beside this skill, resolved on every command (never stored).

    UNTANGLE_POLICY_ROOT overrides it for the current command only.
    """
    override = os.environ.get(POLICY_ENV)
    return Path(override).expanduser().resolve() if override else SIBLING


def load_policy():
    """Hashes of the shared rule files; the bundle VERSION is recorded for information only."""
    base = policy_root()
    missing = [n for n in POLICY_FILES if not (base / n).is_file()]
    need(not missing and (base / 'languages').is_dir(),
          f'{base} is not simple-by-design (missing {", ".join(missing) or "languages/"}). Install the '
          f'handtools bundle so simple-by-design sits beside untangle, or set {POLICY_ENV} for this command.')
    names = list(POLICY_FILES) + sorted(p.relative_to(base).as_posix() for p in (base / 'languages').glob('*.md'))
    version = base.parent.parent / 'VERSION'
    return {'version': version.read_text().strip() if version.is_file() else None,
            'files': {n: file_sha((base / n).read_bytes()) for n in names}}


def parse_spec(state, spec, where):
    """'path' or 'path:a-b' -> (path, set of line numbers); a 0-line file is {0}."""
    need(isinstance(spec, str) and spec, f'{where}: path spec must be text.')
    path, _, rng = spec.partition(':')
    entry = state['ledger'].get(path)
    need(entry and entry['kind'] == 'file', f'{where}: `{path}` is not a file in the ledger.')
    n = entry['lines']
    if not rng:
        return path, set(range(1, n + 1)) or {0}
    a, _, b = rng.partition('-')
    try:
        a, b = int(a), int(b or a)
    except ValueError:
        raise ValueError(f'{where}: `{spec}`: range must be start-end.') from None
    need(1 <= a <= b <= n, f'{where}: `{spec}` is outside 1-{n}.')
    return path, set(range(a, b + 1))


def expand_specs(state, specs, skip=()):
    """Directory specs -> the in-scope files under them (minus `skip` rules); other specs unchanged."""
    if not isinstance(specs, list):
        return specs
    out = []
    for s in specs:
        entry = state['ledger'].get(s) if isinstance(s, str) else None
        if isinstance(s, str) and ':' not in s and not (entry and entry['kind'] == 'file'):
            pre = s.rstrip('/') + '/'
            files = sorted(f for f in in_scope_files(state) if f.startswith(pre) and not is_excluded(f, skip))
            out += files or [s]
        else:
            out.append(s)
    return out


def cover_lines(state, specs, where):
    """Per-path line sets; refuses overlap."""
    out = {}
    for spec in specs:
        path, lines = parse_spec(state, spec, where)
        need(not (out.get(path, set()) & lines), f'{where}: `{spec}` overlaps another range.')
        out.setdefault(path, set()).update(lines)
    return out


def unit_fingerprint(state, cover):
    return file_sha(json.dumps(sorted((p, state['ledger'][p]['sha256'], min(l), max(l), len(l))
                                  for p, l in cover.items())).encode())


def in_scope_files(state):
    return {p for p, e in state['ledger'].items() if e['kind'] == 'file' and e['disposition'] == 'pending'}


def find_drift(state):
    """Differences between the approved snapshot and the tree and policy now."""
    root = Path(state['root'])
    now = walk_tree(root, state['exclude'], {'max_files': 10 ** 9, 'max_bytes': 10 ** 15})
    approved = state.get('map', {}).get('exclusions', [])
    diffs = [f'new: {p}' for p in sorted(set(now) - set(state['ledger'])) if not is_excluded(p, approved)]
    diffs += [f'deleted: {p}' for p in sorted(set(state['ledger']) - set(now)) if not is_excluded(p, approved)]
    diffs += [f'changed: {p}' for p in sorted(in_scope_files(state) & set(now))
              if now[p].get('sha256') != state['ledger'][p]['sha256']]
    policy = load_policy()['files']
    gone = [n for n in state['policy']['files'] if n not in policy]
    need(not gone, f'Policy file(s) missing from {policy_root()}: {", ".join(gone)}. Reinstall the handtools bundle.')
    diffs += [f'policy changed: {n}' for n in state['policy']['files'] if policy.get(n) != state['policy']['files'][n]]
    return diffs
