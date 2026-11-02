# Common evidence runtime

## Operations

`remember.py` is the common entrypoint. `investigate`, `map`, `find`,
`inspect`, `activity`, `signals`, `trace`, `show`, and `query` cover ordinary work.

`investigate` returns the four-view evidence packet (pitfall, invariant, task,
decision) plus prior-work commits; see [history](history.md#investigate).
`--plan` describes it without reading. `--no-sessions` marks every view
`not_searched`.

`prior_work` ranks non-merge commits against goal words: each term weighs
log(1 + commits / commits containing it); subject x3, body x1, best path x2,
linked human request x2, +1 if a changed path still exists; ties go newest.
Generic verbs (`add`, `new`, `ui`, `fix`, ...) and words under 3 letters are
dropped; a goal with none left is an input error. Rows show up to 5 paths with
current state (`exists`, `old -> new`, `-> gone`) and the request + cite when a
session recorded the commit. Always reads the deep commit window (2000);
`scope.archive_horizon` gives the oldest commit/session scanned and the commit
count, so a miss only covers it. `--path` adds one `signals PATH` expansion per
path (max 3). `describe TABLE` gives focused schemas without capturing source.
Leading shared options work before the verb.

`signals TARGET` groups recorded operations on one file or symbol (same target
resolution as `activity`, scheduled scan as `investigate`) into four kinds:
`failed_exchange`, `correction_candidate`, `checkpoint_gap`, `repeated_read`.
See [history](history.md#signals).

`inspect TARGET` performs a bounded recipe: resolve one target, read its source,
select packet leads (shared with `investigate`), collect relationships, retrieve
target history after relationships, expand one session lead, offer one `signals` expansion. It
never edits project code. The default `change` intent uses the existing impact
algorithm, including separately labeled direct/file-only/indirect consumers.
`bug` and `review` trace both directions at the resolved target's grain. They
collect evidence; they do not establish root cause or security findings.
Ambiguity returns candidates without searching history. `--plan` describes the
recipe without executing it. `--no-sessions` disables its recording lane.

`trace REF` reconstructs one bounded episode around a returned event JSON ref,
cite token, or full commit SHA. Default scope is the anchor's human exchange;
parallel branches stay separate lanes and are never merged by timestamp. It
reports branch-local operations, checkpoint claims and their coverage gaps
(boundary to publication, publication to frontier), and independent observations
for requested, edited, verified, committed, pushed, live-confirmed and
blocked/remaining. A test pass, commit, push and live run stay distinct; unknown
outcomes and unsupported checkpoint shapes stay visible. Commit anchors keep each
witness exchange separate and add path-overlap context labeled `related_context`
(shared path, not proven contribution). `next` offers `show` expansions plus
`trace` widen refs for neighboring exchanges, forks, gaps and related lanes. An
exact event ref reads only its recording; a commit anchor uses the bounded
recording archive, with a targeted SHA/subject rescan when the archive horizon
omits the witness. Results are transient.

`show` accepts snapshot source/node/edge refs, session citation tokens or
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
| `sessions` | One recording: span, counts, first request; join `events USING(recording_id)` |
| `commits`, `changes` | Git commits and changes against each parent basis |
| `commit_links` | Recorded/inferred/unresolved event-to-commit witness; one operation may have many |
| `operations` | One operation/path association; missing outcome stays `unknown` |
| `checkpoints` | Original checkpoint claim plus branch-resolved coverage boundary |
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
The row/byte limits bound materialized inputs; SQLite heap is capped at 512 MiB
(error, not partial). Ctrl-C returns `"error": "cancelled"`, exit 130. Recipes do not retry or widen scope automatically; a partial
standard-budget result offers one `coverage` continuation that reruns at deep.

Common results use schema version 2:

- `coverage` describes evidence completeness per provider. `partial` means a
  gap or unknown external input may affect the answer.
- `delivery` describes only the rows actually delivered, independently of
  source coverage. Page limits do not make complete evidence partial.
- `next` contains executable continuation refs, with a purpose and effect.
  `delivery` reads another page; `coverage` explicitly widens a computation cap
  or scan boundary; `expansion` reads more evidence. Inspect expansions: rest of source past the
  80-line preview, one `inspect` per ambiguous candidate (max 5); all pinned to
  the inspected snapshot. Order: coverage, delivery, expansion. A row larger
  than `--max-bytes` gets one delivery continuation sized to fit it. If
  metadata alone still overflows, only `views`, status and that delivery ref
  survive; `next_omitted` names what was dropped. `views` counts are per page.

SQL sees full bounded provider inputs before display projection or paging.
`--limit` controls delivered rows, not aggregate input. Use SQL LIMIT/OFFSET
only when intentionally changing the query itself.

Continuations carry absolute scope, filters, presentation and budget settings.
Source-query continuations pin the source snapshot. Transient inputs are
reloaded and fingerprint-checked; changes fail explicitly instead of shifting
pages silently. Tokens contain request metadata, not transcript payloads, and
are versioned data rather than executable shell commands. Stdin inputs are not
saved: a continuation over `--input NAME=-` carries `stdin.tables` and needs the
same rows piped to `show` again; different rows fail as a source change, a
terminal stdin fails instead of blocking.

All results are transient. The only cache entry is one source-only snapshot per
workspace; a newer capture supersedes it. Transcript text never enters it. Selected event text may require a
larger `--max-bytes`; an executable delivery continuation increases that cap
without changing evidence scope.

One delivery component (`helper/delivery.py`) pages and byte-fits every result;
later pages recompute through continuations. `report:` refs are retired.

## Compatibility

`remember.py` is the only CLI; parsers and routes come from one registry,
`helper/operations.py`. All SQL is stdlib SQLite.
 `--sql SQL` is an alias for the positional SQL.
