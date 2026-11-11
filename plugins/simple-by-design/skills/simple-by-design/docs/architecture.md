# Architecture

Status: current

`simple-by-design` is a local CLI that routes one agent through a fixed design sequence: draft → resolve one gap → review, then record the design. It is design-only; there is no ledger, agent-selected workflow or implementation step.

```mermaid
flowchart LR
  U[User request] --> C["scripts/sbd.py"]
  C --> P["engine/prompts.py"]
  C --> S["engine/state.py"]
  S --> R["engine/router.py"]
  P -. absolute path .-> G["references/design.md"]
  S --> J[".agents/decision.json"]
  R -. fixed phase transitions .-> T["draft / resolve / review / complete"]
```

## Components

- `scripts/sbd.py` is the CLI. It starts a run with `--request`, resumes with no arguments, and accepts one result with `done TICKET`. It prints the next prompt or resumption command; errors go to stderr with a resume hint.
- `scripts/engine/router.py` owns checkpoint schema 4, result shapes and transitions. `phase` is `draft`, `resolve`, `blocked`, `review` or `complete`; payload keys appear only when needed. `draft` accepts `candidate` or `need`; `resolve` accepts `resolved` or `blocked`; `review` accepts `pass`, `revise` or `need`. `advance` rotates the opaque ticket on every non-pass result. A passing review drops the ticket and stores the full completed record: request, candidate, optional resolutions and review.
- `scripts/engine/state.py` is the only writer. It resolves the task root, stores `.agents/decision.json` with sibling `.decision.lock` and temporary files, serialises writers with `flock`, rejects symlinked ancestors and non-regular files, and writes atomically via temporary file, `fsync`, `os.replace` and directory `fsync`. Duplicate JSON keys are rejected. Old-path or pre-schema-4 state fails closed without auto-import. Completion is one write, so a pre-replace failure leaves the review prompt needing a passing result again; a post-replace failure leaves either the old review or the already-valid complete record. No `.agents/artifacts/` path is read, written or checked.
- `scripts/engine/prompts.py` holds the static prompt text, the JSON contract, bounded context and the completed-record summary renderer. Draft and review append an absolute path to `references/design.md`; resolve omits it. The printed return command uses absolute paths.
- `references/design.md` holds common design defaults, ten language profiles and the instruction-design rule. The agent reads it on demand; it is not embedded in every prompt.
- `tests/` holds the stdlib `unittest` suite covering routing, state, atomic completion recovery, concurrency, prompt disclosure and instruction budgets.

## Invariants

- **Design only:** prompts and completion never authorise implementation or external effects.
- **One state owner:** the CLI owns transitions; the agent supplies only the requested result.
- **Opaque tickets:** a ticket is accepted once, only for the current prompt; stale or duplicate results do not advance. `complete` keeps no ticket because it accepts no results.
- **Fail closed:** corrupt, legacy or symlinked state is refused rather than repaired.
- **Portable runtime:** Python 3.11+ on POSIX, standard library only.
- **Bounded instructions:** SKILL body ≤100 words; ordinary emitted static surface ≤400 words; guidance ≤350 words; combined ≤750 words.
- **No ledger:** one current snapshot, no history, workflow selection or agent-authored next step. The completed state is the durable record; the terminal summary is a rendered view and no Markdown artifact is written.

## Data flow

A request enters `sbd.py` and becomes a checkpoint. The agent performs the printed prompt, submits JSON through the printed ticket, and receives the next prompt. A `need` result temporarily routes to `resolve`; `revise` returns to `draft` with named gaps; `blocked` pauses until resumed. A passing review writes the full record in one atomic checkpoint replace and prints the rendered summary followed by `DONE`. Re-running the same `--request` text replays that summary without writing; a different request replaces the record.
