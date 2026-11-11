# untangle

Audit a codebase for avoidable complexity in bounded, resumable stages. Publishes behavior-preserving (A)
and behavior-change (B) simplification recommendations. Recommends only; never edits audited source.

This repository is the skill. An agent reads `SKILL.md`; `scripts/workflow.py` owns the stage order.
See `docs/architecture.md` for the engine and state layout.

## Requirements

- Python 3.9+ (`python3` on Linux/macOS, `python` on Windows); standard library only, no runtime dependencies.
- Optional: [mise](https://mise.jdx.dev/) for the pinned dev toolchain (Python 3.14, ruff).

## Install

Install the `handtools` monorepo package, or copy this directory into your harness
skill folder. See the repository root `README.md` for Pi and Claude Code install
and update commands.

The installed skill directory must stay writable: run state lives in
`<skill>/state/` and audit artifacts in the audited project's `.agents/artifacts/untangle/`.
Active runs from an older schema must be closed with `abandon` (then `start`)
explicitly; state is never migrated silently.

## Use

From the audited project root:

```sh
python3 ~/.agents/skills/untangle/scripts/workflow.py start
```

Do the printed stage, then run the printed `done` command, piping the JSON payload it asks for and always
including the run/phase/revision guard. `status` resumes and repairs exports. After a committed export
failure use `status`, never replay `done`. Stages: `inventory` → `map` → `scope` → `dissect` →
`synthesize` → `challenge` → `checkpoint` → published report.

Read `SKILL.md` for the full contract: approvals, budgets, static-only mapping, and subagent coordination.

## Development

```sh
mise install        # pinned Python + ruff; run once
mise run check      # lint + tests
mise run lint       # ruff check .
mise run test       # python -m unittest discover -s tests -v
```

CI (`.github/workflows/ci.yml`) runs the same checks on push/PR plus a Python 3.9 compatibility leg.
Bump `VERSION` (0.0.1 step) with every committed change.

## Layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Agent entry contract: rules, stages, coordination. |
| `scripts/workflow.py` | CLI: `start`, `status`, `done`, `abandon`. |
| `scripts/workflowlib/` | State machine, checks, transitions, mapping, ledger, exports. |
| `references/` | Mapping protocol, principles, and per-language profiles. |
| `tests/` | Standard-library unittest suite. |
| `docs/architecture.md` | Draft, inferred engine overview. |
