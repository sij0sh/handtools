# Graph tools

`map`, `find`, `show` and `inspect`'s relationships lane read a captured source
graph. `python3 "$S/remember.py" COMMAND --repo DIR` returns JSON by default,
except bare `map`: whole source up to 24 KB (`--whole`: 3,000 lines / 200 KB),
otherwise a directory summary. `--whole-repo-lines 0`, explicit
`--format json|table`, or `--fields` selects rows. No command executes project
code, installs dependencies or runs tests.

Bare `map` text adds a bounded recent-work primer: 3 sessions, 3 non-merge
commits, current session excluded, about 2 KB. Use `--no-primer`,
`--primer-depth N`, `--primer-bytes N`, `--primer-root DIR`, `--primer-merges`,
or `--exclude-session ID`. Other `map` forms include it only with `--primer`;
otherwise, and under `--snapshot` or a byte cap, `primer` names the omission.
`describe` lists commands and tables.

## Examples

```bash
python3 "$S/remember.py" map --kind symbol
python3 "$S/remember.py" find --regex 'retry|timeout' --path 'src/*' --not-path '*.d.ts' --count-by path
python3 "$S/remember.py" inspect src/store.py
python3 "$S/remember.py" inspect 'src/store.py::save' --intent review
python3 "$S/remember.py" show RETURNED_REF
python3 "$S/remember.py" query 'SELECT target, count(DISTINCT source) AS consumers FROM edges WHERE predicate = :kind GROUP BY target' --param kind=IMPORTS
```

Use `--snapshot ID` for an existing view. Otherwise each read captures current
source, reusing an unchanged capture's graph. Ambiguous names return candidates
instead of selecting one silently.

## inspect relationships

`--intent change` (default) runs file-grain impact: symbol targets widen to their
file (`scope.widened_targets`). Consumer rows carry `reach`: `direct` (one hop;
for a symbol target, a call into it, an import line or a mention naming it),
`file_only` (one hop, names only other parts of the file) or `indirect` (two or
more hops). Dependencies are `dependency_context`; tests are `verification`
suggestions (`execution: not_run`); `risk_profile` counts each. Mentions outside
reached files are `unresolved_mentions` gaps: lexical leads, not proven calls.
`--intent bug|review` walks both directions at the target's own grain.
Bounds: `--depth`, `--max-nodes`, `--seconds`; omitted frontiers stay in gaps.

## Evidence and scope

| Predicate | Meaning |
|---|---|
| `CONTAINS`, `DECLARES` | Inventory containment and syntactic definitions. |
| `IMPORTS` | Import destination under the named resolver rule. |
| `CALLS_STATIC` | A supported Python, TS/JS or Rust call or construction. |
| `TESTS` | Test-file (or Rust `#[cfg(test)]` item) import association, not verified assertion coverage. |
| `REFERENCES` | Manifest/CI literal path: package.json scripts, main/types/bin/exports/files; tsconfig extends/include/files/references; Cargo lib/bin/test/build/path deps/workspace members; CI workflow lines. Not an import; not traversed. |

A certain manifest path that matches no captured file is a `references` gap;
`map` prints `referenced but missing: PATH` when absent on disk, or `not captured
but used` when ignored. Script outputs and build-output folders are never
reported missing. Generated/vendored files (`dist`, `vendor`, `generated`
folders; `.min.js`, `_pb2.py`, `.pb.go`, `.generated.*`; `@generated`/`DO NOT
EDIT` headers; `.d.ts` of 1,000+ lines) are listed by `map`.

Traversal uses `IMPORTS` and `CALLS_STATIC`; tests never bridge unrelated
implementations. Each traversal row carries `via` and one shortest witness.
This is potential impact, not runtime reachability or proof of breakage.

Python calls cover unambiguous function/class names and imported bindings.
TS/JS and Rust follow supported re-exports and resolve methods when a receiver's
class/type is known in the same scope. TS/JS `new X()` and Python `Cls()` link
to the class. Rust follows `pub use` and constructors returning `Self`, including
supported Result/Option wrappers. Parameters without a known type, ambiguous
bindings, dynamic receivers, macros and trait dispatch remain unresolved.

Definition/import extraction: Python AST; optional tree-sitter for Rust, Go,
TS/JS and shell. Python import roots include the repository root, `src`, package
parent and importing directory; multiple matches are ambiguous. Rust walks module
files and Cargo package names; Go reads `go.mod` and package files. TS/JS resolves
relative specifiers, the nearest `tsconfig.json` `paths`/`baseUrl` (following
relative `extends`), then workspace `package.json` names through `exports`,
`main` or `types`, mapping `outDir` builds back to `rootDir` source. Other bare
specifiers are `not_in_repo`; unmapped `@/`, `~/` and `#` aliases stay
unresolved. Build features, bundler aliases, Rust `#[path]`, Go replacements and
installed packages are not modeled. Import gaps are one row per statement.
Responsibility, state lifetime and ownership are not inferred.

## Search

`find TEXT` is literal; `find --regex PATTERN` uses Python regex syntax.
`--word` and `--case-sensitive` apply to both. Repeat `--path` to include and
`--not-path` to exclude result paths: glob `*` crosses `/`, plain paths include
descendants. These filters do not change capture; `--exclude` does.
`--count-by path` counts matching rows after filtering; `--kind occurrence`
counts source lines alone.

## Snapshots and cache

Each workspace keeps one derived snapshot: source bytes, inventory, producer
versions, graph and gaps under a content-addressed ID. Every read captures the
tree and reuses the snapshot only when it matches; otherwise it rebuilds and the
new snapshot supersedes the old one. Workspace roots isolate caches, including
separate Git worktrees. Captures include untracked and dirty files and tracked
missing paths. Files changing during capture are marked unavailable. Refs to a
superseded, expired or corrupt snapshot return errors, never old or
current-source substitutes; rerun the original request. Workspaces idle 14 days
are deleted (swept at most daily on save; reads refresh age).

## Capture, limits and delivery

With Git, inventory uses tracked and nonignored untracked paths; without Git, it
walks the directory without following symlinks. Both exclude `.git`, `.hg`,
`.svn`, `__pycache__`, `node_modules`, `.venv`, `venv`, `.remember`,
`.pytest_cache`, `target`, `dist` and `build`. Add `--exclude GLOB` or root
`.rememberignore` globs (one per line, `#` comments, no negation).

Defaults: 20,000 files; 1 MiB/file; 32 MiB total. Non-UTF-8/binary files are hashed
but not parsed. Cache defaults to `$XDG_CACHE_HOME/remember`, else
`%LOCALAPPDATA%\remember` on Windows, else `~/.cache/remember`; `--cache DIR`
must be outside the source root. The snapshot contains source text, never
transcripts.

Delivery bounds: `--limit` (30 rows; query 200), `--offset`, `--max-bytes`
(12 KB). They never limit capture or traversal. `map`/`find` pages replay
against the pinned snapshot through `next`; `gaps` summarizes counts, and
`query 'SELECT * FROM gaps'` lists them. Source reads
support `--start-line` and `--lines`. Delivered rows omit `id`, `key`, `digest`
and default flags; `--verbose` returns full rows. `--fields` projects rows; an
unknown name exits 2. `--format table` prints columns plus status and
continuations.

Exit 0: completed, including explicitly partial evidence. `status: partial`:
inventory, capture, traversal or mention gaps, or a source/parser gap on a result
file (find: any unread in-scope file). Paging and byte caps only truncate
(`delivery.complete: false`, `results_truncated`). Exit 2: invalid input or
failure. No result certifies safety.
