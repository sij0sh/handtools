---
name: untangle
description: Audit a whole codebase for avoidable complexity in bounded, resumable stages; publish behavior-preserving (A) and behavior-change (B) simplification recommendations. Recommends only.
disable-model-invocation: true
---

Set `S` to this skill's absolute directory. From the project root, drive the run with `S/scripts/workflow.py` (`python3` on Linux/macOS, `python` on Windows). The design rules come from `S/../_engine/policy/`; the script finds them.

1. `start`; do the printed stage, then run the printed `done` command, piping JSON when asked.
2. Repeat until `DONE`. Lost the current stage: `status`.
3. `show [part]` prints run state from the journal (the printed steps already include what each needs).
4. `start --continue <audit-id>` begins a successor of a closed audit; reviews of unchanged units carry over.

External contracts come from a shared recon snapshot (`S/../_engine/recon/cli.py`); MAP pins a closed one or
states why none is needed. Recon completeness never counts as review coverage.
