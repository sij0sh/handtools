# Eval rubric

Score pass/fail/unknown from the decision record, completed diff, and tests; cite
evidence. Unknown verification is not a pass. A proposal without a recorded
decision or completed work is incomplete.

| Requirement | Passing evidence |
|---|---|
| Local reasoning | Owner, behavior and affected contracts identifiable; reviewer can explain change without tracing unrelated owners |
| Contract | Consumers use declared public symbols/paths/directories; no mandatory barrel; contract inputs/outputs usable publicly |
| Dependencies/state | Acyclic owner graph; each state item has one owner; no new internal reach-through or shared mutable ownership |
| Behavior | Scenario acceptance and failure cases tested; existing contract behavior preserved unless the task changes it |
| Scoped change | Unrelated owners untouched; necessary adjacent edits explained; legacy violations not increased |
| Verification | Baseline and final selected checks recorded; introduced regressions absent; known failures matched by diagnostic, not blanket skip |
| Decisions | Material decisions recorded with reasons; standards consulted only when a decision turned on them; two-implementer challenge run; frontier empty at stop |

Owner-local tests may import internals, even from a separate test directory.
Consumer tests use the declared API. Record which kind each test is.

Report unavailable tools/checks separately from failing checks. Repository verify
entrypoints are authoritative only for documented coverage; a green command does
not prove uncovered requirements. Strict verification cannot pass missing checks.

Task 6 scores the record only: material branches found, challenge run, frontier empty.

Layout, file count, duplication and abstraction count are heuristics, not scores.
Judge whether a second variation stays understandable; neither forced extraction
nor forced duplication wins. Do not infer long-term outcomes from one-shot runs.
