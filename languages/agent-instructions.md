# Agent instructions profile

Top rule: Every line changes behaviour in every run that loads it.

## 1 Structure

- Requirement: disclose progressively. A file holds only what 100% of the runs
  that load it need; the rest moves to a leaf file behind a pointer.
- Default: the entry file routes: universal steps, then a `condition | file`
  table. Name the condition that triggers the read, not the topic.
- Default: split when the conditional text is longer than its pointer; keep a
  one- or two-line case inline.
- Requirement: point to every leaf from the entry file; leaves route nowhere.
- Requirement: a leaf is complete for its case given the entry file. Text two
  leaves need gets its own leaf.
- Default: group sibling leaves in a subdirectory behind one pattern pointer
  (`languages/<language>.md`).
- Default: promote a rule every run uses to the entry file; demote a rule some
  runs use to a leaf.

## 2 Preferred

- Requirement: always-loaded text (`AGENTS.md`, `CLAUDE.md`, skill
  `description`) holds only what the agent cannot find by looking: unwritten
  conventions, reasons behind choices, gotchas.
- Default: skill `description` gives one trigger per distinct case, leading
  word first. User-only skills set `disable-model-invocation: true`.
- Default: collapse a spelled-out idea into one existing word the model knows.
- Default: state the wanted behaviour; pair any guardrail prohibition with it.
- Requirement: end each step on a checkable completion criterion.
- Default: show an output format by one example; the example is its authority.
- Default: give a reason only where it lets the agent handle unlisted cases.
- Default: when a workflow draws on several sources, state their precedence.

## 3 Disallowed

- Requirement: no sentence whose deletion leaves outcomes unchanged: no-ops,
  duplicates, stale lines, human-facing rationale (that belongs in a README).
