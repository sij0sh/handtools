# Simple by Design

**Records each design decision and its reason before coding, so your agent builds your intent instead of winging it.**

Yes... yet another planning skill that, at a glance, may look redundant next
to the one you already use.

Intent is the difference between your vision and AI slop. Even with
disciplined harness steering, your agent makes a surprising number of 
decisions as it implements. This skill aims to tackle that bottleneck through
a simple but intentional agentic workflow.

Most plans list steps. This one lists decisions, each with a reason, and won't
let your agent stop while any are still open:

```text
PHASE: CHALLENGE  |  LOOP: 1
...
ERROR: 2 open decision(s) remain: D2, D3.
PHASE: BRANCH  |  LOOP: 2
```

## Why it's useful

| A typical plan | With Simple by Design |
|---|---|
| Steps to build | Decisions to build from, each with a reason |
| Agent picks silently mid-edit | Choices you skim before code |
| Gaps hidden as guesses | Gaps shown as open questions |
| Each session invents its own habits | Same house rules every session |

## What makes it different

- **It knows when to stop.** If two good developers could follow the
  decisions and still build different things, something is missing, so it
  loops again.
- **It stays on track.** A skill alone is one long prompt, and your agent
  starts skipping steps as its memory fills. Here a small script hands over
  one step at a time and won't move on until the decision list changes.
- **It respects your project.** Your requirements and existing habits come
  first; built-in defaults only fill what's left.

## Install

Part of the [handtools](../../README.md) bundle; install the bundle, not this
folder alone. untangle and foundation read this skill's references and
schema from the sibling folder. Needs Python 3.9+ (standard library only).
Use `python3` on Linux/macOS and `python` on Windows.

## Quick start

```text
/skill:simple-by-design Design an inventory UI matching the existing app. Stop for review.
```

You get `.agents/design/decisions.json` (settled and open decisions with
reasons) and a plain-language summary when the run closes. No implementation
code.

## The decision record is the ADR log

`decisions.json` is the project's architecture decision record, shared with
the foundation skill. [`references/decisions.schema.json`](references/decisions.schema.json)
is its one definition: each goal is the decision context (goal, constraints,
criteria) and each decision row is one ADR (question, answer, rationale,
`after`, `date`, `superseded_by`). Status is derived: `open`, `resolved`, or
`superseded`. `G#/D#` cites a decision in another goal.

Commit `decisions.json`. Keep session state out of git with:

```gitignore
.agents/*
!.agents/design/
.agents/design/*
!.agents/design/decisions.json
```

The script warns, at close and on `record`, when the file is ignored or
untracked. It never edits `.gitignore`.

- `show [--goal G1]` prints the record as Markdown. It is read-only.
- `record [--goal G1]` upserts one goal from a JSON payload on stdin, without
  a session. Rows without an `id` get the next `D#`. Other skills use it, so
  the script stays the only writer. It refuses a goal an active session holds.

## Several runs

Each `start` adds a short session ID and keeps every earlier session. Use
`status` to list active runs, `status --all` to include closed ones, and
`status --session s1` to show one. `done --session s1` advances it, reading
that step's edits as JSON on stdin;
`abandon --session s1` closes a stale run. Completed and abandoned sessions
stay in `workflow.json` for review.

## Settings

Optional, in `SKILL.md` frontmatter:

```yaml
metadata:
  max-challenges: 3   # challenge rounds per session; default 3
```

At the limit the session closes; gaps the last challenge leaves open get one
final decide, and anything still open is listed in the summary.

## Files it writes

All owned by the script; the agent edits them only through `done`.

- `<project>/.agents/design/decisions.json`: the decision record (ADR log), one set per goal. Commit it.
- `~/.agents/state/decisions/<project key>/workflow.json`: permanent `{version, sessions[]}` registry, per user.
- `~/.agents/state/decisions/<project key>/workflow.lock`: short-lived lock directory around writes.

`$HANDTOOLS_STATE` replaces `~/.agents/state`. The project key is `<folder name>-<8-hex hash of its path>`;
`project.json` beside it names the project. After moving a repo, move its key folder by hand.

## What's inside

| File | Covers |
|---|---|
| `SKILL.md` | How to run the loop |
| `scripts/designflow.py` | Command line: arguments, stdin payload, printed commands |
| `scripts/designlib/` | Loop internals: `flow` (phases, `record`, `show`), `steps` (prompts, output), `sessions` (`workflow.json`), `record` (`decisions.json`), `storage` (paths, lock), `gitcheck` (is the record committed), `config` (`SKILL.md` settings) |
| `references/decisions.schema.json` | The ADR definition: shape of `decisions.json` |
| `references/defaults.md` | Defaults every run starts from |
| `references/contract.md` | Ownership, dependencies, state, failures, tradeoffs |
| `references/instructions.md` | Semantic instructions: designing skills, prompts, `AGENTS.md` |
| `languages/*.md` | TypeScript, JavaScript, Python, Go, Rust, Java, C#, C, C++, SQL |

Profile rules are tagged **Requirement**, **Default**, or **Heuristic**.

The skill stops at decisions. It doesn't write, review, or test code.

## More

- [Skill entrypoint](SKILL.md)
- [Loop script](scripts/designflow.py)
- [Defaults](references/defaults.md)
- [Contract](references/contract.md)
- [Language profiles](languages/)
- [Changelog](../../CHANGELOG.md)
