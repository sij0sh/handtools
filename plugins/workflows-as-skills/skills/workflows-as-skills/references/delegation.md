# Delegation

Add a conditional instruction at the start of a phase's prose only when delegation materially helps: parallel independent work, or isolated fresh-context verification such as an adversarial review. Do not delegate small clear steps, sequential dependencies, or work that needs accumulated context; that is ceremony.

Prefer a native subagent. If none exists, use the same harness's one-shot CLI/SDK with the same model; for Pi use `pi --print --no-session` with `--model` set to the parent model, not a custom scheduler. If neither is available, continue same-agent and report degraded isolation.

Give the child a compact handoff: task, requirements, accepted decisions, relevant evidence, unresolved questions. Exclude the parent reasoning transcript. Require a bounded return: result, evidence, uncertainty, affected decisions. The child must not inherit the parent's conclusion.

Children may write only to disjoint assigned paths. Never allow concurrent writes to the same path; parallel work is limited to disjoint outputs or read-only investigation. The parent joins child work, observes failures, merges conflicts, and cleans up.

The instruction names the trigger, handoff, return, executor, fallback, and workspace rule; it does not prescribe a scheduler.
