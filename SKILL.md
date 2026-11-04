---
name: simple-by-design
description: Record design decisions before implementing features, refactors, or ambiguous changes. Use anytime design decisions are needed.
---

# Simple by Design

Turn a goal into a decision record the user reviews before implementation.

A question is **material** when its answer affects required outcomes, behavior, contracts, ownership, risks, or constraints.

## Run

From the project root, drive the loop with `scripts/designflow.py` in this skill's directory:

1. New work only: `python3 <skill-dir>/scripts/designflow.py start` on Linux/macOS, `python <skill-dir>/scripts/designflow.py start` on Windows. It adds a session and keeps earlier sessions.
2. Do the printed step, then run the printed `done` command. It carries `--session`.
3. Repeat until the script prints `DONE`. Then present its summary and stop for user review.
4. To resume, especially after compaction: `status` lists active sessions; `status --all` adds closed sessions; `status --session sN` shows one. Never run `start` to resume.

If several sessions are active, pass `--session sN` to `done`. Close a stale run with `abandon --session sN`.

## Files

All under `.agents/design/`:

- `decisions.json`: ongoing record; one set per goal. Schema: `references/decisions.schema.json`.
- `workflow.json`: permanent `{version, sessions[]}` registry; script owns it. Sessions are never removed.
- `workflow.lock`: short-lived lock directory around `workflow.json` writes.

## Format

- `G#` goal set; `D#` stable ID within its goal.
- Read `decisions.json` before each edit. Edit only the current session's goal; leave every other goal unchanged.
- `status`: `open` or `resolved`; `answer` required when resolved.
- Optional: `after` (dependency D#s), `rationale` (reason for non-obvious choices).

```json
{"goals": [{
  "id": "G1",
  "goal": "Ship an inventory UI matching the existing app.",
  "constraints": ["Preserve existing API and visual language."],
  "decisions": [
    {"id": "D1", "question": "State authority?", "status": "resolved", "answer": "Server."},
    {"id": "D2", "after": ["D1"], "question": "Updates?", "status": "resolved",
     "answer": "Optimistic with rollback.", "rationale": "Instant UI; server stays authoritative."},
    {"id": "D3", "after": ["D2"], "question": "Conflict behavior?", "status": "open",
     "rationale": "Goal sets no merge policy."}
  ]
}]}
```
