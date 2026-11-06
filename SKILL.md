---
name: saaw
description: Create or revise an agent skill.
disable-model-invocation: true
---

From the project root, drive the run with `scripts/saaw.py` in this skill's directory (`python3` on Linux/macOS, `python` on Windows):

1. `start` adds a session.
2. Do the printed step, then pipe its JSON payload into the printed `done` command.
3. Repeat until `DONE`; present the summary and stop for review.
4. Resume with `status`; close a stale session with `abandon --session sN`.
