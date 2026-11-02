# Coding contract

Optimize for local reasoning: predictable change scope, explicit behavior, clear
ownership, and focused verification. Small diffs and fewer lines are signals,
not the objective. This file owns universal rules; language profiles specialize
them. `SKILL.md` owns the design loop.

## Requirements

- Give each capability an authoritative owner for its behavior, business rules,
  and mutable state. Expose state changes through that owner's contract.
- Keep module dependencies explicit and acyclic. Cross-module access uses
  declared public contracts, never another owner's internals or mutable state.
- Validate untrusted inputs at trust boundaries. Internal code may rely on
  established guarantees; revalidate when trust or assumptions change.
- Make failures, side effects, and resource ownership visible. Concurrent work
  has an owner, an end condition, and observed failures.
- Verify changed behavior and invariants at the narrowest useful boundary.
  Tests inside an owner may exercise its internals; consumer tests use its API.
- Preserve correctness and safety. Existing defects do not justify new ones.

A module is a cohesive ownership boundary, not necessarily a package or folder.
Its public contract may be declared symbols, paths, or interfaces; define which
in the repository's adopted standards. Ownership includes libraries, scripts,
UI, systems, and data work, not only business services.

## Defaults

- Organize by capability. Keep behavior, supporting types, and tests nearby
  within language/build constraints. Start with functions and files; add
  directories, packages, or layers for actual ownership, dependency, build,
  tooling, or deployment needs.
- Separate business decisions from external I/O where that enables direct
  testing. Keep adapters thin without requiring a layered architecture.
- Prefer concrete functions and data, composition, explicit inputs/outputs,
  guard clauses, and shallow nesting. Avoid flags selecting unrelated jobs.
- Keep mutation narrowly owned. Expose dependencies on time, randomness,
  configuration, and I/O where behavior depends on them.
- Extract a shared concept or independently useful boundary, not merely similar
  syntax. A little duplication is cheaper than unrelated feature coupling;
  one business rule still needs one authoritative owner.
- Introduce interfaces for real substitution or boundary isolation; generic
  frameworks for demonstrated variation. Justify new dependencies and layers.
- Use meaningful names. Comments explain constraints and reasons. Delete
  obsolete machinery within scope; avoid unrelated refactors.
- Represent ordinary outcomes explicitly; use idiomatic language mechanisms for
  failures. Do not swallow failures or convert defects into ordinary outcomes.

## Authority and exceptions

Requirements are mandatory. Stop on conflicts and obtain a design decision;
architectural exceptions require approval, scope, and rationale. Temporary
exceptions also need a revisit condition. Safety and correctness cannot be waived.

Defaults are the normal choice. Concrete local reasons can justify alternatives;
record consequential or recurring deviations in the adopted standards. Suitable
repository conventions inform adoption, but do not silently override it. Profile
requirements specialize this contract; profile defaults are selectable, not bans.

Existing violations need an explicit, bounded baseline, not a blanket exception.
Introduce no new violations, including in touched legacy code; improve existing
ones within task scope. Propose larger migrations separately.

## Heuristics and tie-breaker

Function size, nesting, parameter counts, duplication, file counts, and change
surface prompt investigation, not numeric pass/fail limits. Prefer the correct
solution requiring the least unrelated context, fewest unnecessary concepts,
and most predictable change scope. A justified larger diff may be clearer.
