# Workflow contract (draft, M1)

A workflow skill declares what it needs from the shared engine in one manifest. This is the
generator contract that build-skills will validate and generate from in M4. In M1 it is a draft:
nothing enforces it at runtime. `workflow-contract.schema.json` beside this file is its shape.
Foundation's and untangle's manifests are kept as test fixtures, which shows the current workflows
can be described with it.

## Fields

- `name`, `contract_version` (1), `invocation`: `explicit` for a workflow skill. Shared modules
  (planning, recon) have no manifest and no trigger.
- `mode`: `stateless` (nothing saved between steps) or `stateful` (journal-backed run).
- `recon`: what reconnaissance the workflow needs.
  - `depth`: `none`, `orient`, `map` or `deepen`. `none` requires a `reason`.
  - `required_records`: record types the workflow reads (`contract`, `gap`, ...).
  - `external_scope`: `repository` (primary root only) or `supplied` (related roots the user names).
    Never autonomous discovery.
  - `freshness`: `pin` (closed snapshot pinned per run; stale citations reopen dependent work) or
    `reuse-if-fresh` (use the newest fresh snapshot, else refresh).
- `check_packs`: named, versioned check sets (placeholder until M2/M3), plus `unsupported`:
  `report-gap` (unsupported scope is reported, never silently skipped).
- `stages`: in run order. Each has `name`, `inputs`, typed `outputs`, `evidence` (what must be
  cited), `exit_check` (the executable check that refuses `done`) and `next` (permitted
  transitions; `null` ends the run).
- `budgets`: named positive limits and where the run stops when one is spent (`checkpoint`).
- `outcomes`: subset of `complete`, `incomplete`, `cancelled`. Reaching the report means the
  report is written, not that everything was covered; `incomplete` and `cancelled` are never
  presented as success.

## Rules for M4

- Reject a manifest whose stages cannot be reached, whose transitions name unknown stages, whose
  outcomes are undefined, or that confirms a domain claim with no evidence gate.
- A workflow with `recon.depth` other than `none` receives the recon guide in its prompts; it never
  copies the guide's text.
- Distribution ships every shared module the manifest needs (`_engine`, `_engine/recon`,
  `_engine/policy`) and no invocation metadata for them.
