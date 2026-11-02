# Defaults

Use when requirements, adopted decisions, and project conventions leave a choice open.

1. **Keep it simple.** Choose the smallest conventional solution that meets current needs. Add an abstraction or layer when a present need requires it.

2. **One owner.** Give each behavior, rule, and piece of mutable state one authoritative owner.

3. **Local reasoning.** Prefer concrete functions, data, and composition. A reader should understand a behavior from its owner, inputs, and dependencies.

4. **Explicit boundaries.** State contracts, dependencies, side effects, failures, and resource lifetimes. Validate untrusted data at trust boundaries; trust internal callers.

**Tie-breaker:** Among options that meet requirements equally, pick the most conventional and reversible.
