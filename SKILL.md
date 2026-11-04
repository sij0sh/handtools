---
name: simple-by-design
description: Record design decisions before implementing features, refactors, or ambiguous changes. Use anytime design decisions are needed.
---

# Simple by Design

Turn a goal into a decision record the user reviews before implementation.

A question is **material** when its answer affects required outcomes, behavior, contracts, ownership, risks, or constraints.

## Run

From the project root, drive the loop with `scripts/designflow.py` in this skill's directory:

1. Every time this skill runs: `python3 <skill-dir>/scripts/designflow.py start` on Linux/macOS, `python <skill-dir>/scripts/designflow.py start` on Windows. It replaces any unfinished workflow.
2. Do the printed step, then run the printed `done` command.
3. Repeat until the script prints `DONE`. Then stop for user review.
4. Lost the current step (e.g. after compaction): `status`.

## Files

All under `.agents/design/`:

- `decisions.json`: ongoing record; one set per goal. Schema: `references/decisions.schema.json`.
- `workflow.json`: current run; script owns it. Removed when done.
- `decisions.md`: plain-language view; removed and rewritten once at handoff.

## Format

- `G#` goal set; `D#` stable ID within its goal.
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
