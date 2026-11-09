---
name: foundation
description: Audit, plan, and bootstrap a repository's project foundation (toolchain versions, local services, CI, dependency updates, migrations, IaC, ADRs, architecture docs, secrets, onboarding) for greenfield or brownfield projects.
disable-model-invocation: true
---

Set `S` to this skill's absolute directory. From the project root, drive the run with `S/scripts/workflow.py` (`python3` on Linux/macOS, `python` on Windows):

1. `start`; run each printed stage as its own execution (fresh subagent when available), passing on the results it needs.
2. Run the printed `done --stage S`, piping JSON when asked; repeat until `DONE`.

`interview` and `assess` talk to the user; run them in the main context.

Scripts in `S/scripts/` take `--root <project root>`. `audit.py` and `validate.py` are read-only.

ADRs are decision rows in the project's `.agents/design/decisions.json`, defined by `S/../_engine/policy/decisions.schema.json`. Write them only through `S/../simple-by-design/scripts/designflow.py --root <project root> record`.

External contracts come from a shared recon snapshot recorded with `S/../_engine/recon/cli.py`; discover prints how. Pass its id (`recon_snapshot`) from discover to assess; foundation keeps no copy.

Pass each stage the user's request and the earlier stages' results.

## Rules for every stage

- Outcomes over tools: recommend a tool only to close a baseline gap; the smallest stack that does it wins.
- No file writes before the user approves specific items in `assess`.
- Never run repository scripts, tasks, hooks, or installers you have not read; never provision paid infrastructure, deploy, touch production, rotate secrets, or destroy resources.
