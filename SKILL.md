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

Language rule labels:
- **Requirement:** follow unless a requirement or adopted decision overrides it.
- **Default:** use when higher sources leave the choice open.
- **Heuristic:** a prompt to consider; use judgment.

## Loop

1. **Ground:** Establish the goal, constraints, success criteria, and relevant existing decisions or code.
2. **Branch:** List open material questions. Link a dependency when one answer requires another.
3. **Decide:** Resolve questions whose dependencies are settled, using Precedence. State the reason for each non-obvious choice. Add questions the answers raise; drop questions that became irrelevant.
4. **Challenge:** Imagine two competent implementers following every decision. If they could make materially different choices, add the missing question and return to step 2. Stop when they could not.

When a decision changes, revisit its dependents. When intent or evidence is missing, leave the question open with the reason and continue independent branches.

## Record

Record decisions in the response for small tasks. Use `.agents/design/decisions.md` for persistent work. Example:

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

**Format:**
- `[x]` resolved; `[ ]` open.
- `D#` stable ID.
- `(after: D#)` dependency.
- `- reason` after the answer for non-obvious choices; required on open rows.

## Handoff

End with the record and a short handoff: open questions needing the user, and the next step. Implementation starts after the user reviews the record.
