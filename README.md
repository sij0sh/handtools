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

Needs Python 3.9+ (standard library only). Pi checks `~/.agents/skills/` and a
project's `.agents/skills/`:

```bash
git clone https://github.com/sij0sh/simple-by-design.git ~/.agents/skills/simple-by-design
```

Keep `SKILL.md`, `scripts/`, `references/`, and `languages/` together.

## Quick start

```text
/skill:simple-by-design Design an inventory UI matching the existing app. Stop for review.
```

You get `.agents/design/decisions.json` (settled and open decisions with
reasons) and a plain-language `decisions.md`. No implementation code.

## Files it writes

In `.agents/design/`:

- `decisions.json`: ongoing record, one set per goal.
- `workflow.json`: current run state; deleted when done.
- `decisions.md`: plain-language summary, rewritten each run.

## What's inside

| File | Covers |
|---|---|
| `SKILL.md` | How to run the loop, record format |
| `scripts/designflow.py` | Loop state machine, source precedence, reference routing |
| `references/decisions.schema.json` | Shape of `decisions.json` |
| `references/defaults.md` | Defaults every run starts from |
| `references/contract.md` | Ownership, dependencies, state, failures, tradeoffs |
| `references/workflow.py` | Template script for Workflow skills |
| `languages/*.md` | TypeScript, JavaScript, Python, Go, Rust, Java, C#, C, C++, SQL, skills |

Profile rules are tagged **Requirement**, **Default**, or **Heuristic**.

The skill stops at decisions. It doesn't write, review, or test code.

## Uninstall

```bash
rm -rf ~/.agents/skills/simple-by-design
```

Decision records and project code stay.

## More

- [Skill entrypoint](SKILL.md)
- [Loop script](scripts/designflow.py)
- [Defaults](references/defaults.md)
- [Contract](references/contract.md)
- [Language profiles](languages/)
- [Changelog](CHANGELOG.md)
