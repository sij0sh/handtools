# Coding Contracts

Detail for decisions on ownership, boundaries, dependencies, state, or failures. Extends `defaults.md`.

1. **Access through the owner.** Read and change owned state or rules only through the owner's public contract.

2. **Directed dependencies.** Keep dependencies acyclic. Draw a boundary around a cohesive responsibility; it may span folders or share one.

3. **Owned resources.** Name who cleans up each resource, completes or cancels each concurrent task, and observes its failures.

4. **Ownership check.** When understanding a behavior requires reconstructing unrelated systems, move the owner or remove the abstraction.

## Tradeoffs

- **Duplication vs. coupling:** Duplicate small code between unrelated capabilities. Keep each authoritative business rule in one place.
- **Structure vs. indirection:** Add I/O isolation or an abstraction when it marks a real boundary.
- **Size vs. clarity:** Measure complexity by concept count and the owners or contracts touched.
