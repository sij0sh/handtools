# Changelog

## 0.0.11

- Rename the project and skill from `saaw` to `build-skills`: entry point `scripts/build-skills.py`, package `scripts/build_skills/`, tests `tests/test_build_skills.py`.

## 0.0.10

- `start` is the only entry point; the `prompt` command is removed.
- GROUND sends `kind`: `prompt` (saved prompt: user-invoked, SKILL.md only) runs ground -> draft -> review; `staged` runs ground -> design -> draft -> review. Optional `wording` keeps the user's prompt text verbatim.
- Saved prompts keep the fresh-subagent review: would an agent given exactly this text meet the pass condition?
- `execution.md`: "saved prompt" replaces "semantic"; the default is stages, and stateless is the default staged model (no stage label required). DESIGN offers `stateless|stateful` only.
- `instructions.md`: a saved prompt's body is the prompt itself.

## 0.0.9

- Restore the staged engine and the short `SKILL.md` entry; stage prompts and execution-model selection are unchanged.
- Add `prompt`: `prompt --name ... --description ... --body ...` writes a saved-prompt skill with valid frontmatter, without opening a session.

## 0.0.8

- Skills default to `disable-model-invocation: true`; DRAFT requires an explicit `true`/`false` (`false` only when clearly model-invoked or the user asks).
- `description` is one short line (max 100 characters), e.g. `description: Create or revise an agent skill.`; details belong in the skill.

## 0.0.7

- `execution.md`: labeled yes/no criteria. Stages: `focus`, `gate`, `isolate`, `enforce`. Stateful: `resume`, `inspect`, `loop` (every loop sets `loop_limit`), `recover`. Router: `conditional`. Drops '80/20' and 'transforms throughout'.
- `instructions.md`: Core rules (target the gap, condition -> action -> exception, constraints vs preferences, boundaries) plus per-surface rules: description, SKILL.md body, leaf pointer, stage prompt, CHECKS. Sole owner of stage-prompt rule; template docstring keeps mechanics only.
- GROUND adds required `gap`; header, DRAFT, and REVIEW cite it. Review question: least instruction that closes the gap and meets the pass condition; design flaws reported, not applied.
- DESIGN adds `criteria` (validated against model and router) and `stages` [{name, output, check, loop_limit?}] for staged models; design.md records them. DRAFT checks steps.py ORDER matches stage names.

## 0.0.6

- REVIEW: one fresh subagent per loop answers one question (least instruction that meets the pass condition: cuts + missing behavior); orchestrator validates against pass condition and design. Max 3 loops.
- Review payload: `findings[].file` replaces `component`; `next` dropped. `confirmed: true` finishes; applied findings loop; shape rechecked each loop.
- Engine copies the workflow template into the draft and sets `MODE` at DESIGN for staged models; DRAFT prompt prints the SKILL.md run steps.
- DESIGN drops `omit` and `style`; design.md records model, router, why.
- Delete `references/review.md` (criteria: `instructions.md`) and `references/workflow.md` (criteria: `execution.md`; MODE contract: template `steps.py` docstring).

## 0.0.5

- Refocus on creating and revising skills: ground -> design -> draft -> review -> draft | finish; one working copy.
- Archive evaluation machinery (candidates, A/B arms, checks, benchmarks, evaluate/decide rounds, `evaluate.md`, `principles.md`) and old state to `.agents/artifacts/eval-archive/`.
- `structure.md` -> `execution.md` (Execution Models: semantic, stateless stages, stateful stages; router complementary).
- `instructions.md`: what to omit, when to state style. `workflow.md`: stage engine only. `review.md`: omit/style/model findings.
- Template: `MODE = 'stateful' | 'stateless'` in `steps.py`; stateless saves nothing, `done --stage S`.
- DRAFT gate: shape matches declared model and router. Revise: backup kept; finish refuses if target changed.
- Drop `priorities`, `auto`, round cap; user confirms design and finish.

## 0.0.4

- Pivot: stages ground -> assess -> plan -> change -> evaluate -> decide -> finish; each writes an artifact the next cites.
- Agent chooses substrate, evaluation method, and principle weighting; no fixed tracks, polish phases, or line gates.
- One candidate schema `{id, from?, change, hypothesis}`; revise backs up target as `baseline`.
- Script runs declared `checks` (cwd = candidate, cached by content + command, outside the lock); finish blocks regressions of baseline-passing checks.
- A/B arms optional (`tasks`); `control` optional.
- New `references/principles.md` (lenses) and `references/evaluate.md` (methods).
- Modules: `stages`, `checks`, `candidates` replace `experiment`, `polish`, `variants`.

## 0.0.3

- Split `scripts/saaw.py` into a thin CLI + `saawlib/` (config, storage, cli, sessions, skill, payload, variants, experiment, polish, prompts, flow); import graph declared and tested.
- Template now `templates/workflow/scripts/`: `workflow.py` + `workflowlib/`; authors edit `steps.py` only; JSON payloads on stdin; writes locked.
- `cli.py`, `storage.py` shared verbatim between saaw and the template; tests enforce identity.

## 0.0.2

- Replace SHAPE/DRAFT/TRIAL with variant experiments: plan -> build -> run -> decide.
- Structure track (instructions, gated, stated) and wording track (`from` copies); control in every run.
- Run results: tokens, seconds, pass, rank, judge assessment vs goal, summary, output paths in `results.md`.
- Free-text priorities; agent picks leader with a reason; auto mode tests until satisfied; 6-run cap.
- Polish (review, simplify, prose) on a copy of the leader, verified by a rerun.
- Target written only at finish; tested variants locked by content hash.

## 0.0.1

- Initial skill: GROUND → SHAPE → DRAFT → REVIEW → SIMPLIFY → PROSE → TRIAL state machine.
- Concurrent sessions; state under `<skill>/state/<project-key>/`.
- New and revise modes; blind A/B trial against no skill with cached arms.
- Single-run workflow template for generated level-3 skills.
