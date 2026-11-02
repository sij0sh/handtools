# Coding Contracts

Apply when decisions involve ownership, boundaries, dependencies, state, or failure handling. These are design principles, not a checklist.

1. **Clear ownership.** Give each behavior, business rule, and mutable state one authoritative owner. Access or change them through that owner's contract.

2. **Explicit boundaries.** Keep dependencies directed and acyclic. Consumers use public contracts, not another owner's internals. A boundary represents a cohesive responsibility, not necessarily a folder or package.

3. **Visible behavior.** Make important inputs, outputs, side effects, and failures explicit. Validate untrusted data at trust boundaries without redundant internal checks.

4. **Owned resources.** Make resource lifetimes and concurrent work understandable, including responsibility for cleanup, completion, and failures.

5. **Local reasoning.** A maintainer should understand a behavior, its owner, dependencies, and affected consumers without reconstructing unrelated systems. If not, reconsider the ownership or abstraction.

## Tradeoffs

- **Duplication vs. coupling:** Prefer small independent duplication over coupling unrelated capabilities. Keep authoritative business rules in one place.
- **Structure vs. indirection:** Isolate I/O or introduce abstractions when they clarify real boundaries, not to satisfy an architectural pattern.
- **Size vs. clarity:** Judge complexity by unnecessary concepts and affected owners or contracts, not lines, files, or diff size.
