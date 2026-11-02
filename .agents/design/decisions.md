# Goal
Slim `references/{reader,runtime,graph,history}.md` to facts that change an agent's behavior, and remove legacy/deprecated code so one authoritative command surface remains.

## Constraints
- Python 3.11+ stdlib; optional tree-sitter. Stateless: no migration, no compatibility layer, no retained results.
- Public command set stays 10 operations: `map`, `find`, `show`, `query`, `describe`, `activity`, `trace`, `signals`, `investigate`, `inspect`.
- Envelope field set stays: `operation`, `status`, `results`, `scope`, `coverage`, `delivery`, `next`, `snapshots`, `views`.
- Docs in scope: the four leaves only. README stays except for surfaces removed by D102. SKILL.md unchanged.
- Suite green (270 tests, <20 s), VERSION +0.0.1 at commit.

## Condensed prior state
Full history: `.agents/artifacts/decisions-archive-2026-11-02.md`, `.agents/artifacts/p0-*.md`.
- D1-D16: one CLI, stdlib SQLite, DuckDB/session verbs retired.
- D40-D53: one derived textless snapshot per repo; newest only; reports, `recall`, primer lanes retired; signed continuations.
- D54-D76: `investigate`/`signals`/`orientation`; `inspect` order source > packet > relationships > history; `recall` -> `commit_rank`.
- D77-D85: in-process test harness; 270 tests, 5.9 s; retirement guards kept.

## Decisions

### Reference files
- [x] D86: Keep rule per sentence? Delete unless the fact changes how a run interprets or acts on output. Delete anything already printed by `--help`, `describe`, `--plan`, an error message, or SKILL.md/README - reason: agent-instructions section 3, a sentence whose deletion changes nothing is a no-op.
- [x] D87: Leaf ownership? `reader` = setup only. `runtime` = envelope/paging/continuations/budgets/SQL + operation contracts not in SKILL.md. `graph` = source capture, `map`/`find`, `inspect` relationships. `history` = `investigate`/`signals`/`activity`/`trace` + `inspect` history lane + recordings.
- [x] D88: Shared facts? State the interpretation rule inline once in each leaf that needs it, one sentence, no cross-leaf pointer - leaves route nowhere; a pointer would be a dangling read.
- [x] D89: Version language? Refs describe one current format with no `schema version 2`, `v2`, "retired", or "legacy" wording - stateless calls cannot meet another version; version talk only invites compatibility work.
- [x] D90: Size guard? Add `tests/test_layout.py` case: each leaf <= 6 KB, total <= 16 KB (current 28 KB) - pins the slimming against regrowth; cheap and deterministic.
- [x] D91: `reader.md` keeps: Python 3.11+, stdlib, optional tree-sitter grammars + "reported, not installed", macOS Xcode 3.9 gotcha, `scripts/profiles`/`settings.json` as the recording-source config. Deletes: envelope/omissions paragraph, `describe`/`--help` pointer, orientation paragraph, graph/history pointers.
- [x] D92: `runtime.md` keeps: `investigate` goal-word rule and `--path` expansion cap 3, active-session/`archive_horizon` meaning; `inspect` recipe order, intents, ambiguity, `--plan`, "no root cause"; `trace` lane/dimension/commit-anchor rules; `show` accepted refs + `selected`; SQL one-SELECT/read-only/params/`--input`/`--type`/CTE/no-DDL + one example; standard vs deep budget table; coverage vs delivery vs next semantics, oversized-row recovery, `views` per page; continuation scope/pinning/stdin replay, token data-not-shell, PowerShell 5.1 quoting; exit 0/2/130 and partial-vs-truncated. Deletes: operations prose duplicated in SKILL.md/help, table-of-tables, 4 of 5 SQL examples, cache details, `--sql` alias line, `report:` line.
- [x] D93: `graph.md` keeps: snapshot/cache lifecycle (one per workspace, rebuild on mismatch, superseded/expired/corrupt refs fail, 14-day idle, worktree isolation); `map` bare primer behavior and `--snapshot` omission; `inspect` intents/`reach` tiers/bounds; predicate table trimmed to consequence; traversal = `IMPORTS`+`CALLS_STATIC`, tests never bridge, potential not runtime; gaps = unknown not absent; manifest missing vs not-captured; generated/vendored/lockfile listing; capture exclusions + `.rememberignore`; `find` filter semantics (`*` crosses `/`, plain path covers descendants, filters do not change capture, `--count-by` after filtering); paging/`--verbose`/`--fields`. Deletes: per-language resolver rules, exit-code/status section (runtime owns), duplicate examples, `code_items` reference.
- [x] D94: `history.md` keeps: four view semantics + state meanings; `prior_work` weights/generic-word drop/5 paths/2000-commit window; scheduled-scan allocation and suppression (policy not gap); active-session frontier; `signals` four kinds + pi-only checkpoints + "leads not verdicts"; `inspect` history order, ranking tiers, `possible_correction`, alias/no-widening matching, symbol-identity caveats, per-harness caps; `--no-sessions` marks the lane `not_searched`; the not-built list (failure-after-fix, unchanged-content rereads); cite tokens, JSON refs, human/agent/tool separation, copied-text caveat. Deletes: duplicated `investigate` prose from runtime, primer paragraph, PowerShell note (runtime owns), `describe events` pointer, "results are transient" duplicate.
- [x] D95: Audit inventory below is exhaustive for this pass; any legacy item not listed stays. See table.

### Legacy audit
| Site | Current | Action |
|---|---|---|
| `envelope.load_rows` | accepts `rows[]`/`links[]`, grouped `harnesses[]`, any `schema_version <= 2` | current envelope only (D98) |
| `delivery.py`, `runtime.py` errors, `target_history.py` | literal `2`, `2`, internal `schema_version: 1` | one `SCHEMA_VERSION`; drop internal field (D98) |
| `catalog.py` | `CATALOG["rows"] = events`; `code_items` grain cites gone `sessions.py` | delete alias; delete `code_items` (D102) |
| `operations.py` | `Operation.family`/`tier`, `names()`, `--sql` alias, optional `--regex`, ignored `--primer/--no-primer`, "legacy" help | remove (D96, D97) |
| `graph_cli.py` | second `parser()`, duplicate `defaults()`, legacy `run()` dispatcher | fold into `runtime`/`operations` (D96) |
| `graph_store.py` | `report:` guard, `report-` cleanup prefix | delete (D100) |
| `graph_output.py` | "retained graph reports" docstring, `report` table fallback | reword/delete (D100) |
| `reconciliation.py` | `command_kind()` backward-compatible single class | delete dead wrapper (D101) |
| `graph_queries.py` | `inputs()` "compatibility SQL" docstring | reword (D101) |

- [x] D96: Single command owner? `operations.py` declares operation, args, defaults, route, summary. `runtime.normalize` derives `limit`/`max_query_rows`/primer mode. `Operation.route` dispatches; `graph_cli` keeps only `get_graph`/`show`/map-find implementations. Delete `family`, `tier`, `names()`, `GRAPH`, `graph_cli.parser`, `graph_cli.defaults`, `run()` dispatch - one owner per defaults/dispatch (defaults §2).
- [x] D97: CLI aliases? Remove `--sql`, optional-value `--regex` (TEXT form errors), and silent `--primer/--no-primer` acceptance outside `map`; update tests to positional SQL and `--regex PATTERN` - one authoritative invocation per operation.
- [x] D98: Envelope input? Accept a JSON array, JSONL, or object with `schema_version == SCHEMA_VERSION` and `results[]`. Reject other versions, `rows[]`, `links[]`, grouped `harnesses[]`. Export `SCHEMA_VERSION` from `envelope.py`; `delivery`/`runtime` errors use it; drop `target_history` `schema_version: 1` - stateless: no producer emits old shapes.
- [x] D99: Cache schema mismatch? `load_stored` raises `ValueError` when `body["schema"] != SCHEMA`; current-capture reuse catches it and rebuilds; a pinned `--snapshot` ref returns the error - user directive; rebuild is safe because the snapshot is derived.
- [x] D100: Retired refs? Delete `report:` guard, `report-` supersede prefix, `graph_output` `report` fallback; a bad ref gets the generic invalid-reference error - no `report:` ref can exist in a stateless system.
- [x] D101: Dead code? Delete `command_kind`, `ignored_primer`, `delivery.json_size`, `investigate.summary_text` (no caller). Keep `graph_output.COLUMNS` (used by table rendering). Reword stale docstrings in `catalog`, `operations`, `graph_queries` - each is a second, drifting description.
- [x] D102: Public SQL tables (after: O1)? Drop `rows`; drop `code_items` and build the internal `items_by_path` map from graph symbol nodes. Update README table list, refs, `test_runtime` - `nodes` is the sole symbol identity; `code_items` is a derived second copy (defaults §2).
- [x] D103: Tests? Update call sites for removed aliases; keep one retirement guard per removed surface (argparse error, unknown table) per D81; add cache-schema rebuild test and envelope-version rejection test - pins removals without restoring old paths.
- [x] D104: Order? Code refactor -> tests green -> rewrite refs to post-refactor behavior -> size guard -> VERSION 0.5.2 (0.5.1 went to the design-record commit) -> one commit - docs must describe the shipped surface, not the old one.

## Open
- [x] O1: Accept the breaking public surface (remove `--sql`, TEXT+`--regex`, `CATALOG["rows"]`, `code_items`)? Yes - operator confirmed all four; stateless and single-owner defaults outweigh any external SQL naming them.

## Outcome
- 274 tests OK in 5.8 s; refs 15.1 KB total (reader 0.5, runtime 4.0, graph 4.6, history 6.0 KB).
- One owner each: `operations.derive` for defaults, `envelope.SCHEMA_VERSION` for version, `graph_store.SCHEMA` checked on load.
- Removed all four surfaces plus `report:`/`report-` handling, `load_rows` legacy shapes, `command_kind`, `json_size`, `summary_text`, stale docstrings; guards added for each removed alias and table.

## Challenge
Two implementers could still diverge on (a) which of the listed audit rows are public contract breaks - fixed by O1; (b) how much per-language graph detail survives - fixed by D93 keep/delete lists; (c) whether shared facts are duplicated inline - fixed by D88. No other material choice left once O1 is answered.
