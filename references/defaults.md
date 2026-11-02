# Defaults

Apply when requirements and adopted decisions leave room for choice. These are preferences, not rigid rules.

1. **Keep it simple.** Choose the smallest conventional solution that meets current needs. Avoid speculative abstractions, layers, and complexity.

2. **Clear ownership.** Give behavior, rules, and mutable state one authoritative owner. Make important contracts, dependencies, and side effects explicit.

3. **Favor local reasoning.** Prefer concrete functions, data, and composition. Introduce abstractions only when they simplify understanding or serve a real boundary.

4. **Handle boundaries.** Make relevant failures, validation, and resource lifecycles explicit. Preserve correctness without unnecessary defensive machinery.

5. **Respect existing design.** In brownfield work, preserve compatible conventions, contracts, and behavior.

**Tie-breaker:** When choices otherwise meet requirements equally well, prefer the most conventional, reversible, and easy-to-change option.
