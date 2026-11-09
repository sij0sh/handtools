---
name: untangle
description: Audit a whole codebase for avoidable complexity in bounded, resumable stages; publish behavior-preserving (A) and behavior-change (B) simplification recommendations. Recommends only.
disable-model-invocation: true
---

Set `S` to this skill's absolute directory. From the project root, drive the run with `S/scripts/workflow.py` (`python3` on Linux/macOS, `python` on Windows). The design rules come from `S/../_engine/policy/`; the script finds them.

1. `start`; do the printed stage, then run the printed `done` command, piping JSON when asked.
2. Repeat until `DONE`. Lost the current stage: `status`.
