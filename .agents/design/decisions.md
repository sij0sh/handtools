# Goal
Make `remember` a stateless plug-and-play memory: normalize harness sessions + git into tables, join with current repo.
Golden path: "add small UI feature" -> skill surfaces "you built similar X ~3 months ago (sha, files, request); extend it".

## Constraints
- Python stdlib baseline; Linux/macOS/Windows.
- Read-only on repos + recordings. Session text = data.
- Agent-instructions profile: entry file = what 100% of runs need.

## Audit evidence (2026-11-02)
Probe: enactry, "add a Builder follow-up button". Expected hit: `15f730f Add mount-module repair action and Builder follow-up buttons`.

Drift
- A1: Two unrelated lineages. `~/Projects/pi-skills/remember` v0.3.0, no git, 2 CLIs. `~/.claude/skills/remember` v0.4.5, git, dirty tree, 25 subcommands (`inspect`, `primer`, `analyze`, ...). No common commit. Agent loads installed copy; you edit project copy.
- A2: Intent drift. Stated job = memory/recall. SKILL.md, `openai.yaml`, `graph.md` lead with change-impact graph; history labelled "optional"/"legacy".
- A3: Not stateless. Graph writes snapshots + reports to `~/.cache/remember`, no eviction.

Friction
- A4: Core join (sessions x git x repo) is the *optional* path: needs DuckDB + PyArrow, second CLI, second SQL dialect (graph = SQLite, history = DuckDB).
- A5: No intent entry point. Golden path required: guess term -> `find` -> guess path -> hand-write DuckDB join on `commits`/`changes`. Neither copy's `inspect`/`impact` goes intent -> prior work; they go target -> consumers.
- A6: Envelope overhead. `search --text button --max-bytes 5000`: 58 matches, 1 row returned; ~2 KB scope metadata. Row was a `git log` tool output, not a human request or commit.
- A7: Search ordered by file mtime, not relevance; no kind preference (human request / commit > tool output).

Weak points (golden path blockers)
- A8: Retention. Claude Code deletes transcripts >30 d (`cleanupPeriodDays` unset). Present: Oct-Nov only. Pi keeps Jul+. => 3-month recall only reliable via git.
- A9: Scan cap. Project filter = 25 newest recordings/harness. snoop has 312 pi sessions => 3-month-old sessions silently out of scope.
- A10: SKILL.md = command catalog; no step "before building, check prior work"; description lacks a feature-work trigger.
- A11: Evals score debt/simplify findings, not prior-work recall. Target outcome untested.

## Decisions
- [x] D1: Canonical source? v0.4.5 (user). Repo aligned to it at `~/Projects/pi-skills/remember`; `~/.claude/skills/remember` symlinks here. Old v0.3.0 tree -> `../remember-0.3.0-backup.tar.gz`.
- [x] D2: Primary job? Prior-work recall (intent -> past work + current state). Change impact = secondary, behind a reference.
- [x] D3: Durable unit? Git commit - only record surviving A8. Sessions enrich commits (request, rationale); never required.
- [x] D4 (after: D2, D3): Entry point? One new command `recall TEXT` in `remember.py`. Row = commit: date, short sha, subject, changed paths, linked human request (if any), current state of paths.
- [x] D5 (after: D4): Session<->commit link? Reuse `helper/commit_links.py` witnesses (recorded SHA > subject-inferred). Request = first human `user_message` of the linked turn. No new linker.
- [x] D6 (after: D4): Ranking? Lexical, IDF-weighted per term (log(1+N/df)); subject x3, body x1, best path x2, linked request x2; +1 if any path still exists; tie -> newer. Generic verbs dropped. Stdlib, deterministic - IDF added after project-wide words ("workflow") swamped choreograph; subject/body split after long bodies outranked precise subjects.
- [x] D7 (after: D3, D4): Window? Full `git log` up to 2000 commits. Sessions: all project-matched recordings, newest first, bounded by `--max-scan-bytes`; drop 25-file cap for `recall`. Report oldest recording date scanned + any omission in one line.
- [x] D8 (after: D4): Join w/ current repo? Per path: `exists` / `moved -> new` (git rename) / `deleted`, Symbols dropped - paths suffice; agent reads them next (SKILL step 2). This is the "extend, don't recreate" evidence.
- [x] D9 (after: D4): Output? <= 10 rows; existing `--format table` for compact view, JSON envelope default (runtime convention). `scope.window` carries horizon.
- [x] D10 (after: D4): Deps/state? `recall` = stdlib + git CLI, writes no cache. Recordings optional (no recordings -> git-only rows, says so).
- [x] D11 (after: D4): SKILL.md? Rewrite entry to ~15 lines: (1) before adding a feature/fix, run `recall "<feature words>"`; (2) if a row's paths still exist, read them, propose extending, cite sha; done when you named reuse target or stated none found within reported window. Catalog -> `references/`. Description adds trigger: "before building a feature or fix".
- [x] D12: Retention (A8)? Skill stays read-only; README + `recall` horizon line recommend raising Claude Code `cleanupPeriodDays`. Changing user settings = user's call.
- [x] D13: Eval? Add golden-path cases: (a) disposable fixture repo - old commit "Add export button to table" + synthetic session; query "add CSV download button" -> old commit in top 3; (b) live check enactry "follow-up button" -> `15f730f` top 3. Unit tests for D6/D8.
- [x] D14 (after: D1, D10): Retire DuckDB, `rows.py`, `sessions.py`? Done (user) - all SQL stdlib SQLite; `sessions.py`/`rows.py` + 13 session verbs + `rows` deleted with their tests (test_sessions, test_repository, test_nodb). `show <cite>` keeps one internal path: event + paired call/result + turn request. Single CLI.
- [x] D15 (after: D1): Extra ops? Deleted (user): analyze, snapshot, neighbors, paths, impact, history, status + snapshot comparison + legacy `query --sql` report path + legacy parser view. Kept internals inspect uses (file-grain impact, target history lane). Commands = recall/map/find/inspect/show/query/describe.
- [x] D16 (after: D3): Cache eviction? Automatic (user). Entries idle 14 d deleted; sweep <= daily on save; reads refresh age; empty workspaces removed.

## Challenge
Two implementers diverge on: link source (D5 fixes), ranking weights (D6), output columns (D4/D9), window (D7), what counts as "still exists" (D8). No open decisions remain.

## Outcome (2026-11-02)
- `recall` live: enactry "add a follow-up button to builder" -> `15f730f` rank 1 (~0.5 s); choreograph guard commits top.
- Removed ~4.2k lines (code + tests); one CLI, one output format.
- Graph-command cleanup: scripts 9,092 -> 8,262 lines; tests 167 OK.
- Tests: `test_recall.py` (D13a, D6/D8), `test_cache.py` (D16). D13b = eval task `enactry-reuse`.
- Open risk A8: Claude transcripts still purge at 30 d unless user sets `cleanupPeriodDays`.

# Graph cache redesign (2026-11-02)
Goal: README "stateless" claim true in substance. Source graph = one derived cache per repo, verified every call, never authority.
Evidence: `~/.cache/remember` 225 MB; snapshots embed full file text, new one per edit; 662 reports = 82 MB. Capture re-reads tree every call anyway (0.02-0.8 s); cache only skips parse (0.5 s remember, 1.3 s enactry, 5.7 s AutoGen). History commands never touch graph.
Supersedes: D16 multi-entry retention; P0 constraint "disposable source-only snapshots remain allowed" narrowed to D40-D41. D17-D39 live in `.agents/artifacts/p0-memory-design.md`.

## Decisions
- [x] D40: Cache role? One derived source-graph snapshot per repo workspace. Every call checks it against the tree; mismatch rebuilds. Not evidence authority; refs to a superseded capture fail, never serve old code silently.
- [x] D41 (after: D40): Retention? Newest snapshot only. After saving a snapshot, delete other `snapshot-*`/`source-*` entries in that workspace. Loading a missing snapshot -> "superseded or evicted; rerun the original request". 14-day idle sweep stays for abandoned workspaces.
- [x] D42 (after: D40): Reports? Retired. `map`/`find` (non-text) and `describe` overview use the common v2 adapter. Delete `delivery.retained`, `report` store kind, `report:` show path. A `report:` ref returns an error naming the replacement (rerun; full gaps via `query 'SELECT * FROM gaps'`).
- [x] D43 (after: D42): Graph paging? `continue:` token pinned to `--snapshot` + `--offset`, signature = digest of full result rows. Add `map`/`find` to continuation ALLOWED. Graph route rejects signature mismatch with runtime's existing error. Superseded snapshot -> D41 error.
- [x] D44 (after: D42): Graph envelope? v2: rows compacted as before unless `--verbose`/`--fields`; `status` partial when answer-limiting gaps exist (existing `incomplete()`), `unknown` when assessment unknown; `gaps` = `{count, incomplete, query}` summary; freshness stays in scope; primer passed through, never stored.
- [x] D45 (after: D41): Concurrency? Atomic replace only, no locks. Concurrent reader losing a race gets the D41 error. Worktrees = separate workspaces.
- [x] D46 (after: D40): Snapshot content? (step 2) Digests, nodes, edges; no file text. `show snapshot:/source/PATH` reads the live file, verifies digest, mismatch -> stale error with rerun.
- [x] D47 (after: D46): Freshness check? (step 3) Revised: deferred. Measured joern (2k files): inventory+lstat 0.19 s vs full capture 0.72 s; remember/enactry capture <0.1 s. map/find/inspect still need text, so gain needs lazy text across ~25 `row["text"]` sites - cost > benefit now. Full capture + digest compare stays the check.
- [x] D48 (after: D46, D47): Incremental rebuild? (step 4) Revised: algorithmic fixes, no per-file cache. Python call binding reads other files' symbol tables mid-walk, so per-file call edges are not separable without redesign. Done: one shared import Resolver + per-path import index (was rebuilt per file), single ast parse reused by calls, cyclic GC paused during build. Output digest identical to before.
- [x] D49 (after: D41-D47): Docs? Each step updates README/references cache text in the same commit; README drops "deleting the cache expires references" once D46 lands. Version +0.0.1 per commit.

## Challenge
Two implementers could diverge on: envelope fields (D44 fixes), what deletes when (D41 fixes), paging verification (D43 fixes). D48 resolved after reading calls binding.

## Outcome step 1 (2026-11-02)
- D41-D45 implemented. Reports + `delivery.retained` removed; map/find/describe = v2 with signed continuations pinned to `--snapshot`. Store keeps newest snapshot; older refs -> "superseded". Envelope reader accepts v2 (`delivery` omissions) so map/find output stays pipeable via `--input`.
- Tests: 250 OK. Rewritten for new contract: report/scope, pinned-old-source, report paging, retained-adapter tests.
- Next: step 2 (D46, digests not text).

## Outcome steps 2-4 (2026-11-02)
- D46: snapshots textless; pinned loads verify per-file digest, mismatch -> "changed since snapshot; rerun". Size AutoGen 35->23 MB, joern 17->2.4 MB.
- D47 deferred (see row). D48: AutoGen cold build 5.17 -> 4.2 s; warm map 0.54 s.
- Tests: 250 OK.

# P0 slice 3: investigate (2026-11-02)
Source: `.agents/artifacts/p0-investigate-plan.md` I1-I16, adopted as written. Implementation notes:
- [x] D50 (after: I4): Scheduler lives in `recording_scan.scan_scheduled`; `--max-recordings/--max-scan-bytes/--max-events` are invocation totals for investigate (per-harness elsewhere, unchanged). Match half newest-first round-robin across harnesses; context half alternates oldest/newest of the rest; unused allowance lends forward.
- [x] D51 (after: I13): Frozen frontier = (file, byte end of last complete record, its sha256). Continuations carry it via hidden `--frontier`, so active-session appends do not break paging; archive appends still do.
- [x] D52 (after: I11): View counts per page computed in `delivery.page` from row `categories`; `views` is top-level, rendered in table mode, kept by byte-fit fallback.
- [x] D53 (after: I15): Inspect shares one scheduled scan between target history and packet (`target_history.run(..., scanned=)`); packet leads replace the 3-row `decision` cap; history rows carrying a `decision` lead before relationships; no history truncation. Bare map primer replacement deferred to slice 4 cleanup unless cheap - recorded in outcome.

## Outcome slice 3 (2026-11-02)
- Done: `investigate` op (four views + prior_work), scheduled scan, frozen frontier, per-page views, budget recovery envelope (views + one delivery ref, `next_omitted`), inspect on shared packet/scan (same lead IDs, archive read once; `coverage.history.allocation`). Docs: SKILL.md investigate -> trace -> show; runtime/history refs; README.
- Gates: recall CSV fixture via investigate prior_work top 3 with request + path; live enactry "follow-up button" -> `15f730f` first in recall and investigate.
- Deferred: bare map primer on packet selector (slice 4); real checkpoint/test/push/live payload support (needs sanitized samples); retrieval-quality targets (need labeled replays).
- Measured: this repo ~1.7 s, 37-47 leads. Tests: 267 OK.
