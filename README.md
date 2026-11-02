# Simple by Design

**A coding-agent skill: turn a goal into the smallest comprehensive set of
implementation decisions.**

A feature brief can leave owners, contracts, and failure behavior open. Two
competent implementers then follow the same brief and build materially different
systems.

## Problem

Design gaps show up late as duplicate rules, unclear owners, or incompatible
failure handling. More specification can add pages of detail without settling the
few decisions that change the result.

## Proof

A run ends with a decision record and a concise handoff:

```md
# Goal
Ship an inventory UI matching the existing app.

## Constraints
Preserve existing API and visual language.

## Decisions
- [x] D1: State authority? Server.
- [x] D2 (after: D1): Updates? Optimistic with rollback.
- [ ] D3 (after: D2): Conflict behavior?
```

D3 stays open because the goal does not settle conflicts. The skill reports the
gap and continues independent branches instead of inventing an answer.

The record is not the finish line. The challenge step asks whether two competent
implementers could still diverge materially. If they could, the missing decision
is added and the loop repeats.

## What changes

| Common shortcut | This skill |
|---|---|
| Start implementation from a feature brief | Resolve material decisions first, then hand off |
| Share similar code across capabilities | Keep small duplication when sharing would couple unrelated owners |
| Rewrite legacy code to fit a preferred pattern | Preserve compatible existing design; treat patterns as evidence |
| Judge simplicity by diff size | Judge unnecessary concepts and affected owners or contracts |
| Treat an empty question list as done | Run the two-implementer challenge; it decides completion |

## Install

No runtime dependencies; the skill is Markdown only.

Place the directory where your coding agent discovers skills. Pi scans
`~/.agents/skills/` and project `.agents/skills/`:

```bash
git clone https://github.com/sij0sh/simple-by-design.git ~/.agents/skills/simple-by-design
```

Keep `SKILL.md`, `references/`, and `languages/` together. Other agents use their
own documented skill directory.

The skill sets `disable-model-invocation: true`, so it loads only when invoked
explicitly. In Pi:

```text
/skill:simple-by-design Design an inventory UI matching the existing app. Record material decisions in .agents/design/decisions.md and stop for review.
```

Expected: a decision record with resolved and open rows, the reason for any
blocked question, and a handoff. No implementation code.

## Use

### The loop

```text
Ground -> Branch -> Decide -> Challenge
              ^                    |
              +--- material gap ---+
```

1. **Ground:** establish the goal, constraints, success criteria, and relevant
   existing decisions or implementations.
2. **Branch:** identify unresolved material questions. Add a dependency only when
   one answer depends on another.
3. **Decide:** settle questions whose dependencies are resolved. Adopt the
   simplest adequate choice and explain non-obvious tradeoffs. Add resulting
   questions; discard irrelevant branches.
4. **Challenge:** imagine two competent implementers following every decision. If
   they could diverge materially, identify the missing decision and repeat from
   step 2.

Repeat until no material questions remain. A changed decision reopens its
dependents. If intent or evidence is missing, leave the question open with the
reason and continue independent branches.

### References on demand

`references/defaults.md` is always read. Deeper rules load only when a decision
turns on them:

| Decision concerns | Read |
|---|---|
| Ownership, contracts, dependencies, boundaries, failures | [`references/contract.md`](references/contract.md) |
| Language design, types, errors, concurrency | `languages/<language>.md` |

Profiles: TypeScript, JavaScript, Python, Go, Rust, Java, C#, C, C++, SQL.

Use project conventions first. References are inputs to a decision, not mandatory
checklists, and should not add requirements unrelated to the goal.

### Rule strengths

Profile rules carry a strength label:

- **Requirement:** satisfy it unless the goal or an adopted decision says
  otherwise.
- **Default:** adopt when requirements leave room; prefer the smallest
  conventional, reversible choice.
- **Heuristic:** review prompt, not a gate. No line, file, or diff-size limits.

### Decision records

For a small task, record decisions in the response. For persistent work, use
`.agents/design/decisions.md`.

- `[x]` resolved; `[ ]` open.
- `D#` stable decision ID.
- `(after: D1)` optional dependency edge.

### Scope

The skill stops at decisions and a concise handoff. It does not write
implementation code. Implementation, review, and verification stay with the
calling workflow.

## Removal

Remove the skill directory or its search-path entry:

```bash
rm -rf ~/.agents/skills/simple-by-design
```

Decision records (`.agents/design/decisions.md`) and project code remain.

## Reference

- [Skill entrypoint](SKILL.md)
- [Defaults](references/defaults.md)
- [Contract](references/contract.md)
- [Language profiles](languages/)
- [Changelog](CHANGELOG.md)
