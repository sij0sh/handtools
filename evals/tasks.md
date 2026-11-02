# Eval tasks

Run independent clean copies; use TypeScript and Python separately. Record
revision, tools, baseline checks, the decision record, final diff and checks.
Score completed work with `rubric.md`.

## Design setup

Run the loop. Read `references/defaults.md`, adopt routine defaults with a one-line
reason each, and record them in `design/decisions.md`. Read a standards file only
when a decision turns on it. Inspect existing configuration; it owns mechanical
details, and profile commands are fallbacks. Ask only for indispensable intent or a
consequential tradeoff that cannot be inferred; record the answer. A stop for
approval is not completion.

## 1. Legacy scoped fix

Copy `fixture/`; run `fixture/seed-small-fix.sh <copy>`. Capture baseline failures.
Orders discounts round down; 6699 cents at 15 percent must total 5694. Fix orders,
add a regression assertion, leave billing unchanged. Run baseline and final checks,
including failing checks: distinguish the seeded failure, unrelated baseline
failures, unavailable checks, and introduced regressions. No new violations;
no global cleanup. Removing a check or accepting every failure is not a baseline.

## 2. Greenfield feature

Start an empty project in either language. Implement order quotes from lines
(unit cents and quantity) and a percentage discount, returning integer cents.
Accept 0-100 percent; reject negative prices, nonpositive quantities and invalid
discounts. Define the rounding contract explicitly. Test 0/100 percent, invalid
inputs and 6699 at 15 percent -> 5694. Select and record tools/coverage first.
Ownership and contract must be identifiable without mandatory layers, repositories,
interfaces, or directories. A single cohesive implementation can pass.

## 3. Second real variation

Continue task 2. Add a fixed-cent discount alongside percentage discount. Clamp
fixed discounts at subtotal; reject negative discounts. Keep existing percentage
behavior and API compatibility; add tests for both variants and overlarge fixed
discounts. Judge whether the resulting design is understandable locally, not
whether an abstraction was introduced. Leave unrelated code untouched.

## 4. Boundary change

Copy `fixture/`. Billing needs invoice total plus the total of its related order.
Record the orders contract and the billing -> orders direction before editing.
Implement through the declared contract, not orders internals; test success,
unknown invoice and unknown order. Orders owns order data; billing owns invoice
data. Verify unchanged existing behavior and no reverse edge/cycle. Consumers must
be able to use contract input types without importing undeclared implementation.

## 5. Existing owner extension

Copy `fixture/`. Add `getOrderLines` / `get_order_lines`, returning sku, quantity
and unit cents. Extend the declared orders contract; test success and
invalid/missing IDs. Billing stays unchanged.

## 6. Design-only probe

Start an empty project: a job that imports an order CSV and writes a monthly
revenue report. Design only; implement nothing.

The framing names none of the decisions a careless loop skips: duplicate row
policy, month bucketing (timezone and boundary), malformed-row handling, and
currency/precision of the output. Pass iff the record resolves the material ones
with reasons, the two-implementer challenge finds no remaining material
divergence, and the frontier is empty. Fail on invented trivia (naming, formatting,
tooling options) or a record that stops while a material branch is open.

## Interpretation

Requirements: acyclic dependencies, declared contracts, owned state, behavior/tests,
no new violations. Defaults: repository-selected layout/tools, adopted in the record.
Heuristics: diff size, duplication, abstraction count; inspect, do not gate on them.
Historical `results/` runs used obsolete stop-at-gate rules. They do not evaluate
these tasks or demonstrate long-term maintainability. Rerun before comparing.
