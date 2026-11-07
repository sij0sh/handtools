---
name: simple-by-design
description: Record design decisions before implementing features, refactors, or ambiguous changes. Use anytime design decisions are needed.
---

# Simple by Design

Turn a goal into a decision record the user reviews before implementation.

## Run

From the project root, drive the loop with `scripts/designflow.py` in this skill's directory:

1. New work only: `python3 <skill-dir>/scripts/designflow.py start` on Linux/macOS, `python <skill-dir>/scripts/designflow.py start` on Windows. It adds a session and keeps earlier sessions.
2. Do the printed step, then pipe its JSON payload into the printed `done` command. It carries `--session`.
3. Repeat until the script prints `DONE`. Then present its summary and stop for user review.
4. To resume, especially after compaction: `status` lists active sessions; `status --all` adds closed sessions; `status --session sN` shows one. Never run `start` to resume.

If several sessions are active, pass `--session sN` to `done`. Close a stale run with `abandon --session sN`.
