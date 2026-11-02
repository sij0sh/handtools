# SQL profile

Top rule: Enforce data invariants and make table ownership explicit.

## 1 Structure

- Requirement: identify one owning capability for each table and its write API.
- Default: group migrations and queries by capability without requiring a schema
  or directory per capability; schema names alone do not enforce ownership.
- Default: keep views/functions with their owner and migrations ordered and focused.

## 2 Preferred

- Requirement: enforce applicable primary/foreign keys, uniqueness, not-null,
  and check constraints; application validation does not replace database invariants.
- Requirement: parameterize data values; allowlist identifiers that cannot be bound.
- Default: list query columns explicitly and qualify cross-schema object references.
- Requirement: use exact decimal or integer minor units for money, with defined
  currency/scale/rounding; define NULL meaning and timestamp/time-zone semantics.
- Requirement: define transaction scope, isolation, and conflict/retry semantics
  for multi-step invariants; keep external side effects out of retried transactions.
- Default: evolve deployed schemas with expand-contract migrations; stage backfills
  and compatibility windows before removing old columns or constraints.
- Requirement: plan recovery for destructive migrations; respect engine DDL semantics.
- Heuristic: add indexes for demonstrated query/constraint needs, not every column.

## 3 Disallowed

- Requirement: no cross-owner base-table writes bypassing the declared interface.
- Requirement: no implicit casts or ambiguous NULL/time semantics changing correctness.
- Default: avoid trigger-hidden business workflows and destructive one-step rollouts.
