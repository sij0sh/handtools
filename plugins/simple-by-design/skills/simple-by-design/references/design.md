# Design defaults

## Common

Choose the smallest conventional adequate solution; prefer reversible ties. Use plain functions, data and composition. Give each rule/state one authoritative owner; direct dependencies one way. Keep public contracts small; specify boundary inputs, outputs, errors, effects and lifetimes. Validate untrusted ingress, not every internal call. Name resource cleanup owners. Own spawned work: cancel/shut down, join, observe failures, including shutdown; cancellation or dropped handles alone do not establish termination. Add abstractions/concurrency for present needs, not speculation.

Defaults guide current choices, not unrelated cleanup, fixed versions, layouts or tooling. Project requirements/conventions outrank preferences, never correctness/safety. Evidence of defects defeats precedent; explain departures. Missing facts are not established conventions.

## Languages

Consult relevant rows, including when a convention seems settled. For unlisted languages use common contracts and project evidence, not invented profiles.

| Language | Decision edges |
|---|---|
| C | Pair buffers/sizes; check overflow, bounds, termination; specify allocation ownership and failure output state. |
| C++ | RAII; values/unique ownership; borrowed views must not outlive storage or invalidating mutations. |
| C# | Nullable contracts; using/await using; cancellation and awaited Tasks; no sync-over-async. |
| Go | Explicit errors, %w, errors.Is/As; consumer interfaces; owned goroutines; handle material Close errors. |
| Java | Concrete services; explicit nullability; try-with-resources; executor/future shutdown, join and observed failures. |
| JavaScript | Checked maintained code; validated ingress; tagged outcomes; owned, awaited, cancellable promises. |
| Python | Typed boundaries/functions; plain data/functions; context managers; owned tasks/threads; preserve specific failure causes. |
| Rust | Result/Option; borrow before cloning; traits for real contracts; documented/tested unsafe invariants; no unproven unwrap/expect. |
| SQL | Constraints, parameterization; exact money and explicit NULL/time semantics; transactions/retries; expand-contract migrations with recovery. |
| TypeScript | Strict types; validate unknown ingress at runtime; tagged outcomes; owned promises; no unchecked boundary assertions. |

## Agent instructions

Add a rule only with an identifiable trigger, changed decision and observable outcome. Remove words that change none.
