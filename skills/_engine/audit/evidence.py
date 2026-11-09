"""Evidence references, path specs and source fingerprints for audits. Reads files and runs read-only
git; never runs project code.

An evidence ref is {"path", "statement", "lines"?, "revision"?} plus "sha256", which the recorder
adds. No revision means the working tree; a commit SHA means `git show <sha>:<path>`. Commit refs are
immutable, so drift checks rehash working-tree refs only. Same shape as recon evidence, without
`source` (audits read the primary root only).
"""
import re
import subprocess
from pathlib import Path, PurePosixPath

from _engine.recon import sources

MAX_STATEMENT = 500
MAX_REFS = 50
SHA = re.compile(r'^[0-9a-f]{40}$')


def need(cond, msg):
    if not cond:
        raise ValueError(msg)


def text(obj, key, where, limit=MAX_STATEMENT):
    value = obj.get(key) if isinstance(obj, dict) else None
    need(isinstance(value, str) and value.strip(), f'{where}: `{key}` must be non-empty text.')
    need(len(value) <= limit, f'{where}: `{key}` is longer than {limit} characters.')
    return value


def git(root, *args):
    """stdout of a read-only git command, or None."""
    try:
        out = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=60,
                             stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def safe_path(rel, where):
    need(isinstance(rel, str) and rel.strip(), f'{where}: `path` must be a relative path.')
    p = PurePosixPath(rel)
    need(not p.is_absolute() and '..' not in p.parts and '\\' not in rel,
         f'{where}: `{rel}` must be relative to the project root, without `..`.')
    return p.as_posix()


def content_hash(root, rel, revision=None):
    """sha256 of the working-tree file or of its content at `revision`; None when unreadable."""
    if revision is None:
        return sources.file_hash(root, rel)
    data = git(root, 'show', f'{revision}:{rel}')
    return None if data is None else sources.sha256(data)


def hash_refs(root, refs, where, required=True):
    """Validate evidence refs and add each one's sha256; refuse files that cannot be read."""
    need(isinstance(refs, list), f'{where}: `evidence` must be a list of refs.')
    need(refs or not required, f'{where}: cite at least one evidence ref.')
    need(len(refs) <= MAX_REFS, f'{where}: at most {MAX_REFS} evidence refs.')
    out = []
    for ref in refs:
        need(isinstance(ref, dict), f'{where}: each evidence ref is {{"path", "statement"}}.')
        rel = safe_path(ref.get('path'), where)
        text(ref, 'statement', where)
        revision = ref.get('revision')
        need(revision is None or (isinstance(revision, str) and SHA.match(revision)),
             f'{where}: `revision` is a full commit SHA, or absent for the working tree.')
        digest = content_hash(root, rel, revision)
        need(digest is not None, f'{where}: cannot read `{rel}`' + (f' at {revision}.' if revision else '.'))
        item = {'path': rel, 'statement': ref['statement'], 'sha256': digest}
        for key in ('lines', 'revision'):
            if ref.get(key):
                item[key] = str(ref[key])
        out.append(item)
    return out


def changed(root, refs):
    """Paths of working-tree refs whose content changed or vanished."""
    return sorted({r['path'] for r in refs if 'revision' not in r and sources.file_hash(root, r['path']) != r['sha256']})


def parse_spec(spec, where):
    """'path', 'dir/' or 'path:start-end' -> (path, (start, end) or None)."""
    need(isinstance(spec, str) and spec.strip(), f'{where}: a path spec is non-empty text.')
    m = re.match(r'^(.*?):(\d+)-(\d+)$', spec)
    if m:
        start, end = int(m.group(2)), int(m.group(3))
        need(1 <= start <= end, f'{where}: bad line range in `{spec}`.')
        return safe_path(m.group(1), where), (start, end)
    return safe_path(spec.rstrip('/') or '.', where), None


def expand(root, specs, where, max_files):
    """Files named by path specs (directories walked, symlinks skipped), sorted, at most max_files."""
    root = Path(root)
    out = set()
    for spec in specs:
        rel, _ = parse_spec(spec, where)
        full = root / rel
        need(full.exists(), f'{where}: `{rel}` does not exist.')
        if full.is_dir():
            files, truncated = sources.walk(full, max_files=max_files)
            need(not truncated, f'{where}: `{rel}` has more than {max_files} files; narrow the scope.')
            out.update((PurePosixPath(rel) / f).as_posix() if rel != '.' else f for f, _ in files)
        else:
            out.add(rel)
    need(len(out) <= max_files, f'{where}: scope has {len(out)} files; the limit is {max_files}.')
    return sorted(out)


MAX_EXCERPT = 2000
CWD_KINDS = ('worktree', 'tempdir')


def command_run(run, allowed, where):
    """A command the agent ran: approved, outside the target tree, with its revision and result."""
    need(isinstance(run, dict), f'{where}: a command run is an object.')
    cmd = text(run, 'command', where, limit=1000)
    need(cmd in allowed, f'{where}: `{cmd}` was not approved; approved commands: '
                         + (', '.join(allowed) or 'none (static analysis only)') + '.')
    need(run.get('cwd') in CWD_KINDS, f'{where}: commands run in an isolated `cwd`: worktree|tempdir, '
                                      'never the target checkout.')
    need(isinstance(run.get('revision'), str) and (SHA.match(run['revision']) or run['revision'] == 'worktree'),
         f'{where}: `revision` is the commit SHA checked out for the run, or "worktree" for a copy of it.')
    need(type(run.get('exit')) is int, f'{where}: `exit` is the integer exit status.')
    need(isinstance(run.get('output_sha256'), str) and re.match(r'^[0-9a-f]{64}$', run['output_sha256']),
         f'{where}: `output_sha256` is the sha256 of the full output.')
    excerpt = text(run, 'excerpt', where, limit=MAX_EXCERPT)
    out = {'command': cmd, 'cwd': run['cwd'], 'revision': run['revision'], 'exit': run['exit'],
           'output_sha256': run['output_sha256'], 'excerpt': excerpt}
    if run.get('env'):
        out['env'] = text(run, 'env', where)
    return out


def fingerprint(root, files):
    return {rel: sources.file_hash(root, rel) for rel in files}


def drift(root, prints):
    """Paths whose working-tree content differs from a fingerprint."""
    return sorted(rel for rel, digest in prints.items() if sources.file_hash(root, rel) != digest)
