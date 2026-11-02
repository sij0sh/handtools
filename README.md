# Simple by Design

**A coding-agent skill that gets the big design choices on paper before any
code gets written, so you can check them first.**

## The problem

A coding agent makes a lot of decisions while it works. Who owns this data?
What shape is it? What happens when a call fails? Which library? Most of these
choices never get said out loud. You find them later, buried in the diff.

By then they are baked in. Review turns into guessing what the agent meant.
Changing course gets expensive. And two sessions given the same task can build
two different things.

## The fix

This skill makes the agent write those decisions down first, in a short list
you can read in a minute. You check the plan, then the code gets written.

Here is what a run produces:

```md
# Goal
Ship an inventory UI matching the existing app.

## Constraints
Preserve existing API and visual language.

## Decisions
- [x] D1: State authority? Server.
- [x] D2 (after: D1): Updates? Optimistic with rollback - instant UI; server stays authoritative.
- [ ] D3 (after: D2): Conflict behavior? Open - goal sets no merge policy.
```

Each line is one decision. `[x]` means settled, `[ ]` means still open, and
`(after: D1)` means it depends on an earlier one. Anything not obvious gets a
short reason. D3 stays open because the goal says nothing about conflicts. The agent flags the gap instead of making
something up.

How does it know when it's done? It imagines two good developers following the
list. If they could still build meaningfully different things, a decision is
missing, so it keeps going. When they couldn't, the list is complete.

## Why decide first

Fixing a design choice in a plan costs a sentence. Fixing it after it's in the
code costs a rewrite. Thinking choices through up front pays off in the result:

- **Fewer surprises.** You see what the agent intends before it builds it.
- **Better choices.** Each decision gets a moment of thought instead of being
  made on the fly mid-edit.
- **Honest gaps.** Unknowns show up as open questions, not hidden guesses.
- **Easier review.** You read what was intended, then check the code against
  it.

## Why coding standards

When a requirement doesn't settle something, the agent still has to pick. With
no standard, it picks differently each time. Over many sessions that adds up to
a codebase full of one-off habits that nobody, human or agent, can keep straight.

The skill ships a shared set of defaults so those picks stay consistent:

- **Same answer every time.** Similar problems get similar solutions across
  sessions and languages.
- **Easier to grow.** Clear owners and boundaries mean new code has an obvious
  place to go.
- **Easier to read.** Less to rediscover, so people and agents can understand a
  piece of code on its own.

Your project's existing conventions always come first. The defaults only fill
in what's left open.

## Before and after

| Without the skill | With the skill |
|---|---|
| Choices show up only in code | Choices show up in a list before code |
| Each session invents its own conventions | Shared defaults across sessions and languages |
| Review guesses at intent | Review reads intent |
| Growth piles up hidden conventions | Defaults keep owners and boundaries clear |

## Install

Nothing to install beyond the files. The skill is plain Markdown.

Put the folder where your coding agent looks for skills. Pi checks
`~/.agents/skills/` and a project's `.agents/skills/`:

```bash
git clone https://github.com/sij0sh/simple-by-design.git ~/.agents/skills/simple-by-design
```

Keep `SKILL.md`, `references/`, and `languages/` together. Other agents have
their own skill folder; check their docs.

## Quick start

Run it before you start building:

```text
/skill:simple-by-design Design an inventory UI matching the existing app. Record material decisions in .agents/design/decisions.md and stop for review.
```

You get a decision list with settled and open items, a reason for anything
left open, and a short handoff. No implementation code.

## What's inside

| File | What it covers | Why it helps |
|---|---|---|
| `SKILL.md` | Decision loop, source precedence, list format | Gets choices written down before code |
| `references/defaults.md` | Keep it simple, one owner per thing, local reasoning, clear boundaries | One starting point for every session |
| `references/contract.md` | Ownership, dependencies, state, resources, failures, tradeoffs | Keeps a growing system easy to follow |
| `languages/*.md` | Rules for 10 languages | Consistent choices per language |

The agent always reads the defaults. It opens the contract or a language file
only when a decision needs it.

### Language profiles

TypeScript, JavaScript, Python, Go, Rust, Java, C#, C, C++, and SQL. Each starts
with one top rule, then lists structure, preferred patterns, and patterns to
avoid. Rules are tagged by strength:

- **Requirement:** follow it unless the goal says otherwise.
- **Default:** use it when nothing else decides.
- **Heuristic:** a prompt to think, not a hard rule.

## What it doesn't do

The skill stops at decisions and a handoff. It doesn't write the code, review
it, or test it. That stays with you or your normal workflow.

## Remove it

Delete the folder:

```bash
rm -rf ~/.agents/skills/simple-by-design
```

Your decision records (`.agents/design/decisions.md`) and project code stay.

## More

- [Skill entrypoint](SKILL.md)
- [Defaults](references/defaults.md)
- [Contract](references/contract.md)
- [Language profiles](languages/)
- [Changelog](CHANGELOG.md)
