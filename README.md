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

## Shared planning and policy

`skills/_engine/` is a Python package, not an invokable skill. It owns the shared planning
contract (`planning.py`) and `policy/`: defaults, contracts, instruction design, language rules
and the ADR schema. Workflow skills use these directly; they never invoke simple-by-design.
The four workflow skills remain user-invoked only. Remember remains a read-only memory tool.

Planning grounds the goal and acceptance criteria, resolves material decisions, challenges gaps,
and checks readiness. No-choice plans are valid; blocking unknowns cannot pass readiness.
Generated staged skills enable `PLANNING = True`; the engine enforces readiness before work.

## State and recovery

The authoritative resumable state is a script-owned SQLite event journal under:

```text
~/.agents/state/<area>/<project-key>/events.sqlite3
```

`HANDTOOLS_STATE` overrides the root. The existing path-based project key is retained for compatibility;
use explicit `--root` consistently. Moving a checkout still requires moving its state directory.
A journal stream's `state.changed` events contain validated stage state, not independently edited JSON.
Read-only status does not append events. Legacy workflow JSON is read until the first mutation imports
it and retains a `.migrated` backup. Old binaries must not be used after migration; edits to old JSON
are never merged back. Legacy build-skills runs without a ready plan cannot advance: preserve drafts/backups, abandon, and restart from the current target. There is one authority per stream, with deterministic replay.

Project ADRs remain committed in `.agents/design/decisions.json` for team portability. Untangle's
`current.md`, `audit.json`, and final `report.md` are generated views. Drafts, backups and accepted
application bytes remain files because recovery needs their contents. Never edit generated views as
workflow state. Build-skills keeps design and review data inside its journal; status renders them.

Build-skills runs ground → design (staged output) → draft → review → apply → verify. Ground includes
a proportional ready plan even for prompt outputs. Review can send `replan: true` with a new ready
`plan` to revise the design within the same run. Accepted drafts are hashed; apply commits intent
before writing, checks target drift, then verifies installed bytes. Interrupted application remains
pending until reconciled. A retry requires the same accepted draft and unchanged pre/postimage bytes.
No live install is performed just by generating a skill.

## Event commands and transcript pilot

From the bundle root, use `python3 skills/_engine/engine.py --help`.
Explicit journal runs support start/append/status/history, expected revisions, retry IDs and a read-only
SQL query over `workflow_events`. Existing workflow CLIs use journal-backed state automatically.
Remember exposes `workflow_events`, `workflow_runs`, `workflow_decisions`, and `workflow_authorizations` through its usual read-only query interface.

A minimal explicit event run:

```bash
python3 skills/_engine/engine.py start --run example --expect-revision 0 --request-id example-start <<'JSON'
{"goal":"Explore a design"}
JSON
python3 skills/_engine/engine.py history --run example
python3 skills/_engine/engine.py query --sql 'SELECT run_id, revision, kind FROM workflow_events'
```

For a plan-only capture experiment, add `--backend transcript` before the command. Start emits a JSON
receipt without storing state. Provide every source using `--recording PATH` before status/append.
Append requires both `--expect-revision` and `--head` (the previous receipt's event ID), plus a stable
request ID. The exact reader supports direct engine command results in Codex, Claude Code and pi JSONL;
it includes explicitly selected current sessions. Examples in assistant prose are ignored. Invalid,
missing or conflicting chains fail. Status reports an **observed prefix**, not guaranteed durability.
The pilot has synthetic capture tests; live harness retention/flush guarantees are not established.
It is not the backend for filesystem application. Do not silently switch an existing run's backend.

## Runtime distribution

In-bundle skills share `_engine`. Generated external workflow skills receive one pinned copy under
`scripts/_engine/`, including planning policy and schema resources. The generator refreshes launcher
and runtime together; domain steps remain authored in `scripts/steps.py`. Generated prompt skills
remain prompt-only. Run model (`stateful`/resumable vs `stateless`/ephemeral) is independent of output
kind; resumable currently selects the journal, ephemeral writes no state. No sibling skill install is
required. Reject unsupported runtime versions rather than guessing a migration.

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
