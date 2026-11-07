---
name: simple-by-design
description: Record design decisions before implementing features, refactors, or ambiguous changes. Use anytime design decisions are needed.
disable-model-invocation: true
---

# Simple by Design

Turn a goal into a decision record the user reviews before implementation.

## Run

Set `S` to this skill's absolute directory. From the project root, drive the loop with `S/scripts/designflow.py`:

1. New work only: `python3 "$S/scripts/designflow.py" start` on Linux/macOS, `python "$S/scripts/designflow.py" start` on Windows. It adds a session and keeps earlier sessions.
2. Do the printed step, then pipe its JSON payload into the printed `done` command. It carries `--session`.
3. Repeat until the script prints `DONE`. Then present its summary and stop for user review.
4. To resume, especially after compaction: `status` lists active sessions; `status --all` adds closed sessions; `status --session sN` shows one. Never run `start` to resume.

If several sessions are active, pass `--session sN` to `done`. Close a stale run with `abandon --session sN`.

`.agents/design/decisions.json` is the project's decision record (ADR log). Commit it. If the script warns that it is ignored or untracked, show the user the printed `.gitignore` lines; do not edit `.gitignore` yourself. `show` prints the record as Markdown.
