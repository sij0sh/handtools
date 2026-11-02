---
name: simple-by-design
description: Turn a goal into the smallest sufficient set of implementation decisions. Use for design, planning, code review, legacy adoption, and consequential changes.
---

# Simple by Design

Design until two competent implementers, **following the same adopted decisions**, cannot make materially different choices about the goal's required outcomes, behavior, contracts, ownership, risks, or constraints. Different compliant internals are allowed. Optimize for *minimum sufficient decisions*, not exhaustive specification.

## Policy

Read `references/defaults.md`. Honor explicit requirements and approved decisions first. Prefer established compatible project choices in brownfield work; otherwise use the defaults. A pattern observed in code is evidence, not automatically an approved decision. Ask the user only about indispensable intent, permissions, or consequential tradeoffs that cannot reasonably be inferred. Adopt other recommendations directly and state them.

This file owns the loop; the files below own the rules. Open one only when a decision turns on it:

| Open | When a decision turns on |
|---|---|
| `standards/contract.md` | ownership, public contracts, dependency direction, trust boundaries, failures, resource lifecycle |
| `standards/local-reasoning.md` | ambiguous ownership or a contested abstraction |
| `languages/<language>.md` | language-specific types, errors, resources, concurrency, validation; one file, never a set |
| `templates/boundaries/<tool>` | configuring a boundary or layering check |

Record an adopted rule as an ordinary decision, e.g. `D4: Errors? -> specific exceptions; business outcomes as values (python profile)`.

## Loop

1. **Frame.** State the goal, scope, success criteria, hard constraints, and what differences would be material. Do not manufacture requirements.
2. **Ground.** Read only relevant existing decisions (e.g. `design/decisions.md`, repository standards records), contracts, comparable implementations, and evidence. In brownfield work, identify what must be preserved; reconcile desired behavior against actual behavior. In greenfield work, start from defaults.
3. **Branch.** Find unresolved *material* decisions. Use owners, inputs/outputs, state, interfaces, workflows, failure cases, and quality requirements as prompts - not a mandatory inventory. Add prerequisites only when an answer genuinely depends on another.
4. **Resolve frontier.** Address all open decisions whose prerequisites are resolved. For each, compare genuinely viable options (typically two), recommend and adopt the simplest adequate choice, state a brief reason, and note consequences. For a routine default, a one-line reason is enough. Remove branches made irrelevant; add new material questions discovered.
5. **Challenge.** Imagine two independent competent implementers obeying every adopted decision. Identify the *first material divergence*, not arbitrary coding differences. If found, add or reopen that decision and repeat from step 3. Otherwise finish.

**Control rule:** Repeat steps 3-5 until the frontier is empty AND the semantic challenge finds no material unresolved divergence. A passing structural check is not evidence of semantic completeness. If an essential question is blocked by missing user intent or unavailable evidence, say precisely what is blocked; proceed on unrelated branches. Do not spin or substitute guesses.

**Revision rule:** When a decision changes, reopen all decisions whose answers depend on it; re-evaluate their branches. Implementation contradictions re-enter the same loop.

## Record only what matters

For a small, one-off task, the decision record may stay in the response. For multi-step, shared, or revisable work, write one `design/decisions.md` file:

```md
# Goal
Ship an inventory UI consistent with the existing app.

## Constraints
Preserve the existing API and visual language.

## Decisions
- [x] D1: State authority? -> Server authoritative; shared consistency.
- [x] D2 (after: D1): Update behavior? -> Optimistic with rollback; existing app convention.
- [ ] D3 (after: D2): What happens on conflicting edits?
```

`[x]` means resolved; `[ ]` means open. `D#` is a stable identifier. `(after: D1, D2)` is optional and represents **decision dependencies**, not implementation task order. Record only consequential rationales or evidence. Do not require surface lists, full option matrices, per-decision files, or rejected-choice links.

For persistent records run `node <skill-dir>/scripts/frontier.mjs <repo>/design/decisions.md` after a round; it reports design-record state, not code checks (`scripts/verify.sh` does those). Exit 1 shows the next ready questions or stale descendants; exit 2 means malformed dependencies; exit 0 means **mechanically closed only**. Complete the semantic challenge before claiming design readiness.

## Scope and execution

- If asked to design only, stop at the decision record and a concise handoff; do not implement.
- If asked to implement, build the adopted design, verify changed behavior at the narrowest useful boundary, and reopen affected decisions if evidence contradicts them. Run `scripts/verify.sh` with the target repository as working directory; classify findings and new-versus-baseline failures per `workflows/review.md`.
- For UI, consider visual hierarchy and interaction states; for games, player-visible rules and state transitions; for pipelines, data contracts, retries, idempotency and recovery - only when material to the goal.
- No mandatory swarm. Delegate research or an independent challenge only when the problem's scale or uncertainty justifies the coordination cost. Delegate against a specific question and expected output, not a standing agent catalog.
