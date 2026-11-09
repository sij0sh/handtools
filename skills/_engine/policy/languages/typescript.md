# TypeScript profile

Top rule: Preserve type safety at runtime boundaries.

## 1 Structure

- Default: group types and behavior by capability; no prescribed folder tree.
- Default: expose a small module entry; keep implementation exports private.
- Heuristic: split packages only for an actual dependency or deployment boundary.

## 2 Preferred

- Default: enable `strict`, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes`.
- Requirement: accept untrusted input as `unknown`; validate before domain use.
- Default: use discriminated unions for states and ordinary business outcomes.
- Default: reserve exceptions for operational failures; translate at adapters.
- Default: use plain functions, immutable values, and explicit public return types.
- Heuristic: introduce interfaces only for real consumer contracts.
- Default: synchronous logic first; use promises for asynchronous I/O.
- Requirement: own async work, await completion, propagate cancellation,
  and observe failures, including during shutdown.

## 3 Disallowed

- Requirement: no unchecked `any`, assertions, or suppression at ingress.
- Default: avoid recursive generic frameworks and global type dumping grounds.
- Requirement: keep runtime validation even when static types appear sufficient.
