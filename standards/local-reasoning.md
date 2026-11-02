# Local reasoning

`standards/contract.md` owns code rules. This file explains tradeoffs, not an
additional checklist. `SKILL.md` owns the design loop. Profiles only specialize
universal rules.

## The change test

A maintainer should quickly answer:

1. Where does this behavior belong?
2. Which inputs, state changes, dependencies, and failures affect it?
3. Which contracts and consumers could this change affect?
4. What focused verification demonstrates the intended behavior?

If answering requires reconstructing unrelated features, investigate ownership,
implicit dependencies, or an abstraction that hides more than it explains.

## Tradeoffs

- **Locality versus line count:** modest duplication can keep independent
  capabilities independent. Duplicating an authoritative business rule instead
  creates competing owners; keep that rule behind its owner's contract.
- **Structure versus ceremony:** a script may need a few functions; a library
  may need public symbols and private implementation; an application may need
  capability modules. Folders and projects are tools, not proof of separation.
- **Isolation versus indirection:** isolate I/O to test decisions directly.
  Add an interface only when it makes a real boundary or substitution clearer.
- **Consistency versus legacy:** selected conventions reduce repeated decisions.
  Baseline existing violations without extending them or forcing a rewrite.
- **Small diff versus clear change:** count affected owners and contracts, not
  just files. Legitimately cross-cutting changes can be large and understandable.

## Growth

Start with the smallest structure expressing today's ownership. As capabilities
vary, preserve independent changes before extracting shared machinery. Create a
new module when it clarifies an actual boundary; declare its contract and checks
at that point. Do not prebuild a speculative architecture.

Useful review signals: discoverability, dependency traceability, affected-owner
count, ease of focused tests, and ease of deleting obsolete behavior. Treat them
as evidence to explain, not quotas to optimize.
