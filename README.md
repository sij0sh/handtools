# handtools

One repository for my agent skills, released as one plugin for Claude Code, Codex and pi.

| Skill | What it does |
|---|---|
| [simple-by-design](skills/simple-by-design/) | Records design decisions before implementation. Owns the shared design rules and the ADR log. |
| [untangle](skills/untangle/) | Audits a codebase for avoidable complexity using simple-by-design's rules. |
| [foundation](skills/foundation/) | Audits and bootstraps a repository's foundation; records ADRs in simple-by-design's log. |
| [build-skills](skills/build-skills/) | Creates or revises an agent skill. |
| [remember](skills/remember/) | Memory for coding agents from past sessions and commits. |

## Install

Install the whole bundle. The skills read each other's files as siblings under `skills/`.

| Harness | Install | Update |
|---|---|---|
| Claude Code | `/plugin marketplace add sij0sh/handtools`, then `/plugin install handtools@handtools` | Claude's `/plugin` screen flags updates; skills are `/handtools:<skill>` |
| Codex | `codex plugin marketplace add sij0sh/handtools`, then `codex plugin add handtools@handtools` | `codex plugin marketplace upgrade` |
| pi | `pi install git:github.com/sij0sh/handtools` | `pi update git:github.com/sij0sh/handtools` (plain `pi update` updates only pi) |

Do not also copy or symlink these skills into `~/.agents/skills` or `~/.claude/skills`. pi and Codex read
`~/.agents/skills` too, and pi keeps the first skill it finds with a given name, so an old copy hides the
installed one.

### Is an update available?

Claude Code tells you. pi and Codex do not for a skills-only package, so run:

```bash
python3 scripts/check.py   # from a checkout, or from the installed copy
```

It fetches every handtools git clone it finds (this checkout, pi's package clone, Codex's and Claude's
marketplace clones) and prints `update available ... run: <command>` for each one that is behind. It never
applies updates. Exit status: 0 current, 1 update available, 2 could not check.

## Develop locally

Test edits without pushing:

- Claude Code: `claude --plugin-dir /abs/path/to/handtools`
- pi: `pi install /abs/path/to/handtools` (a local path is live)
- Codex: `codex plugin marketplace add /abs/path/to/handtools` (Codex caches a copy; run `codex plugin marketplace upgrade` after edits)

## Shared rules: one owner

simple-by-design owns every rule other skills use. Nothing is copied:

- `skills/simple-by-design/references/defaults.md`, `contract.md`, `instructions.md`, and `languages/*.md`: the design rules untangle applies.
- `skills/simple-by-design/references/decisions.schema.json`: the one ADR definition. A project's ADR log is its committed `.agents/design/decisions.json`, written only by `designflow.py` (`record` for other skills, `show` to read).

A skill reaches them at `S/../simple-by-design/`, where `S` is the skill's own directory.

## Where skills keep state

The ADR log is committed in each project (`.agents/design/decisions.json`). Everything else a skill saves
between steps is per user, outside both the project and the installed skill (a plugin update replaces the
skill's folder):

```text
~/.agents/state/                     # $HANDTOOLS_STATE overrides; %USERPROFILE%\.agents\state on Windows
  decisions/<project key>/           # simple-by-design sessions (workflow.json), foundation.json
  untangle/<project key>/            # run state and <audit-id>/{current.md, audit.json, report.md}
  build-skills/<project key>/        # sessions, drafts, backups
  <skill>/<project key>/             # any skill built from build-skills' workflow template
```

The project key is `<folder name>-<8-hex hash of its absolute path>`, and each key folder has a
`project.json` naming its project. Moving a repo leaves its state behind; `mv` the key folder to follow it.
Each skill names its folder in one `AREA` constant; `skills/_engine/storage.py` owns the layout.

## One workflow engine

`skills/_engine/` is the one implementation of what the workflow skills share. It is a Python package, not a
skill (no `SKILL.md`):

| Module | Owns | Used by |
|---|---|---|
| `storage` | state root, project root and key, state dirs, atomic JSON, lock | all four |
| `cli` | quoting, the printed rerun command, the stdin payload, error printing | all four |
| `flow` | single-run `start`/`status`/`done`/`abandon`, given the skill's `steps` module | foundation, untangle, template |
| `sessions` | the multi-session registry (`s1`, `s2`, ...) | simple-by-design, build-skills |

A skill keeps only its own steps (prompts, checks, `advance`) and a thin launcher. The launcher walks up from
its own path to the first folder holding `_engine/`, so the same `from _engine import ...` works inside
handtools and in a skill build-skills generated elsewhere, which gets a vendored `scripts/_engine/` copy
refreshed on every revision. A new workflow skill inside handtools starts from
`skills/build-skills/templates/workflow/scripts/` (`workflow.py` + `steps.py`). `tests/test_bundle.py` fails if
an engine module is copied or edited into a skill, or a launcher stops resolving `skills/_engine/`.

## Release

1. Bump `VERSION` and the same version in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json` and `package.json`.
2. Add a `## [x.y.z] - YYYY-MM-DD` entry to [CHANGELOG.md](CHANGELOG.md).
3. Push and tag `vX.Y.Z`. Claude only offers an update when the version changes.

## Checks

```bash
python3 -m unittest discover -s tests                       # bundle guards
python3 -m unittest discover -s skills/_engine/tests
python3 -m unittest discover -s skills/simple-by-design/tests
python3 -m unittest discover -s skills/foundation/tests
python3 -m unittest discover -s skills/build-skills/tests
python3 -m unittest discover -s skills/remember/tests       # optional tree-sitter deps: skills/remember/requirements.txt
```

The bundle guards fail when a shared rule file or engine module is copied (even if edited), a launcher no longer
resolves `skills/_engine/`, a package breaks its declared import graph, a cited sibling path is missing,
a manifest version differs from `VERSION`, `skills/` changed since the last tag without a version bump,
the ADR schema and its validator disagree, or a skill's Codex invocation policy differs from its
`disable-model-invocation` flag. CI runs them on every push ([.github/workflows](.github/workflows/)).

Design decisions for this repo are in [.agents/design/decisions.json](.agents/design/decisions.json):
`python3 skills/simple-by-design/scripts/designflow.py show`.
