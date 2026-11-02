# Simple by Design

A skill for coding agents: turn a goal into the smallest sufficient set of
implementation decisions, then implement against them.

## Problem

Each feature can add another layout, abstraction, or error convention. A small
change then needs a reviewer to trace unrelated owners, and two implementers
following the same brief can still build different things.

## Proof

The loop produces a decision record. A checker tracks what is open, stale, or
structurally broken:

```md
## Decisions
- [ ] D1: State authority? -> server
- [x] D2 (after: D1): Update behavior? -> optimistic with rollback
- [x] D3 (after: D2): Conflict edits? -> last write wins
```

```bash
node <skill-dir>/scripts/frontier.mjs design/decisions.md
```

```text
ready D1: State authority? -> server
reopen D2: depends on open D1
reopen D3: depends on open D2
3 unresolved or stale; decide ready questions, then rerun
```

Once every decision is resolved:

```text
mechanically closed (3 decisions); perform semantic two-implementer challenge
```

Exit 0 means structurally closed, never semantically complete. Exit 1 lists the
next ready questions or stale descendants. Exit 2 means malformed dependencies.

## The loop

```text
Frame -> Ground -> Branch -> Resolve frontier -> Challenge
                     ^                             |
                     +----- material divergence ----+
```

Stop when the frontier is empty and the challenge finds no material divergence
between two competent implementers. Then implement, verify, and reopen decisions
that evidence contradicts.

## What changes

| Repeated question | Default answer |
|---|---|
| Where does behavior belong? | Its capability owner, with explicit state and contracts |
| Should similar code become shared? | Only for a shared concept or useful boundary |
| Which folder architecture is required? | None; structure follows actual needs |
| Must legacy code be rewritten? | No; bounded improvements without new violations |
| Does a small diff prove simplicity? | No; inspect owners, contracts, behavior |
| Is an empty decision list done? | No; the two-implementer challenge decides |

## Install

Needs a coding agent that discovers directory-based skills, Node for the checker,
and bash for `verify.sh`.

Add this checkout to the agent's skill search path, or copy the whole directory to
its documented skill location. Keep `SKILL.md`, `references/`, `standards/`,
`languages/`, `templates/`, and `scripts/` together; discovery steps depend on the
host.

## Quick start

```text
Use simple-by-design. Design <goal>. Record material decisions in
design/decisions.md, then stop for my review.
```

The loop reads `references/defaults.md`, adopts routine defaults with a one-line
reason, and asks only about indispensable intent or consequential tradeoffs. You
get back the decision record and the frontier output shown above.

## Use

### Standards on demand

`references/defaults.md` is always read. Deeper rules load only when a decision
turns on them:

- `standards/contract.md`: ownership, contracts, dependency direction, trust
  boundaries, failures, resource lifecycle.
- `standards/local-reasoning.md`: ambiguous ownership or a contested abstraction.
- one `languages/<language>.md`: types, errors, resources, concurrency, validation.

Adopted profile rules become ordinary decision rows, e.g.
`D4: Errors? -> specific exceptions; business outcomes as values (python profile)`.

### Rules at three strengths

- **Requirements:** correctness, safety, ownership, explicit acyclic dependencies,
  declared public contracts, trust-boundary validation, behavioral verification.
- **Defaults:** concrete functions and data, capability-first organization, explicit
  control flow, narrowly owned mutation, idiomatic language choices.
- **Heuristics:** size, nesting, duplication, and change surface prompt review;
  they are not numeric gates.

Architectural exceptions need approval, scope, and rationale; temporary ones need
a revisit condition. Correctness and safety do not bend. Existing debt gets a
bounded baseline, not permission to add violations.

### Scripts

| Script | Phase | Checks |
|---|---|---|
| `scripts/frontier.mjs` | design | record structure: ready, waiting, reopen, cycles, unknown dependencies |
| `scripts/verify.sh` | implement | code: repository entrypoint or profile commands |

Run verification from the target repository, using the actual path to this checkout:

```bash
/path/to/simple-by-design/scripts/verify.sh --strict
```

Resolution: `SBD_VERIFY_CMD`, `make verify`, `npm run verify`, `just verify`, then
detected profile commands. `--strict` fails on missing tools or undetected checks;
`--only=python` selects fallback profiles without a stack marker. Non-strict mode
can skip checks, so exit zero alone is not proof.

### Languages and boundary checks

Profiles: TypeScript, JavaScript, Python, Go, Rust, Java, C#, C, C++, SQL. A missing
profile means universal rules plus a reported coverage gap.

[Boundary templates](templates/boundaries/) cover import-linter, dependency-cruiser,
ArchUnit (.NET and JVM), golangci, deny.toml, clang-tidy, CMake layering, sqlfluff.

### Examples and evals

[reference-feature](examples/reference-feature/) has TypeScript and Python
implementations with consumer tests and `architecture.json` declaring coverage and
limits. Layouts are illustrative.

[Eval tasks](evals/tasks.md) cover a legacy fix, greenfield feature, second
variation, boundary change, owner extension, and a design-only probe. Historical
`evals/results/` runs predate this policy; rerun before comparing.

## Removal

Remove the skill search-path entry or copied directory. Repository decision
records, tool configuration, and code stay; revise their links or decisions
separately.

## Maintenance

```bash
bash scripts/check-profiles.sh
python3 -m unittest discover -s scripts -p 'test_*.py'
```

## Reference

- [Agent entrypoint](SKILL.md)
- [Loop defaults](references/defaults.md)
- [Contract](standards/contract.md) and [rationale](standards/local-reasoning.md)
- [Language profiles](languages/)
- [Review findings and evidence](workflows/review.md)
- [Boundary templates](templates/boundaries/)
