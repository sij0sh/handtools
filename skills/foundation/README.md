# foundation

Audit, plan, and bootstrap a repository's project foundation: pinned toolchains, one-command setup, tests and lint, CI, dependency updates, migrations, infrastructure as code, ADRs (in simple-by-design's `.agents/design/decisions.json`), architecture docs, secrets hygiene, and onboarding.

Part of the [handtools](../../README.md) bundle. An agent reads `SKILL.md`; `scripts/workflow.py` owns the stage order. ADRs use simple-by-design's decision record: `../simple-by-design/references/decisions.schema.json` defines them and `designflow.py record` writes them.

## Quick start

Requires Python 3.9+ (`python3` on Linux/macOS, `python` on Windows). Development tools are pinned with [mise](https://mise.jdx.dev/).

```sh
mise install
mise run check
python3 scripts/workflow.py start
```

Run each printed stage as its own execution, then pipe the JSON payload into `done --stage <stage>` until the workflow prints `DONE`.

| Stage | Purpose |
| --- | --- |
| `discover` | Read-only audit and project classification. |
| `interview` | Ask only the decisions the repo and record cannot answer. |
| `assess` | Classify every baseline capability, then propose fixes and ask what to apply. |
| `apply` | Implement only the approved items and write the decisions record. |
| `validate` | Run the approved checks and report what changed and what remains. |

`interview` and `assess` talk to the user; run them in the main agent context. `scripts/audit.py` and `scripts/validate.py` are read-only and never execute project code.

## Development

```sh
mise run test      # stdlib unittest suite
mise run lint      # ruff
mise run check     # lint + test
mise run audit     # read-only project audit
mise run validate  # read-only changed-file checks
```

The scripts must stay Python 3.9+ and standard-library-only; ruff is a development-only tool. `tests/test_imports.py` enforces the import rules.

## Layout

```text
SKILL.md                 agent-facing entrypoint and rules
scripts/workflow.py      CLI: start, status, abandon, done
scripts/workflowlib/     stages, CLI helpers, optional state storage
scripts/audit.py         read-only project scan (JSON)
scripts/validate.py      read-only changed-file checks (JSON)
references/              greenfield and brownfield rules
assets/                  mise, CI, and Renovate templates
docs/architecture.md     architecture overview
tests/                   unit and integration tests
```

## Status

CI runs from the handtools root workflow. `assets/ci.yml` and `assets/renovate.json` are templates for target projects. foundation's own design decisions are goal G2 in the handtools `.agents/design/decisions.json`.
