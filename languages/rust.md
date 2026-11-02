# Rust profile

Top rule: Express state and ownership with types before adding abstractions.

## 1 Structure

- Default: group modules by capability; no crate or workspace required per feature.
- Default: expose small APIs; private items first, `pub(crate)` only when needed.
- Heuristic: split crates for real dependency, build, or distribution boundaries.

## 2 Preferred

- Default: use structs and enums for data, states, and business outcomes.
- Default: use typed `Result` for failure and `Option` for meaningful absence.
- Default: borrow before cloning; document ownership transfers at APIs.
- Heuristic: use traits for real contracts, not one trait per struct.
- Default: use `#[must_use]` where ignoring a value loses required work.
- Default: synchronous logic first; async only for an actual concurrency need.
- Requirement: own spawned tasks, cancel/shut down and join them, and observe
  failures; dropping a handle is not evidence of task termination.
- Requirement: keep `unsafe` small with documented safety invariants and tests.

## 3 Disallowed

- Requirement: no `unwrap`/`expect` on unproven fallible production paths.
- Default: avoid mutable statics and cloning to evade ownership design.
- Requirement: no undocumented unsafe invariants or unobserved task failures.
