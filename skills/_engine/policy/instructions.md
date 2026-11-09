# Semantic Instructions: A Design Framework for AI Agents

Core principle: Design instructions to change agent behavior, not to describe ideal behavior.

A good semantic instruction is a minimal behavioral contract: it changes a specific decision, under identifiable conditions, toward a verifiable outcome.

## 1. Refine the original principles

| Original idea | Stronger formulation |
|---|---|
| Design for behavioral change | Target a specific decision the agent would otherwise get wrong. |
| Define an observable pass condition | Specify success, failure, and how to distinguish them. |
| Write the bare minimum | Minimize ambiguity and unnecessary constraints, not merely tokens. |
| Prefer implicit intent | Rely on defaults when they're reliable; explicitly specify consequential deviations. |

### Important gaps

1. Observable success isn't sufficient. An agent can pass an output test while taking unacceptable actions along the way. Evaluate both results and critical process constraints.
2. Default behavior isn't guaranteed. Models, tools, and environments differ. Assume common conventions only when mistakes are inexpensive or the defaults have been validated.
3. Instructions have opportunity costs. Every rule consumes attention, may conflict with another rule, and can reduce flexibility. A rule should earn its place by preventing a meaningful failure.
4. Behavioral flexibility matters. Specify what matters, not how to do everything. Mandate procedures only when the procedure itself is important.
5. Exceptions often matter more than the main rule. Most agents handle ordinary cases reasonably. Instructions create greater value at boundaries: ambiguity, competing goals, irreversible actions, missing information, and failures.

## 2. Seven rules for designing semantic instructions

1. Specify the behavioral delta. Describe what the agent should do differently from its natural behavior. Avoid repeating established conventions.
2. Target decisions, not personality. Replace vague qualities such as "thoughtful," "proactive," or "thorough" with concrete decision rules.
3. Make conditions explicit. Define when a rule applies. An instruction without scope can unintentionally affect unrelated tasks.
4. Distinguish constraints from preferences. Constraints must hold; preferences guide tradeoffs. Do not give them equal priority.
5. Encode important boundaries. Explicitly address permissions, irreversible actions, uncertainty, unavailable capabilities, and conditions for stopping.
6. Preserve implementation freedom. State the desired outcome and necessary boundaries. Let the agent choose the approach unless the method is itself consequential.
7. Test before expanding. Add or strengthen rules in response to observed failures, not hypothetical stylistic improvements.

## 3. A practical design workflow

1. Define the desired behavior. What observable decision or result should change?
2. Establish baseline behavior. What does the agent already do without additional instructions?
3. Identify the gap. Where does the baseline fail, become inconsistent, or create unacceptable risk?
4. Write the smallest intervention. Add a targeted rule only for the gap. Prefer condition → action → exception.
5. Test across boundaries. Test normal, ambiguous, adversarial, and exceptional scenarios. Include tests where the rule should not apply.
6. Prune and consolidate. Remove rules that don't materially improve results. Resolve overlaps, contradictions, and unnecessary prescriptions.
7. Retest after changes. Verify improvements without introducing regressions elsewhere.

## 4. The semantic instruction template

Use this structure when an explicit rule is necessary:

```text
BEHAVIORAL CONTRACT
When [trigger or context],
do [required behavior],
unless [meaningful exception].
If unable, [fallback behavior].
Pass when [observable acceptance condition].
```

Not every instruction needs all five elements. Omit whichever elements add no behavioral value.

### Example: Proactive behavior

Weak:

> Be proactive, efficient, and careful. Take initiative while respecting the user's preferences.

Stronger:

> Proceed without asking for approval on reversible, low-risk actions within the requested scope. Obtain approval before irreversible changes. If the intended outcome is materially ambiguous, clarify before acting.

This version changes identifiable decisions and can be tested.

## 5. Questions to ask before adding an instruction

- Necessity: Would the agent behave correctly without this instruction?
- Behavior: Which specific decision should change?
- Observability: How would I demonstrate that the instruction worked?
- Scope: When should the instruction apply, and when shouldn't it?
- Implicit defaults: Am I restating something the agent already reliably does?
- Freedom: Am I prescribing a method where an outcome would suffice?
- Risk: What is the cost of following, ignoring, or misinterpreting it?
- Conflict: Could this contradict an existing instruction or higher-priority constraint?
- Robustness: Does it work on unfamiliar cases, not just my examples?
- Compression: Can I remove anything without changing intended behavior?

## 6. The most useful additional principle: instructional leverage

Evaluate an instruction by its marginal behavioral value, not its elegance.

An instruction has high leverage when it:

- Prevents an important, recurring failure.
- Requires little context to interpret.
- Applies consistently across relevant situations.
- Introduces few exceptions or unintended consequences.
- Preserves the agent's ability to adapt.

This suggests a broader design philosophy:

Instructions should define the boundaries of autonomy, not substitute for intelligence.

They are most valuable when identifying what the agent cannot reliably infer: specific user preferences, unusual priorities, unacceptable risks, permissions, and success conditions.

## 7. A compact doctrine

1. Start with desired behavior.
2. Observe the default before intervening.
3. Specify differences, not conventions.
4. Make consequential boundaries explicit.
5. Prefer outcomes over procedures.
6. Use conditions instead of universal rules.
7. Preserve autonomy wherever safe.
8. Test behavior, not wording.
9. Remove instructions without demonstrated value.
10. Optimize the instruction set as a system, not each rule independently.

The governing question is:

"What is the smallest additional piece of information that will reliably cause the agent to make the right decision?"

That is a stronger optimization target than prompt length, prose clarity, or exhaustive specification.
