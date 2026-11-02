# Runtime contracts

`investigate GOAL` needs descriptive goal words (3+ letters, not only generic verbs);
omit GOAL for repository orientation. `--path` adds one `signals PATH` expansion per
path, max 3. `scope.archive_horizon` is the oldest commit/session scanned, so a miss
covers only that horizon.

`inspect TARGET` runs a fixed recipe: resolve one target, source, packet leads,
relationships, history, then one session-lead expansion. Ambiguous or unresolved
targets return candidates without reading history. `change` intent uses file-grain
impact; `bug` and `review` walk both directions at the target's grain. Results are
evidence, never root cause or a security verdict. `--plan` lists stages without reading.

`trace REF` anchors on one human exchange, or on a commit's witness exchanges (kept
separate; path overlap is `related_context`, not contribution). Branches are separate
lanes, never merged by timestamp. Test pass, commit, push and live confirmation are
distinct observations; checkpoints stay claims with a coverage boundary. Unknown
outcomes and unsupported checkpoint shapes remain visible.

`show` accepts snapshot source/node/edge refs, cite tokens, event JSON refs, full commit
SHAs (`git:` optional) and `continue:` tokens. An expanded session event is
`selected: true`; nearby rows are previews, not the anchor.

## SQL

One read-only `SELECT` or `WITH` per call; mutation, ATTACH, PRAGMA, extension loading
and multiple statements are rejected. Dependencies are compiled before providers load,
so a query reads only the tables it names. `--plan` lists them without loading providers; supplied `--input` files are
still read for their schema.
`--param NAME=VALUE` binds `:NAME`, `$NAME` or `@NAME` as strings. `--input NAME=FILE`
adds object rows from a JSON array, JSONL or a current result envelope (`-` is stdin);
built-in names are reserved. `--type TABLE.COLUMN=TYPE` supplies missing or
all-null column types. Use CTEs for intermediate tables; DDL is unsupported. SQL sees
full bounded inputs before projection and paging, so `--limit` changes delivery, not
aggregates.

## Budgets

standard: 30 s, 20,000 files, 25 recordings and 25,000 events per harness, 200 commits,
100,000 input rows. deep: 120 s, 50,000, 100, 100,000, 2,000, 200,000. Per-file 1 MiB.
Deadlines are checked at provider and file boundaries; Git and SQLite receive the
remaining time; a single parse is not preempted. SQLite heap is capped at 512 MiB
(error, not partial). A partial standard result offers one `coverage` continuation that
reruns at deep; recipes never widen scope on their own.

## Results

`coverage` states evidence completeness per provider; `partial` means a gap or a
possibly incomplete external input could change the answer. `delivery` describes only
rows delivered: paging and byte caps set `complete: false` without making evidence
partial. `next` holds executable refs: `coverage` widens a computation boundary,
`delivery` reads the next page, `expansion` reads more evidence; order is coverage,
delivery, expansion. A row larger than `--max-bytes` gets one delivery ref sized to fit.
If metadata alone overflows, `views`, status and that ref survive and `next_omitted`
names the drop. `views` counts are per page.

Continuations carry absolute scope, filters, presentation and budget; source queries
pin the snapshot, transient inputs are reloaded and fingerprint-checked, and changed
inputs fail instead of shifting pages. Tokens are data, not shell; they never contain
transcript text. A stdin continuation needs the same rows piped again; a terminal stdin
fails instead of blocking. `next[].argv` is quoted for the current platform (POSIX or
Windows argv). PowerShell 5.1 strips `"` from native arguments: use PowerShell 7+ or
escape as `\"`.

Exit 0 for completed results, including explicitly partial evidence; 2 for invalid input
or failure; 130 for Ctrl-C (`"error": "cancelled"`). Truncation is delivery, not partial
evidence. Only one source snapshot per workspace is cached, plus its lookup index; results and
transcript text are never retained.
