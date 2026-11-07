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

## Release

1. Bump `VERSION` and the same version in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json` and `package.json`.
2. Add a `## [x.y.z] - YYYY-MM-DD` entry to [CHANGELOG.md](CHANGELOG.md).
3. Push and tag `vX.Y.Z`. Claude only offers an update when the version changes.

## Checks

```bash
python3 -m unittest discover -s tests                       # bundle guards
python3 -m unittest discover -s skills/simple-by-design/tests
python3 -m unittest discover -s skills/foundation/tests
python3 -m unittest discover -s skills/build-skills/tests
python3 -m unittest discover -s skills/remember/tests       # optional tree-sitter deps: skills/remember/requirements.txt
```

The bundle guards fail when a shared rule file is copied (even if edited), a cited sibling path is missing,
a manifest version differs from `VERSION`, `skills/` changed since the last tag without a version bump,
the ADR schema and its validator disagree, or a skill's Codex invocation policy differs from its
`disable-model-invocation` flag. CI runs them on every push ([.github/workflows](.github/workflows/)).

Design decisions for this repo are in [.agents/design/decisions.json](.agents/design/decisions.json):
`python3 skills/simple-by-design/scripts/designflow.py show`.
