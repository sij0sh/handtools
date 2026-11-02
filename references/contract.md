# Coding Contracts

Each piece of state or rule has one owner, all access goes through that owner, dependencies point one way, and each resource has a named owner for cleanup and failure.

1. **Access through the owner.** Who owns this state or rule? Does other code touch it only through the owner's public contract (its declared functions, API, events) and not its internals?

2. **Directed dependencies.** Do any dependencies form a cycle? If yes, draw a boundary around one cohesive responsibility and move one side behind it. The boundary can be one file or many folders.

3. **Owned resources.** For each resource (file, lock, connection, timer, task), name three owners:
     - who cleans it up
     - who completes or cancels it
     - who observes its failure

4. **Ownership check.** Ask: to understand this behavior, must a reader reconstruct unrelated systems? If yes, the owner is in the wrong place or the abstraction is false. Move the owner or delete the abstraction.

## Tradeoffs

- **Duplication vs. coupling:** Duplicate small code between unrelated capabilities. Keep each authoritative business rule in one place.
- **Structure vs. indirection:** Add I/O isolation or an abstraction when it marks a real boundary.
- **Size vs. clarity:** Measure complexity by concept count and the owners or contracts touched.
