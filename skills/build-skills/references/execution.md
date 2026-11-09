# Execution Models

Choose the least orchestration that meets the pass condition. Answer in order. Section 1 is GROUND `kind`; DESIGN records every `label` that is yes in `criteria`.

## 1. Saved prompt or stages

Use `kind: prompt` unless the skill needs one of the following, then use `kind: staged`: 

- `focus`: steps form a chain (e.g. plan -> execute -> review); each step's output quality matters and the next builds on it.
- `gate`: a later step must wait for a script check or user approval.
- `isolate`: a step must not see another step's context (independent review, blind judgment).
- `enforce`: order or branch must hold even when the agent would skip or merge steps.

Cut a stage only at a boundary that meets one of these; other steps stay numbered inside a stage prompt. Step count alone never decides. Each stage names its `output` and the `check` that verifies it (script CHECKS, user, or consuming stage).

## 2. Stateful or stateless

Staged only. Default: stateless; orchestrator carries results; stages run in one context, or fresh subagents when `isolate`. Stateful if any is yes:

- `resume`: run spans user turns, concurrent sessions, or may outlive context compaction.
- `inspect`: an intermediate artifact must be read by the user or a later stage after its producer's context is gone.
- `loop`: any stage repeats. Every loop sets `loop_limit`.
- `recover`: target writes need backup or rollback.

## 3. Router or SKILL.md only

Staged only. Router if:

- `conditional`: some instructions apply only under a condition a pointer can name (mode, language, branch), and a typical run skips them.

Content every run reads stays in SKILL.md. Stage-specific text goes in the stage prompt, not a leaf. One condition per leaf.

Revise: apply fresh; show the user any change from the existing model.

## Shared planning and backend

The authoring run always uses the shared planning contract in `_engine/planning.py`.
Prompt output needs no runtime. Staged output uses the engine's `PLANNING = True` readiness gate.
Stateful means resumable, currently backed by a journal; stateless means ephemeral with no recovery
or retained cross-turn authorization promise. Backend is a separate runtime choice. Transcript-only
capture is an explicit plan-only pilot, not an installation backend. Shared resources live in the
packaged `_engine/policy/`; never depend on a sibling skill.
