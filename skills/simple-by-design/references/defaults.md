# Defaults

Use when requirements, adopted decisions, and project conventions leave a choice open.

1. **Keep it simple.** Choose the smallest conventional solution that meets current needs. Add an abstraction or layer when a present need requires it.

2. **One owner.** Each behavior, each business rule, each piece of mutable state has exactly one authoritative owner. Other code does not keep a second copy that can drift.

3. **Local reasoning.** Prefer plain functions, plain data, and composition. A reader must understand a behavior from three things only: the owner, its inputs, its dependencies. If the reader must also open a framework, a global, or a side channel, the design is wrong.

4. **Explicit boundaries.** At each boundary, write down:
    - the contract (inputs, outputs, errors)
    - the dependencies
    - the side effects
    - the failure modes
    - the resource lifetime

Validate data at trust boundaries (user input, network, files, another service). Trust internal callers. Do not re-validate the same data in every internal function.

**Tie-breaker:** Among options that meet requirements equally, pick the most conventional and reversible.
