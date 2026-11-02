---
name: simple-by-design
description: Record design decisions before implementing features, refactors, or ambiguous changes. Use anytime design decisions are needed.
---

# Simple by Design

Turn a goal into a decision record the user reviews before implementation.

A question is **material** when its answer affects required outcomes, behavior, contracts, ownership, risks, or constraints.

## Precedence

Settle each question from the first source that answers it:

1. Requirements and adopted decisions.
2. Existing project conventions that fit the goal. Replace one only through an explicit decision.
3. `references/defaults.md` (read every run).
4. The relevant reference below.
5. The simplest adequate choice.

Ask the user when essential intent, permissions, or a consequential tradeoff stays unanswered by all five.

## References

Read a reference when a decision turns on its topic:

| Decision concerns | Read |
|---|---|
| Ownership, contracts, dependencies, boundaries, or failures | `references/contract.md` |
| Language-specific design, types, errors, or concurrency | `languages/<language>.md` |
| Skills, `AGENTS.md`, `CLAUDE.md`, or other agent instructions | `languages/agent-instructions.md` |

## Loop

**prerequisite** Rewrite `.agents/design/decisions.md` to briefly summarize its current state so prior work is condensed into a small historic record. 

1. **Ground:** Establish the goal, constraints, success criteria, and relevant existing decisions or code. Record to `.agents/design/decisions.md`.
2. **Branch:** List open material questions. Link a dependency when one answer requires another. Update `.agents/design/decisions.md`.
3. **Decide:** Resolve questions whose dependencies are settled, using Precedence. State the reason for each non-obvious choice. Add questions the answers raise; drop questions that became irrelevant. Update `.agents/design/decisions.md`.
4. **Challenge:** Imagine two competent implementers following every decision. If they could make materially different choices, add the missing questions. Update `.agents/design/decisions.md`. 

**loop** Repeat steps 2 through 4 until enough decisions are made that no two SWEs could implement a materially different solution following the decisions.

## Format 

- `[x]` resolved; `[ ]` open.
- `D#` stable ID.
- `(after: D#)` dependency.
- `- reason` after the answer for non-obvious choices; required on open rows.

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

## Handoff

Do one edit pass over the final `.agents/design/decisions.md` so it is understandable to someone new and unfamiliar with code.
