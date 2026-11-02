# Go profile

Top rule: Prefer concrete structs, explicit errors, and owned goroutines.

## 1 Structure

- Default: group cohesive packages by capability; no package required per feature.
- Default: use `internal/` for private packages and minimal exported APIs.
- Heuristic: use `cmd/<name>/` when multiple binaries need separate entry points.

## 2 Preferred

- Default: use concrete structs; small interfaces belong to their consumers.
- Default: return explicit values and errors; wrap causes with `%w`.
- Requirement: inspect wrapped errors with `errors.Is`/`errors.As`, not strings.
- Requirement: pass `context.Context` through cancellable I/O paths.
- Default: synchronous calls first; start goroutines for demonstrated concurrency.
- Requirement: every goroutine has an owner, cancellation/shutdown path, join,
  and observed failure; cancellation alone does not wait for termination.
- Requirement: close owned resources, normally with `defer`; handle material
  `Close` errors, especially when they determine write success.

## 3 Disallowed

- Default: avoid interface-per-struct and unrelated `util`/`common` packages.
- Requirement: do not use `panic` for ordinary business or operational failures.
- Requirement: do not discard errors or leave goroutines unowned.
