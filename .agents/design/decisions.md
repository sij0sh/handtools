# Goal
`remember` is stateless evidence memory: rebuild source, Git and session tables per call, expose refs, keep only one textless source snapshot per repository.

## Constraints
- Python 3.11+ standard library; optional tree-sitter extras; Linux/macOS/Windows.
- Read-only on repositories and recordings; transcript text never enters the snapshot cache.
- Agent entry point = `investigate`, then `trace`/`show`; one CLI (`scripts/remember.py`).

## Condensed prior state
Historical detail: `.agents/artifacts/decisions-archive-2026-11-02.md`.
- D1-D16: single CLI, stdlib SQLite, prior-work recall, cache eviction. DuckDB/session verbs retired.
- D40-D53: one derived snapshot per repo; newest only; reports retired; signed continuations; textless snapshots; investigate packet.
- D54-D76: `recall` retired (now `commit_rank`); `investigate`/`signals`/`orientation`; inspect order source/packet/history; current `VERSION` 0.5.0.
- Current commands: `map`, `find`, `show`, `query`, `describe`, `activity`, `trace`, `signals`, `investigate`, `inspect`.

# Test suite refactor (2026-11-02)

## Goal
Keep coverage of current contracts, run the whole suite under 20 s, remove tests that test the wrong owner or duplicate another layer.

## Evidence
- Baseline: 271 tests, 24.4 s. 235 CLI invocations each started `remember.py` (~60 ms import/startup); test_graph + test_graph_features alone were 9.7 s.
- Graph tests without explicit `--no-primer` ran bare-map orientation against the developer's real recordings (`TRACE_SESSIONS_SETTINGS` default), making runs slow and environment-dependent (`test_bare_map...` ~1 s).
- `tests/test_graph_features.py` imported `tests/test_graph.py` and borrowed its `setUp`/`cli`/`fixture`.
- `test_runtime.test_sql_timeout` duplicated `test_graph.test_sql_timeout` (same engine path).
- No test targeted a removed command except explicit retirement guards (`recall`, removed primer flags).

## Decisions
- [x] D77: Budget? Under 20 s locally, measured not enforced. A timing assertion would be flaky on CI; profile per test instead.
- [x] D78: CLI execution owner? `tests/support.invoke` calls `runtime.main` in-process for contract tests. Real subprocess stays for entrypoint smoke, SIGINT, and commands the test executes. Reason: preserves argparse, routing, envelopes and exit codes; removes 235 interpreter starts.
- [x] D79 (after: D78): In-process isolation owner? `tests/support.py` patches stdout/stderr/stdin, restores env/cwd/settings, and clears `cite._recording` between calls. Reason: `discovery.SETTINGS` and cite lookup are process-global; tests must not inherit the developer archive.
- [x] D80 (after: D78): Shared graph fixture? `tests/graph_fixture.GraphCase`; no test module imports another test module. Reason: `FeatureTests.setUp = GraphTests.setUp` coupled two files and hid fixture ownership.
- [x] D81: Delete deprecated tests? None found; remove only the duplicate engine timeout test. Keep one-line retirement guards: they pin the current argparse error.
- [x] D82 (after: D78): Over-engineered layers? Collapse `cli`/`raw` subprocess wrappers onto `support`; keep E2E assertion detail, including table formatting and pinned-ref failures. Do not reduce parser/resolver/reconciliation tables: they are pure, fast, and the main correctness evidence.
- [x] D83 (after: D79): Orientation in graph tests? Always `--no-primer` or a temp empty recording settings. Bare map is the exception: it gets a temp settings file so the entrypoint still runs the default primer path without reading user archives.
- [x] D84 (after: D78): Windows? Skip the SIGINT test on `win32`; `preexec_fn` is POSIX-only. In-process support uses only portable stdlib APIs.
- [x] D85 (after: D81): Test count? 270; README command `python3 -m unittest discover -s tests` unchanged. No production behavior change.

## Challenge
Two implementers could differ on which CLI assertions become in-process (D78), how global settings/caches are isolated (D79), or whether to delete "low-value" retirement guards (D81). D83 fixes the archive dependence; D84 fixes the Windows gap. No material choice left open.

## Outcome (2026-11-02)
- 270 tests, OK, 5.9 s locally (target <20 s); repeated runs stable. Slowest: SIGINT test ~1.0 s; all others <0.12 s.
- Removed: duplicate `test_runtime.test_sql_timeout`; per-module subprocess CLI boilerplate; cross-module test inheritance.
- Added: `tests/support.py`, `tests/graph_fixture.py`; `--no-primer`/empty-settings isolation in graph tests; Windows skip for SIGINT.
- Evaluation: no deprecated tests; two retirement guards kept; over-engineering was infrastructure (235 process launches, borrowed fixtures), not assertion depth. `test_large_map...` asserted the substring `DIRECTOR`; now `DIRECTORIES`.
