# untangle architecture

Status: draft, inferred (reverse-engineered from `SKILL.md`, `scripts/`, and `references/`; not yet confirmed by the owner).

## Purpose

`untangle` audits a whole codebase for avoidable complexity without changing it. It maps structure and
flows statically, dissects approved ranges, synthesizes A (behavior-preserving) and B (behavior-change)
recommendations, and publishes a report. It recommends only: source edits and project execution are outside
the skill's contract.

## Entry contract

- `SKILL.md` is the agent entry: recommend-only rule, static inspection until SCOPE approval, exact
  `allowed_commands` afterward, no approval inference, checkpoint discipline, subagent rules.
- `scripts/workflow.py` owns stage order. `--root` selects the audited project root (default: git top level,
  else cwd). Commands: `start`, `status`, `done`, `abandon`.

## Stage machine (stateful)

`MODE = 'stateful'`, one run per project. `ORDER` in `workflowlib/steps.py`:

| Stage | Outcome |
| --- | --- |
| `inventory` | Approved root, reasoned exclusions, finite `max_files`/`max_bytes`/`max_map_steps`. No execution. |
| `map` | Static bounded loop: seed → trace/correct → finish; owns `map_rev`, mapping model and queue. |
| `scope` | User approves `map_rev`, exclusions, observables, exact `allowed_commands`, six budgets. |
| `dissect` | Line/flow review of exact ranges; findings with evidence, policy tier, track A/B/gap. |
| `synthesize` | Merged recommendations, waves, preserved alternatives; planned verification only. |
| `challenge` | Independent review of source and both map views; objections reopen work or publish. |
| `checkpoint` | User decides: extend limits/budgets, reinventory, or publish incomplete. |

Publication writes the report and removes the workflow state. Derived exports carry no approval.

## State and artifacts

- Run state: `<skill>/state/<project-key>/workflow.json`, `<project-key>` = sanitized root name + 8-char
  SHA-256 of the normalized root. Writes are atomic (temp file + replace) under a lock directory with stale
  break. `schema_version` is checked strictly; legacy state is archived via explicit `abandon`, never migrated.
- Audit artifacts: `<root>/.agents/artifacts/untangle/<audit-id>/` with `current.md`, `audit.json`, and on
  publication `report.md`.
- Every payload after `start` carries the guard `{"run": audit_id, "phase": ..., "rev": ...}`; stage checks
  reject mismatches, missing user approvals, and over-budget actions.

## Invariants

- Recommend-only: no audited-source edits; mapping is static-only; post-SCOPE commands must match the
  approved list exactly.
- Approvals and budgets are explicit user inputs, never inferred or reset. Counters are cumulative.
- Canonical state commits before derived exports; a failed export requires `status`, not replaying `done`.
- Source or reference drift becomes a checkpoint; no silent stale-map reuse.
- Python 3.9+, standard library only.

## Module map

| Module | Responsibility |
| --- | --- |
| `workflow.py` | Argparse CLI and dispatch. |
| `workflowlib/steps.py` | `ORDER`, stage prompts, advance hook. |
| `workflowlib/flow.py` | Guarded run lifecycle, schema check, resume, drift refresh, publish. |
| `workflowlib/checks.py` | Payload validation per stage (approvals, budgets, findings, review). |
| `workflowlib/transitions.py` | Stage handlers that update the candidate state. |
| `workflowlib/mapping.py` | MAP model, queue, corrections, reopen. |
| `workflowlib/work.py` | Units, findings, recommendations, budgets, coverage. |
| `workflowlib/ledger.py` | Root/tree hashes, exclusions, path specs, scope, drift. |
| `workflowlib/exports.py` | `current.md`, `audit.json`, `report.md` rendering. |
| `workflowlib/storage.py` | Project key, paths, JSON I/O, lock. |
| `workflowlib/cli.py` | Launcher quoting, stdin payload parsing, error exit codes. |

## Contracts and evolution

- Frozen: recommend-only/no-source-edit, stdlib-only runtime, `SKILL.md` entry behavior.
- Versioned: workflow JSON protocol and on-disk state schema (`SCHEMA_VERSION` + `VERSION` bump); changes
  must be backward compatible or ship explicit legacy handling.
- The reference layout (`references/mapping.md`, `principles.md`, `languages/`) may evolve through routing
  updates in the prompts and ledger.
