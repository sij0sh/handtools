# Skills profile

Top rule: Every line changes behaviour in every run that loads it.

## 1 Choose structure

- Requirement: pick by what the agent must hold at once.
  - Progressive Disclosure: one task in one pass; context plus instructions,
    however long (e.g. rewrite one thing in a set style).
  - Workflow: ordered steps where a later step depends on an earlier result;
    sequence, branch, or loop (e.g. do X, then Y; if Y = A, do Z, else finish).
- Default: a Workflow step that needs context points to a leaf; Progressive
  Disclosure applies inside the step.

## 2 Shared

- Default: `description` gives one trigger per distinct case, leading word
  first. User-only skills set `disable-model-invocation: true`.
- Default: collapse a spelled-out idea into one existing word the model knows.
- Default: state the wanted behaviour; pair any guardrail prohibition with it.
- Requirement: end each step on a checkable completion criterion.
- Default: show an output format by one example; the example is its authority.
- Default: give a reason only where it lets the agent handle unlisted cases.
- Default: when a skill draws on several sources, state their precedence.
- Requirement: no sentence whose deletion leaves outcomes unchanged: no-ops,
  duplicates, stale lines, human-facing rationale (that belongs in a README).

## 3 Progressive Disclosure

- Requirement: `SKILL.md` holds only what 100% of the runs that load it need;
  the rest moves to a leaf file behind a pointer.
- Default: `SKILL.md` routes: universal steps, then a `condition | file`
  table. Name the condition that triggers the read, not the topic.
- Default: split when the conditional text is longer than its pointer; keep a
  one- or two-line case inline.
- Requirement: point to every leaf from `SKILL.md`; leaves route nowhere.
- Requirement: a leaf is complete for its case given `SKILL.md`. Text two
  leaves need gets its own leaf.
- Default: group sibling leaves in a subdirectory behind one pattern pointer
  (`languages/<language>.md`).
- Default: promote a rule every run uses to `SKILL.md`; demote a rule some
  runs use to a leaf.

Example `SKILL.md` body:

```markdown
Rewrite the target in house style: active voice, one idea per sentence.

| Condition | Read |
|---|---|
| Target is an API reference | `references/api.md` |
| Target is in `<language>` | `languages/<language>.md` |
```

## 4 Workflow

- Requirement: a script owns state and step order; template
  `references/workflow.py`. The agent never edits the state file.
- Requirement: `SKILL.md` says only: run `start`, do the printed step, run the
  printed `done`, repeat until `DONE`, run `status` if the step is lost.
- Requirement: each step prompt ends on a criterion the script checks before
  it advances; `done` refuses an unmet one.
- Requirement: the agent reports a branch value through a `done` flag; the
  script picks the next step.
- Default: `start` replaces any unfinished run; finishing removes the state
  file and prints `DONE`.
- Default: state lives at `.agents/<skill>/workflow.json`; write it atomically.

Example `SKILL.md` body:

```markdown
From the project root, drive the run with `scripts/workflow.py`:

1. `python3 <skill-dir>/scripts/workflow.py start`.
2. Do the printed step, then run the printed `done` command.
3. Repeat until the script prints `DONE`.
4. Lost the current step: `status`.
```
