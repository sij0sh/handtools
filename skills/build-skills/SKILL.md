---
name: build-skills
description: Create or revise an agent skill.
disable-model-invocation: true
---

Set `S` to this skill's absolute directory. From the project root, drive the run with `S/scripts/build-skills.py` (`python3` on Linux/macOS, `python` on Windows):

1. `start` adds a session; do the printed step, then pipe its JSON payload into the printed `done` command.
2. Repeat until `DONE`; present the summary and stop for review.
3. Resume with `status`; close a stale session with `abandon --session sN`.
