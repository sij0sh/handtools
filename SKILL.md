---
name: simple-by-design
description: Turn a goal into the smallest comprehensive set of implementation decisions.
disable-model-invocation: true
---

# Simple by Design

Resolve decisions until two competent implementers, following all adopted decisions, cannot make materially different choices affecting required outcomes, behavior, contracts, ownership, risks, or constraints.

## Policy

Read `references/defaults.md`. Honor requirements and adopted decisions first. In brownfield work, preserve compatible existing designs; treat observed patterns as evidence, not mandates. Use defaults elsewhere.

Read other standards or language references when relevant to a decision. Adopt reasonable choices directly. Ask the user only when essential intent, permissions, or consequential tradeoffs cannot be inferred.

Prefer the simplest adequate choice.

## References (as needed)

When a material decision involves established coding standards, consult only the relevant reference:

| Decision concerns | Read |
|---|---|
| Ownership, contracts, dependencies, boundaries, or failures | `references/contract.md` |
| Language-specific design, types, errors, or concurrency | `languages/<language>.md` |

Use relevant project conventions first. Open references only when they could affect the decision; do not treat them as mandatory checklists or introduce requirements unrelated to the goal.

## Loop

1. **Ground:** Establish the goal, constraints, success criteria, and relevant existing decisions or implementations.
2. **Branch:** Identify unresolved material questions. Add dependencies only where necessary.
3. **Decide:** Resolve questions whose dependencies are settled. Adopt the simplest adequate choice, briefly explaining non-obvious tradeoffs. Add resulting questions; discard irrelevant branches.
4. **Challenge:** Imagine two competent implementers following every decision. If they could diverge materially, identify the missing decision and repeat from step 2. Otherwise stop.

Repeat until no material questions remain. When a decision changes, reconsider dependent decisions. If blocked by missing intent or evidence, leave the question open, explain why, and continue independent branches.

## Record

For small tasks, record decisions in the response. For persistent work, use `.agents/design/decisions.md`. Example:

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

**Format:**
- `[x]` resolved; `[ ]` open.
- `D#` stable decision ID.

## Scope

Stop at the decisions and a concise handoff. Do not implement.
