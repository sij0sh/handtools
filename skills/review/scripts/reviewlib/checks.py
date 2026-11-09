"""FRAME and scope: mode, git baseline, in-scope files and their fingerprints, approved commands,
budgets, and source drift since FRAME. Reads files and runs read-only git; never runs project code."""
from pathlib import Path

from _engine.audit import budgets, evidence, packs

BUDGETS = ('hunt_transitions', 'validate_transitions', 'attempts_per_candidate', 'variant_obligations',
           'challenge_rounds', 'max_obligations')
PACKS = ('general', 'tests', 'python')
MAX_SCOPE_FILES = 2000
HUNT_BATCH = 5
VALIDATE_BATCH = 3
need, text = evidence.need, evidence.text


def is_git(root):
    top = evidence.git(root, 'rev-parse', '--show-toplevel')
    return top is not None and Path(top.decode().strip()).resolve() == Path(root).resolve()


def rev(root, ref, where):
    out = evidence.git(root, 'rev-parse', '--verify', '--quiet', f'{ref}^{{commit}}')
    need(out, f'{where}: `{ref}` is not a commit in this repository.')
    return out.decode().strip()


def _lines(data):
    return [x for x in (data or b'').decode('utf-8', 'surrogateescape').splitlines() if x]


def _diff(root, d, where):
    """Resolve base/head; head is the checked-out HEAD or "worktree" (uncommitted changes included)."""
    need(is_git(root), f'{where}: diff mode needs the project root to be a git repository top level.')
    need(isinstance(d, dict), f'{where}: diff mode needs `diff` {{"base": ref, "head": "HEAD"|"worktree"}}.')
    base = rev(root, text(d, 'base', where), where)
    head_ref = text(d, 'head', where)
    current = rev(root, 'HEAD', where)
    head = 'worktree' if head_ref == 'worktree' else rev(root, head_ref, where)
    need(head in ('worktree', current), f'{where}: head `{head_ref}` is not checked out. Check it out (or review '
                                        'from a worktree of it) so evidence reads the reviewed code.')
    merge_base = (evidence.git(root, 'merge-base', base, current) or b'').decode().strip()
    need(merge_base, f'{where}: `{d["base"]}` and HEAD share no history.')
    args = ['diff', '--name-only', '--no-renames', merge_base] + ([] if head == 'worktree' else [head])
    changed = _lines(evidence.git(root, *args))
    need(changed, f'{where}: no changes between {d["base"]} and {head_ref}.')
    present = [p for p in changed if (Path(root) / p).is_file()]
    return {'base': base, 'base_ref': d['base'], 'head': head, 'head_ref': head_ref, 'merge_base': merge_base,
            'changed': present, 'deleted': sorted(set(changed) - set(present))}


def _bug(b, where):
    need(isinstance(b, dict), f'{where}: bug mode needs `bug` {{"symptom", "expected", "reproduction", "version"}}.')
    out = {k: text(b, k, f'{where} bug') for k in ('symptom', 'expected', 'reproduction')}
    out['version'] = text(b, 'version', f'{where} bug') if b.get('version') else 'unknown'
    return out


def commands(items, where):
    """Approved commands: exact command text, purpose and declared side effects."""
    need(isinstance(items, list), f'{where}: `allowed_commands` is a list (empty = static analysis only).')
    out = []
    for c in items:
        need(isinstance(c, dict), f'{where}: each allowed command is {{"command", "purpose", "side_effects"}}.')
        out.append({k: text(c, k, where, limit=1000) for k in ('command', 'purpose', 'side_effects')})
    return out


def allowed(state):
    return [c['command'] for c in state['frame']['allowed_commands']]


def frame(root, payload):
    w = 'FRAME'
    need(payload.get('approved_by_user') is True, f'{w}: needs the user\'s explicit approval: `"approved_by_user": true`.')
    mode = payload.get('mode')
    need(mode in packs.MODES, f'{w}: `mode` is one of {", ".join(packs.MODES)}.')
    out = {'mode': mode, 'expected': text(payload, 'expected', w),
           'allowed_commands': commands(payload.get('allowed_commands', []), w), 'packs': list(PACKS)}
    specs = payload.get('scope', [])
    need(isinstance(specs, list), f'{w}: `scope` is a list of path specs.')
    files = []
    if mode == 'diff':
        out['diff'] = _diff(root, payload.get('diff'), w)
        files = out['diff']['changed']
    else:
        need(specs, f'{w}: {mode} mode needs `scope` (the paths to review).')
        if mode == 'bug':
            out['bug'] = _bug(payload.get('bug'), w)
    files = sorted(set(files) | set(evidence.expand(root, specs, w, MAX_SCOPE_FILES)))
    need(files, f'{w}: the scope has no files.')
    need(len(files) <= MAX_SCOPE_FILES, f'{w}: {len(files)} files exceed {MAX_SCOPE_FILES}; narrow the scope.')
    out['scope'] = specs
    out['files'] = evidence.fingerprint(root, files)
    out['unsupported'] = packs.unsupported(files, packs.load(PACKS))
    limits = budgets.approve(payload.get('budgets'), BUDGETS, w)
    return out, limits


def extend_scope(state, root, specs, where):
    files = evidence.expand(root, specs, where, MAX_SCOPE_FILES)
    f = state['frame']
    f['scope'] = f['scope'] + [s for s in specs if s not in f['scope']]
    for rel, digest in evidence.fingerprint(root, files).items():
        f['files'].setdefault(rel, digest)
    need(len(f['files']) <= MAX_SCOPE_FILES, f'{where}: scope exceeds {MAX_SCOPE_FILES} files.')
    f['unsupported'] = packs.unsupported(f['files'], packs.load(f['packs']))


def cited(state):
    """{item id: (working-tree evidence refs, cited paths)} for obligations, candidates and test gaps.
    An obligation also cites its target file."""
    out = {}
    for o in state.get('obligations', {}).values():
        target = o['target'].split(':')[0]
        extra = {target} if target in state['frame']['files'] else set()
        out[o['id']] = (o['evidence'], extra)
    for c in state.get('candidates', {}).values():
        out[c['id']] = (list(c['sources']) + list((c.get('verdict') or {}).get('refs', [])), set())
    for t in state.get('test_gaps', {}).values():
        out[t['id']] = (t['evidence'], set())
    return {k: ([r for r in refs if 'revision' not in r], extra | {r['path'] for r in refs if 'revision' not in r})
            for k, (refs, extra) in out.items()}


def drift(state, root):
    """Paths changed since FRAME (in scope or cited), plus 'HEAD' when the reviewed commit moved."""
    changed = set(evidence.drift(root, state['frame']['files']))
    for refs, _ in cited(state).values():
        changed.update(evidence.changed(root, refs))
    d = state['frame'].get('diff')
    if d and d['head'] != 'worktree' and (evidence.git(root, 'rev-parse', 'HEAD') or b'').decode().strip() != d['head']:
        changed.add('HEAD')
    return sorted(changed)
