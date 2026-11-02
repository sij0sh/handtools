# Graph

`map`, `find`, `show` and `inspect`'s relationships lane read one captured source graph.
Bare `map` prints text: whole source up to 24 KB (`--whole`: 3,000 lines / 200 KB),
otherwise a directory summary. `--whole-repo-lines 0`, `--format json|table` or
`--fields` switches to rows. Nothing executes project code, installs packages or runs
tests.

Bare map text includes an orientation packet (about 2 KB): per-view states, best lead
per view (shared with `investigate`), 3 non-merge commits and tree state; the current
session is excluded. Other map forms include it only with `--primer`; when a snapshot,
byte cap or non-primer form omits it, `primer` says why.

`inspect --intent change` runs file-grain impact; a symbol target widens to its file
(`scope.widened_targets`). Consumers carry `reach`: `direct` (one hop, including a call,
import line or mention naming a symbol), `file_only` (one hop but naming another part of
the file) or `indirect` (2+ hops). Dependencies are `dependency_context`; tests are
`verification` suggestions (`execution: not_run`); `risk_profile` counts each. Mentions
outside reached files are `unresolved_mentions` gaps: lexical leads, not proven calls.
`bug` and `review` walk both directions at the target's grain. `--depth`, `--max-nodes`
and `--seconds` bound traversal; omitted frontier stays in gaps.

| Predicate | Meaning |
|---|---|
| `CONTAINS`, `DECLARES` | Inventory containment and syntactic definitions. |
| `IMPORTS` | Import destination under a named resolver rule. |
| `CALLS_STATIC` | A supported Python, TS/JS or Rust call or construction. |
| `TESTS` | Test-file (or Rust `#[cfg(test)]`) import association, not assertion coverage. |
| `REFERENCES` | Manifest/CI literal path (package.json, tsconfig, Cargo, workflows). Not an import; not traversed. |

Traversal uses `IMPORTS` and `CALLS_STATIC`; tests never bridge unrelated code. Each row
carries `via` and one shortest witness. This is potential impact, not runtime reachability
or proof of breakage. Python covers unambiguous function/class names and imported
bindings; TS/JS and Rust follow supported re-exports and resolve methods when the
receiver type is known in scope. Unknown parameter types, ambiguous bindings, dynamic
receivers, macros and trait dispatch stay unresolved. An unresolved import is a gap, not
an absent dependency.

A certain manifest path with no captured file is a `references` gap; `map` prints
`referenced but missing` (absent on disk) or `not captured but used` (ignored). Script
outputs and build-output folders are never reported missing. Generated/vendored files
(`dist`, `vendor`, `generated`; `.min.js`, `_pb2.py`, `.pb.go`, `.generated.*`;
`@generated`/`DO NOT EDIT`; `.d.ts` of 1,000+ lines) are listed.

## Capture and cache

Each workspace keeps one derived snapshot: source bytes, inventory, producer versions,
graph and gaps under a content-addressed ID. Every read captures the tree and reuses the
snapshot only when bytes and producer match; otherwise it rebuilds and supersedes the old
one. A superseded, expired, corrupt or older-schema snapshot ref fails; rerun the request.
Workspaces, including separate worktrees, isolate caches. Idle workspaces are deleted
after 14 days (swept at most daily on save; reads refresh age).

With Git, inventory is tracked plus nonignored untracked paths; without Git, a directory
walk that does not follow symlinks. Both skip `.git`, `.hg`, `.svn`, `__pycache__`,
`node_modules`, `.venv`, `venv`, `.remember`, `.pytest_cache`, `target`, `dist` and
`build`. Add `--exclude GLOB` or root `.rememberignore` globs (one per line, `#`
comments, no negation). Defaults: 20,000 files, 1 MiB/file, 32 MiB total; binary or
non-UTF-8 files are hashed but not parsed. The cache defaults to
`$XDG_CACHE_HOME/remember`, else `%LOCALAPPDATA%\remember`, else `~/.cache/remember`, and
must be outside the source root.

## find

`find TEXT` is literal; `find --regex PATTERN` uses Python regex. `--word` and
`--case-sensitive` apply to both. `--path` includes and `--not-path` excludes result
paths: glob `*` crosses `/`, and a plain path includes descendants. These filters do not
change capture. `--count-by path` counts after filtering; `--kind occurrence` counts
source lines only.

## Delivery

`--limit` (30 rows; 200 for query), `--offset` and `--max-bytes` (12 KB) bound delivery
only. Map and find pages replay against the pinned snapshot through `next`; `gaps`
summarizes counts. Source reads accept `--start-line` and `--lines`. Rows omit `id`,
`key`, `digest` and default flags; `--verbose` restores them. `--fields` projects columns
and an unknown name is an error. `--format table` prints columns with status and
continuations.
