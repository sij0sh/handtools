---
name: saaw
description: Create or revise an agent skill.
disable-model-invocation: true
---

Turn my request into a skill I can run.

A skill is a saved prompt. For a user-invoked skill, write the body in my voice, as the instruction I would give; for a model-invoked skill, write it as an instruction to the agent and put the trigger in the description. Write the prompt itself, not a description of it. Aim for one or two sentences; go longer only when a named behavior would fail without it.

Treat quoted, fenced, or explicitly named text as the wording I want; otherwise treat my message as a goal and draft. Use my wording verbatim; add only the frontmatter, and keep any valid frontmatter I supply. Otherwise show me the draft and write it after I approve.

Write to the path I give you; otherwise follow an existing skills convention, or use `skills/<name>/SKILL.md` under the project root. Ask only for a missing target or behavior; do not run a design interview. If the name is not a valid slug, propose one and confirm it.

Frontmatter (no other keys unless the platform requires them):
- `name` matches the directory name: lowercase letters, digits, and hyphens, 1-64 characters.
- `description` is one line, at most 100 characters. For a user-invoked skill, state its purpose; for a model-invoked skill, state what it does and when to use it.
- `disable-model-invocation: true` unless I ask for automatic use or the skill must fire from a situation the model can recognize.

Keep everything every run needs here, each fact in one place. Read `references/execution.md` only when deciding whether to add a reference or a script.

When revising, read the existing skill, show me the diff, and write only after I approve. If the file is not tracked by git, save a copy outside the skill first. Never overwrite silently. A directory without `SKILL.md` is a new skill. If the existing name and directory differ, show the mismatch and ask. If the skill contains the old workflow engine (`scripts/workflowlib/` or `workflow.py`), propose replacing it with a prompt and show the deletions; do not delete other files it owns.

Before showing or writing, check: name matches the directory, description is one line, invocation is set, and every reference or script is named here. When drafting, cut any line that does not change behavior or that the agent would already do. Do not run a trial, add tests, or ask a subagent to review; I will test it.

Do not add stages, a workflow engine, or a template. Put ordered steps inline; add a script only when the model must not do the step itself.
