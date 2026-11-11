# semantic-instructions

Agent skill that creates, edits, reviews, or simplifies instructions written for AI agents: prompts, `SKILL.md`, `AGENTS.md`, agent definitions, workflow stages, and evaluation instructions.

It runs a three-phase workflow — Frame → Compose → Challenge — through a small state engine that enforces reading before writing and requires an evidenced challenge. Challenge is a single review: the engine never revises or writes the target instruction, and the calling agent decides whether to act on a revision recommendation.

## Requirements

- Python 3.11+
- POSIX (Linux, macOS); the engine uses `fcntl`
- Standard library only — no install step, no dependencies, no lockfile

## Install

Install the `handtools` monorepo package, or copy this directory into your harness
skill folder. See the repository root `README.md` for Pi and Claude Code install
and update commands.

Model invocation is disabled in `SKILL.md`; invoke the skill explicitly.

## Usage

From the project whose instructions you want to change:

```sh
S=~/.agents/skills/semantic-instructions
python3 "$S/scripts/semantic_flow.py" --request '<request>'
```

Follow the printed phase prompt and return JSON through the printed command. Re-running without `--request` resumes the active run. The engine keeps state in `.agents/semantic-instructions.json` under the project root; add `.agents/` to that project's `.gitignore`.

## Layout

- `SKILL.md` — trigger and invocation contract
- `references/details.md` — phase contract
- `references/principles.md` — instruction-design principles
- `scripts/semantic_flow.py` — state engine (stdlib only)
- `tests/test_semantic_flow.py` — unittest suite

## Test

```sh
python3 -m unittest discover -s tests -v
```

## Distribution

Version lives in `VERSION`. Bump the patch version with each change and copy or pull the repo into the skills directory; there is no package registry, build step, or installer.

## License

MIT — see `LICENSE`.
