# JavaScript profile

Top rule: Check maintained code statically and validate runtime boundaries.

## 1 Structure

- Default: group behavior and data by capability, without a mandatory folder tree.
- Default: expose named module APIs; keep implementation exports private.
- Default: use ESM for greenfield code; migrate CommonJS only within scope.

## 2 Preferred

- Default: use checked JSDoc with TypeScript `checkJs` for maintained code.
- Requirement: validate untrusted JSON, configuration, and user input at ingress.
- Default: model states and ordinary business outcomes as tagged objects.
- Default: reserve exceptions for operational failures; translate at adapters.
- Default: use plain functions, explicit return shapes, and injected collaborators.
- Default: use synchronous logic first; promises for asynchronous I/O.
- Requirement: own async work, await completion, propagate cancellation,
  and observe failures, including during shutdown.

## 3 Disallowed

- Requirement: no implicit globals or unchecked boundary data.
- Default: avoid `eval`, prototype mutation, and behavior-hiding inheritance.
- Default: avoid mutable module state; make state ownership explicit.
- Requirement: do not silence maintained-code type errors with blanket exclusions.
