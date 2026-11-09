# Python profile

Top rule: Make function contracts and resource lifetimes explicit.

## 1 Structure

- Default: group modules by capability; no mandatory package or layer per feature.
- Default: keep module APIs small; use private names for implementation details.
- Heuristic: use a `src/` package layout when packaging/import isolation warrants it.

## 2 Preferred

- Default: type maintained functions, including business logic and boundaries.
- Default: use dataclasses for data; frozen dataclasses for value objects.
- Default: represent ordinary business outcomes as values, not exceptions.
- Default: raise specific exceptions for operational failures; preserve causes.
- Requirement: use context managers for resource acquisition and release.
- Default: use functions and concrete collaborators; Protocols for real contracts.
- Default: synchronous code first; async only for an actual concurrency need.
- Requirement: own tasks/threads, join them, provide cancellation or cooperative
  shutdown, and observe failures; use structured task groups where supported.

## 3 Disallowed

- Default: avoid import-time I/O, mutable globals, and behavior-hiding decorators.
- Requirement: narrow untyped third-party data before domain use.
- Requirement: do not swallow broad exceptions or abandon background tasks.
