# Common evidence runtime

## Operations

`remember.py` is the common entrypoint. `map`, `find`, `inspect`, `show`, and
`query` cover ordinary work. `describe TABLE` gives focused schemas without
capturing source. Advanced graph/history commands remain available. Leading
shared options work before the verb, including for history adapters.

`inspect TARGET` performs a bounded recipe: resolve one target, read its source,
collect relationships, retrieve target history, expand one session lead. It
never edits project code. The default `change` intent uses the existing impact
algorithm, including separately labeled direct/file-only/indirect consumers.
`bug` and `review` trace both directions at the resolved target's grain. They
collect evidence; they do not establish root cause or security findings.
Ambiguity returns candidates without searching history. `--plan` describes the
recipe without executing it. `--no-sessions` disables its recording lane.

`show` accepts retained source/node/edge/report refs, session citation tokens or
JSON refs, full commit SHAs (`git:SHA` also works), and `continue:...` tokens.
For recordings outside configured directories, use their JSON refs. A selected
session event is marked `selected: true`; surrounding rows are previews.

## SQL and custom tables

The common query path uses SQLite from Python's standard library. No extra
analytics package is required. Only one SELECT or WITH query is accepted;
external files, extension loading, and mutation are rejected. Parameters use
`:name`, `$name`, or `@name` with `--param name=value` (string values).

```bash
python3 "$S/remember.py" query 'SELECT path, size FROM files ORDER BY size DESC LIMIT 10'
python3 "$S/remember.py" query 'SELECT sha, subject FROM commits LIMIT 10'
python3 "$S/remember.py" query 'SELECT kind, count(*) AS n FROM events GROUP BY kind'
python3 "$S/remember.py" query 'SELECT f.path, o.owner FROM files f JOIN owners o USING(path)' --input owners=owners.json
python3 "$S/remember.py" query "WITH wanted(path) AS (VALUES ('src/api.py')) SELECT f.* FROM files f JOIN wanted USING(path)"
```

SQLite compilation determines table/column dependencies before any provider
runs. The runtime loads each required provider once per invocation; Git-only
queries do not scan recordings. `--plan` compiles the query and displays its
provider plan without executing providers. Supplied files are read to establish
their schema even during planning.

| Table | Grain / source |
| --- | --- |
| `files` | Captured source path, digest, state, content, lines and source ref |
| `nodes`, `edges`, `gaps` | Source graph nodes, typed edges, unresolved occurrences |
| `code_items` | Captured symbol; use `nodes` for canonical graph identities |
| `events` (`rows` alias) | Normalized recorded event |
| `commits`, `changes` | Git commits and changes against each parent basis |
| `commit_links` | Recorded/inferred/unresolved event-to-commit witness |
| `edit_hunks`, `edit_symbols` | Recorded edit evidence and explicitly qualified symbol mappings |
| `file_status` | Live Git worktree metadata; distinct from pinned `files` |

Use `describe TABLE` for exact columns, keys and grain. Joins may multiply
witnesses: count distinct identities at the intended grain. `files` supports
ordinary directories; Git tables report unavailable coverage outside Git.
`file_status` is live even when graph tables use `--snapshot`; the two scopes
are deliberately separate. Recorded edits mapped to captured source retain
their basis and uncertainty; they do not prove historical source identity.

`--input NAME=FILE` accepts JSON object arrays, JSONL, or existing result
envelopes; `-` reads stdin. Built-in names are reserved, case-insensitively.
For empty/all-null data, declare `--type NAME.COLUMN=TEXT` (also INTEGER, REAL,
BOOLEAN and JSON). Types on built-ins are fixed. Custom inputs are limited to
16 MiB combined and the invocation's row budget. Unknown external coverage
remains unknown; supplied rows are not assumed to be an exhaustive population.
No custom table or transcript-derived result is persisted. Use CTEs for
intermediate tables; persistent DDL is intentionally unsupported.

## Budgets and coverage

| Budget | Deadline | Source files / bytes | Recordings per harness | Events per harness | Git commits | Query input rows |
| --- | --- | --- | --- | --- | --- | --- |
| standard | 30 s | 20,000 / 32 MiB | 25 | 25,000 | 200 | 100,000 |
| deep | 120 s | 50,000 / 128 MiB | 100 | 100,000 | 2,000 | 200,000 |

Per-file source default: 1 MiB. Recording scan byte caps: 64/256 MiB per harness.
Advanced numeric flags override policy defaults. Deadlines are cooperative at
provider/file boundaries; SQLite queries are interruptible and Git subprocesses
receive remaining time. A single parser operation is not forcibly preempted.
The row/byte limits bound materialized inputs; there is no OS-level memory cap
on SQLite. Recipes do not retry or widen scope automatically; a partial
standard-budget result offers one `coverage` continuation that reruns at deep.

Common results use schema version 2:

- `coverage` describes evidence completeness per provider. `partial` means a
  gap or unknown external input may affect the answer.
- `delivery` describes only the rows actually delivered, independently of
  source coverage. Page limits do not make complete evidence partial.
- `next` contains executable continuation refs, with a purpose and effect.
  `delivery` reads another page; `coverage` explicitly widens a computation cap
  or scan boundary; `expansion` reads more evidence (inspect: all target
  history leads, same recording scope and limits, pinned snapshot). Order:
  coverage, delivery, expansion.

SQL sees full bounded provider inputs before display projection or paging.
`--limit` controls delivered rows, not aggregate input. Use SQL LIMIT/OFFSET
only when intentionally changing the query itself.

Continuations carry absolute scope, filters, presentation and budget settings.
Source-query continuations pin the source snapshot. Transient inputs are
reloaded and fingerprint-checked; changes fail explicitly instead of shifting
pages silently. Tokens contain request metadata, not transcript payloads, and
are versioned data rather than executable shell commands. Stdin inputs cannot
be replayed, so their output does not offer a continuation. Preserve the input
in a user-approved file or rerun the query with a larger output limit.

The runtime's new query/inspect/session-show results remain transient. Existing
source graph operations retain source-only snapshots/reports. Transcript text
never goes through the graph report store. Selected event text may require a
larger `--max-bytes`; an executable delivery continuation increases that cap
without changing evidence scope.

One delivery component (`helper/delivery.py`) pages and byte-fits every result
through an explicit adapter: `retained` (graph reports, source-only, saved),
`history`, `common` (v2) and `envelope` (sessions.py/rows.py), all transient.
`retained` refuses history/inspect or `retention: transient` documents.

## Compatibility

`sessions.py` and `rows.py` are thin adapters into the same helper package.
All three CLIs build parsers and routes from one registry, `helper/operations.py`.
Their established DuckDB SQL dialect and v1 envelopes remain supported and
still require optional dependencies. No backend is silently selected based on
installed packages. New work should use positional `remember.py query SQL`.

The original `remember.py query --sql SQL` graph-only shape keeps its retained
v1 report/paging behavior. Queries using new tables/columns go through the
common catalog. Retained graph `show` and advanced history commands preserve
their existing output contracts. This bridge avoids invalidating existing
consumers while agents adopt the smaller common interface.
