# Java profile

Top rule: Use concrete services and explicit value contracts.

## 1 Structure

- Default: organize by capability, not global controller/service/repository layers.
- Default: keep implementation classes and constructors package-private where
  callers need no access; expose intentional APIs and invariant-safe construction.
- Heuristic: add packages/modules only for a real boundary, not every capability.

## 2 Preferred

- Default: use records for values and concrete services with constructor injection.
- Requirement: declare and check nullability using the repository's supported scheme.
- Default: represent ordinary business outcomes as values, not exceptions.
- Default: use specific exceptions for operational failures; preserve causes.
- Requirement: use try-with-resources for owned closeable resources.
- Default: synchronous calls first; concurrency only for demonstrated need.
- Requirement: own concurrent work, cancel/shut down and join it, and observe
  failures; use supported structured APIs or explicit executor/future lifecycles.
- Heuristic: add interfaces only for real consumer contracts or substitution.

## 3 Disallowed

- Default: avoid interface-per-class, field injection, and redundant DTO chains.
- Requirement: do not hide nullability violations or swallow broad exceptions.
- Default: keep framework annotations out of business values where practical.
