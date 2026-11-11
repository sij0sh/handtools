# Details

**Frame.** Read the target and direct references; note existing rules, evidence, and questions. Separate requirements from preferences; distinguish facts, assumptions, unknowns, decisions. Surface consequential ambiguity as a question, not a rule.

**New.** SKILL.md needs `name`/`description` frontmatter; AGENTS.md is plain markdown; agent definitions follow project shape or surface unknown; prompts are plain text; workflow/evaluation instructions follow surrounding format.

**Kinds.** Semantic directives guide judgment; evaluative questions expose failure; mechanical rules govern execution. State when conditional rules apply. Use deterministic mechanics for state, ordering, persistence, checks. A mechanical rule needs a trigger, changed decision, and observable outcome.

**Challenge.** Sufficiency: could literal compliance miss the intended outcome? Give a concrete failure case, or a plausible case plus evidence ruling it out; "none found" alone is insufficient. Necessity: state how each rule changes behavior; remove rules with no effect. Semantic directives need no mechanical trigger. Revise only affected text, at most twice; recheck after each. Stop when no material defect remains or the limit is reached; report unresolved risks.

**Output.** Review never writes. Return findings with a proposed diff for warranted changes. For create/edit/simplify, write the specified target path and briefly confirm; without a path, return the instruction inline. New files use the required format; edits preserve format and scope. Explain removed or contested rules and report unresolved risks; otherwise add no commentary.
