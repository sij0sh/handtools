# C# profile

Top rule: Use nullable-aware values, concrete services, and owned Tasks.

## 1 Structure

- Default: group code by capability; no project or layer required per capability.
- Default: keep implementation types `internal`; expose only intentional APIs.
- Heuristic: split projects for real dependency or deployment boundaries.

## 2 Preferred

- Default: enable nullable reference types and treat new warnings as errors.
- Default: use records for values and concrete services with constructor injection.
- Default: represent ordinary business outcomes as values, not exceptions.
- Default: use specific exceptions for operational failures; preserve causes.
- Requirement: use `using`/`await using` for owned disposable resources.
- Default: synchronous logic first; use `Task` for asynchronous operations.
- Requirement: propagate `CancellationToken`; own, cancel, and await spawned work
  and observe failures, including during shutdown.
- Heuristic: add interfaces only for real consumer contracts or substitution.

## 3 Disallowed

- Requirement: no sync-over-async (`.Result`, `.Wait()`, blocking await bridges).
- Default: avoid `async void` except required event handlers with observed failures.
- Default: avoid interface-per-class, service locators, and redundant DTO chains.
- Requirement: no unchecked null-forgiving assertions at untrusted boundaries.
