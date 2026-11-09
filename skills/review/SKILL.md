---
name: review
description: Review a diff, a subsystem or a reported bug in bounded, resumable stages; confirm bugs only with a repeatable counterexample or a complete source argument, keep test gaps separate, and report coverage honestly. Report-only.
disable-model-invocation: true
---

Set `S` to this skill's absolute directory. From the project root, drive the run with `S/scripts/workflow.py [--root DIR] <command>` (`python3` on Linux/macOS, `python` on Windows). The checks come from `S/../_engine/audit/packs/`; the script finds them.

1. `start`; do the printed stage, then run the printed `done` command, piping JSON when asked.
2. Repeat until `DONE`. Lost the current stage: `status`.
3. `show [part]` prints run state from the journal (the printed steps already include what each needs).
4. `abandon` cancels the run; after FRAME it writes a report marked CANCELLED.

Never edit the project. Run only commands the user approved at FRAME, in a worktree or temp copy.
External contracts come from a shared recon snapshot (`S/../_engine/recon/cli.py`); recon completeness never counts as review coverage.
