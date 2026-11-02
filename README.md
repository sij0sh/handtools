# Simple by Design

A coding-agent skill that turns a goal into the smallest sufficient set of
implementation decisions, then implements against them.

Without shared decisions, each feature can introduce another layout, abstraction,
or error convention. This skill runs one recursive design loop, records only the
decisions that would materially change the outcome, and stops when two competent
implementers could not diverge.

```text
Frame -> Ground -> Branch -> Resolve frontier -> Challenge
           ^                                        |
           +----------- material divergence --------+

Stop: frontier empty AND no material divergence.
Then implement, verify, and reopen decisions contradicted by evidence.
```

## What changes

| Repeated design decision | Adopted default |
|---|---|
| Where does behavior belong? | Its capability owner, with explicit state and contracts |
| Should similar code become shared? | Only for a shared concept or useful boundary |
| Which folder architecture is required? | None; structure follows actual project needs |
| Must legacy code be rewritten? | No; bounded improvements without new violations |
| Does a small diff prove simplicity? | No; inspect affected owners, contracts, and behavior |
| Is an empty decision list done? | No; the two-implementer challenge decides |

Local reasoning means understanding a capability without reconstructing unrelated
features. It applies to applications, libraries, CLIs, scripts, UI, systems, and
data work. Language profiles specialize the rules; they do not prescribe frameworks.

## Setup and first use

Requires a coding agent that discovers directory-based skills. Add this checkout
to its skill search path, or copy the whole directory to its documented skill
location. Keep `SKILL.md`, `references/`, `standards/`, `languages/`, `templates/`,
and `scripts/` together; installation and discovery commands depend on the host.

Ask the agent:

```text
Use simple-by-design. Design <goal>. Record material decisions in
design/decisions.md, then stop for my review.
```

The loop adopts routine defaults and states why; it asks only about indispensable
intent or consequential tradeoffs. The finished record is what you review. Existing
conventions, records such as `.agents/artifacts/coding-standards.md`, and comparable
code are evidence, not automatic authority.

## Standards on demand

`references/defaults.md` is always read. Deeper rules load only when a decision
turns on them:

- [contract.md](standards/contract.md) - ownership, contracts, dependency
  direction, trust boundaries, failures, resource lifecycle.
- [local-reasoning.md](standards/local-reasoning.md) - ambiguous ownership or a
  contested abstraction.
- one [language profile](languages/) - language-specific types, errors, resources,
  concurrency, validation.

Adopted profile rules become ordinary decision rows, e.g.
`D4: Errors? -> specific exceptions; business outcomes as values (python profile)`.

## Rules at three strengths

- **Requirements:** correctness, safety, ownership, explicit acyclic dependencies,
  declared public contracts, trust-boundary validation, and behavioral verification.
- **Defaults:** concrete functions/data, capability-first organization, explicit
  control flow, narrowly owned mutation, and idiomatic language choices.
- **Heuristics:** size, nesting, duplication, and change surface prompt review;
  they are not numeric gates.

Architectural exceptions need approval, scope, and rationale. Temporary exceptions
need a revisit condition. Correctness and safety cannot be waived. Existing debt
gets a bounded baseline, not permission to add violations or skip legacy paths.

## Languages and boundary checks

Profiles cover TypeScript, JavaScript, Python, Go, Rust, Java, C#, C, C++, and SQL.
They select types, outcomes/errors, ownership/resources, concurrency, boundaries,
and verification defaults. Missing profiles fall back to universal rules with an
explicit coverage gap.

Boundary-configuration starters in [templates/boundaries/](templates/boundaries/)
cover import-linter, dependency-cruiser, ArchUnit (.NET and JVM), golangci, deny.toml,
clang-tidy, CMake layering, and sqlfluff. Each language profile names the template
its verify block uses.

## Scripts

Two scripts, two phases:

| Script | Phase | Checks |
|---|---|---|
| `scripts/frontier.mjs` | design | `design/decisions.md` structure: ready, waiting, reopen, cycles, unknown dependencies |
| `scripts/verify.sh` | implement | code: repository entrypoint or language-profile commands |

The frontier checker reports design-record state only. Exit 0 means mechanically
closed, never semantically complete; exit 1 lists the next ready questions or stale
descendants; exit 2 means malformed dependencies.

Run verification from the target repository, using the actual path to this checkout:

```bash
/path/to/simple-by-design/scripts/verify.sh --strict
```

Resolution: `SBD_VERIFY_CMD`, `make verify`, `npm run verify`, `just verify`, then
detected language-profile commands. Repository entrypoints replace profile checks;
inspect their coverage. `--only=python` selects fallback profiles, not extra checks
on top of an entrypoint. `--strict` fails on missing tools or undetected checks.
Non-strict mode can skip checks; exit zero alone does not mean fully verified.

Tools enforce objective rules; ownership and design still require review. SQL
lint does not prove schema ownership. C/C++ fallback commands assume CMake;
repository entrypoints may use other build systems.

## Evidence and maintenance

[Reference implementations](examples/reference-feature/) demonstrate TypeScript
and Python contracts, consumer tests, and configured checks. Their layouts are
illustrative. Each example declares coverage and limitations in `architecture.json`.

[Evaluation tasks](evals/tasks.md) exercise greenfield implementation, second-feature
variation, boundary changes, bounded legacy work, and a design-only probe where
discovery quality is the pass condition.

From this checkout, check profile consistency and verifier behavior:

```bash
bash scripts/check-profiles.sh
python3 -m unittest discover -s scripts -p 'test_*.py'
```

## Removal

Remove the skill search-path entry or copied skill directory from your agent.
Repository decision records, configuration, and code remain; remove their links
or revise those decisions separately if no longer wanted.

## Reference

- [Agent entrypoint](SKILL.md)
- [Loop defaults](references/defaults.md)
- [Authoritative contract](standards/contract.md) and [rationale](standards/local-reasoning.md)
- [Language profiles](languages/)
- [Review findings and evidence](workflows/review.md)
- [Boundary templates](templates/boundaries/)
- [MIT license](LICENSE)
