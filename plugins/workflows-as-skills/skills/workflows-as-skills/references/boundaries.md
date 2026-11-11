# Workflow shape

What reasoning materially improves this result?

| Choice | Use when | Cost |
|---|---|---|
| One-pass prose | intent stable; output checkable | weak recovery |
| Linear phases | artifact consumed and challenged by next phase | handoffs, stale results |
| Persistent engine | resume/compaction, guarded transitions, loops | code, tests, recovery |
| Judgment loop | falsifiable material judgment | latency, churn, correlated blindness |
| Conditional resolution | intent or unsafe fact gap blocks progress | pause |
| Approval/effect gate | irreversible/harmful effects need permission | friction; not correctness |
| Delegated stage | parallel independent work or isolated fresh-context verification | handoff loss, conflicts |

**Delegation test.** See delegation.md when parallel or fresh context helps.

**Boundary test.** Split on a signal: objective, reasoning, evidence, dependency, verification (strongest). Ask: what would be lost if performed together? None → merge. Record signal, handoff, merged loss, closure check, earliest rewind.

**Continuation test.** Continue while a distinct, plausible, consequential failure remains. Evaluation loops change perspective, not repeat; progress loops continue while revisions resolve deficiencies.

**Termination test.** Stop when findings repeat, are immaterial, or uncertainty is untestable. Budget is a safety cap, not exit. Exhaustion reports unresolved uncertainty; zero findings is not proof.

Gates answer authority, not cognition. No fixed counts or numeric confidence.
