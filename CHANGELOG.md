# Changelog

One entry per release. A release bumps `VERSION` (and the manifests that copy it) and adds one entry here.

## [0.1.1] - 2026-11-09

v0.1.1 milestone M1 (reconnaissance contract), per `.agents/artifacts/v011.md`.

- Shared reconnaissance in `skills/_engine/recon/` (not a skill, no trigger): evidence-backed snapshots of components, contracts, relationships, observations, decision references and discovery gaps. `recon/cli.py` runs bounded read-only collectors (`orient`, `candidates`) and records snapshots (`start`, `record`, `close`, `refresh`, `status`, `query`). The recorder hashes every cited file; unknown fields stay unknown; an advertised channel without subscriber evidence has an unresolved consumer and a gap. A `decision:` record must match an answered decision in the ADR log, so inferred patterns stay observations.
- The journal accepts `record.accepted` events carrying a versioned domain envelope, reduced by explicit reducers. Version-1 runs replay unchanged; an unknown envelope version or a missing reducer fails visibly. Recon receipts are recognized in transcripts as non-authoritative evidence.
- `refresh` starts a successor snapshot: records whose evidence is unchanged carry forward, changed ones and their dependents are marked stale, and records without evidence go stale when the scope changed.
- remember adds `recon_snapshots`, `recon_contracts`, `recon_components`, `recon_relationships`, `recon_observations` and `recon_gaps`, rebuilt from the journal.
- foundation: discover follows the shared recon guide and may pin a closed snapshot; interview asks only consequential recon gaps; a new `external-contracts` capability; assess requires a `contract_gaps` finding for every external contract with an unknown owner or compatibility rule. Still stateless.
- untangle: MAP pins a closed recon snapshot or states why none is needed; map entries and findings cite `recon_refs`; the printed steps render state from the journal and `show` prints it (current.md/audit.json are still written); cited recon records that changed block a complete report until reinventory; `start --continue <audit-id>` begins a successor audit that keeps unchanged reviews.
- Generated workflow skills ship `_engine/recon` and record `recon: 1` in `distribution.json`. Draft workflow contract in `_engine/policy/workflow-contract.md` (enforced from M4).
- remember, foundation, untangle and build-skills' `install_engine` were changed directly rather than through build-skills, which only generates standalone skills (G5 D17, D18).

## [0.1.0] - 2026-11-09

- Shared non-skill planning contract and policy ownership in `_engine`.
- Transactional workflow event journal, legacy state import, exact transcript receipt pilot and SQL views.
- Build-skills ready-plan gates, bounded redesign, accepted-draft apply/verify and durable application recovery.
- Standalone workflow templates ship compatible engine, launcher, policy and schema resources.
- User-only generated workflows; no-choice plans allowed; unresolved choices block completion.

## [0.0.3] - 2026-11-09

- Per-user state moves to `~/.agents/state/<area>/<project key>/` (`$HANDTOOLS_STATE` overrides it), out of installed skill folders (a plugin update replaced them) and out of projects: build-skills and untangle runs, untangle's `current.md`/`audit.json`/`report.md`, simple-by-design's `workflow.json`, and foundation's `foundation.json`. The ADR log stays committed at `.agents/design/decisions.json`.
- foundation records its interview answers, including project kind and maturity, as ADR rows under one goal. `foundation.json` keeps only `goal`, `accepted`, `declined` and `updated`.
- One workflow engine, `skills/_engine/` (`storage`, `cli`, `flow`, `sessions`; not a skill), replaces the copies in build-skills, foundation, simple-by-design, untangle and build-skills' template. Skills keep only their steps and a launcher that finds `_engine/` by walking up from itself. build-skills vendors a copy into the workflow skills it writes and refreshes it on every revision. The bundle tests fail if an engine module is copied into a skill.
- `designflow.py --root` now defaults to the git top level, else the current directory, like the other skills.
- Upgrading: move each project's `.agents/design/workflow.json` to `~/.agents/state/decisions/<project key>/` to keep its sessions (run any `designflow.py status` once to create the folder and its `project.json`). Unfinished build-skills or untangle runs and old `.agents/artifacts/untangle/` exports are not carried over.

## [0.0.2] - 2026-11-09

- remember: evidence extraction normalizes Windows path separators, so repository paths are recognized; its activity continuation test no longer assumes short temporary paths.

## [0.0.1] - 2026-11-06

- Start handtools: build-skills, foundation, remember, simple-by-design and untangle in one repo, released as one plugin for Claude Code, Codex and pi.
- simple-by-design owns the shared design rules; untangle finds them beside itself instead of asking for `policy_root`.
- `.agents/design/decisions.json` is the one ADR log. simple-by-design adds `record`, `show`, `date`, `superseded_by`, `G#/D#` references, and a warning when the log is not committed. foundation records, audits and validates ADRs there and no longer writes Markdown ADRs.
- `scripts/check.py` reports when an installed copy is behind origin.

## Before handtools

Per-skill histories, kept as they were (headings nested one level down).

### build-skills (pre-handtools)

#### 0.0.11

- Rename the project and skill from `saaw` to `build-skills`: entry point `scripts/build-skills.py`, package `scripts/build_skills/`, tests `tests/test_build_skills.py`.

#### 0.0.10

- `start` is the only entry point; the `prompt` command is removed.
- GROUND sends `kind`: `prompt` (saved prompt: user-invoked, SKILL.md only) runs ground -> draft -> review; `staged` runs ground -> design -> draft -> review. Optional `wording` keeps the user's prompt text verbatim.
- Saved prompts keep the fresh-subagent review: would an agent given exactly this text meet the pass condition?
- `execution.md`: "saved prompt" replaces "semantic"; the default is stages, and stateless is the default staged model (no stage label required). DESIGN offers `stateless|stateful` only.
- `instructions.md`: a saved prompt's body is the prompt itself.

#### 0.0.9

- Restore the staged engine and the short `SKILL.md` entry; stage prompts and execution-model selection are unchanged.
- Add `prompt`: `prompt --name ... --description ... --body ...` writes a saved-prompt skill with valid frontmatter, without opening a session.

#### 0.0.8

- Skills default to `disable-model-invocation: true`; DRAFT requires an explicit `true`/`false` (`false` only when clearly model-invoked or the user asks).
- `description` is one short line (max 100 characters), e.g. `description: Create or revise an agent skill.`; details belong in the skill.

#### 0.0.7

- `execution.md`: labeled yes/no criteria. Stages: `focus`, `gate`, `isolate`, `enforce`. Stateful: `resume`, `inspect`, `loop` (every loop sets `loop_limit`), `recover`. Router: `conditional`. Drops '80/20' and 'transforms throughout'.
- `instructions.md`: Core rules (target the gap, condition -> action -> exception, constraints vs preferences, boundaries) plus per-surface rules: description, SKILL.md body, leaf pointer, stage prompt, CHECKS. Sole owner of stage-prompt rule; template docstring keeps mechanics only.
- GROUND adds required `gap`; header, DRAFT, and REVIEW cite it. Review question: least instruction that closes the gap and meets the pass condition; design flaws reported, not applied.
- DESIGN adds `criteria` (validated against model and router) and `stages` [{name, output, check, loop_limit?}] for staged models; design.md records them. DRAFT checks steps.py ORDER matches stage names.

#### 0.0.6

- REVIEW: one fresh subagent per loop answers one question (least instruction that meets the pass condition: cuts + missing behavior); orchestrator validates against pass condition and design. Max 3 loops.
- Review payload: `findings[].file` replaces `component`; `next` dropped. `confirmed: true` finishes; applied findings loop; shape rechecked each loop.
- Engine copies the workflow template into the draft and sets `MODE` at DESIGN for staged models; DRAFT prompt prints the SKILL.md run steps.
- DESIGN drops `omit` and `style`; design.md records model, router, why.
- Delete `references/review.md` (criteria: `instructions.md`) and `references/workflow.md` (criteria: `execution.md`; MODE contract: template `steps.py` docstring).

#### 0.0.5

- Refocus on creating and revising skills: ground -> design -> draft -> review -> draft | finish; one working copy.
- Archive evaluation machinery (candidates, A/B arms, checks, benchmarks, evaluate/decide rounds, `evaluate.md`, `principles.md`) and old state to `.agents/artifacts/eval-archive/`.
- `structure.md` -> `execution.md` (Execution Models: semantic, stateless stages, stateful stages; router complementary).
- `instructions.md`: what to omit, when to state style. `workflow.md`: stage engine only. `review.md`: omit/style/model findings.
- Template: `MODE = 'stateful' | 'stateless'` in `steps.py`; stateless saves nothing, `done --stage S`.
- DRAFT gate: shape matches declared model and router. Revise: backup kept; finish refuses if target changed.
- Drop `priorities`, `auto`, round cap; user confirms design and finish.

#### 0.0.4

- Pivot: stages ground -> assess -> plan -> change -> evaluate -> decide -> finish; each writes an artifact the next cites.
- Agent chooses substrate, evaluation method, and principle weighting; no fixed tracks, polish phases, or line gates.
- One candidate schema `{id, from?, change, hypothesis}`; revise backs up target as `baseline`.
- Script runs declared `checks` (cwd = candidate, cached by content + command, outside the lock); finish blocks regressions of baseline-passing checks.
- A/B arms optional (`tasks`); `control` optional.
- New `references/principles.md` (lenses) and `references/evaluate.md` (methods).
- Modules: `stages`, `checks`, `candidates` replace `experiment`, `polish`, `variants`.

#### 0.0.3

- Split `scripts/saaw.py` into a thin CLI + `saawlib/` (config, storage, cli, sessions, skill, payload, variants, experiment, polish, prompts, flow); import graph declared and tested.
- Template now `templates/workflow/scripts/`: `workflow.py` + `workflowlib/`; authors edit `steps.py` only; JSON payloads on stdin; writes locked.
- `cli.py`, `storage.py` shared verbatim between saaw and the template; tests enforce identity.

#### 0.0.2

- Replace SHAPE/DRAFT/TRIAL with variant experiments: plan -> build -> run -> decide.
- Structure track (instructions, gated, stated) and wording track (`from` copies); control in every run.
- Run results: tokens, seconds, pass, rank, judge assessment vs goal, summary, output paths in `results.md`.
- Free-text priorities; agent picks leader with a reason; auto mode tests until satisfied; 6-run cap.
- Polish (review, simplify, prose) on a copy of the leader, verified by a rerun.
- Target written only at finish; tested variants locked by content hash.

#### 0.0.1

- Initial skill: GROUND → SHAPE → DRAFT → REVIEW → SIMPLIFY → PROSE → TRIAL state machine.
- Concurrent sessions; state under `<skill>/state/<project-key>/`.
- New and revise modes; blind A/B trial against no skill with cached arms.
- Single-run workflow template for generated level-3 skills.

### simple-by-design (pre-handtools)

#### 0.0.1 - 2026-10-27

- Scaffold repository, license, version, and directory tree.

#### 0.0.2 - 2026-10-27

- Add eval fixture, four tasks, rubric, and results directory.

#### 0.0.3 - 2026-10-27

- Add local-reasoning style rationale and enforceable style contract.

#### 0.0.4 - 2026-10-27

- Add preflight checks, gate triggers, plan template, and review criteria.

#### 0.0.5 - 2026-10-27

- Add TypeScript language profile.

#### 0.0.6 - 2026-10-27

- Add Python language profile.

#### 0.0.7 - 2026-10-27

- Add Go language profile.

#### 0.0.8 - 2026-10-27

- Add Java language profile.

#### 0.0.9 - 2026-10-27

- Add SKILL.md with routing, loop, gate, verify, and missing-profile rules.

#### 0.0.10 - 2026-10-27

- Add verify.sh with entry-point resolution, stack detection, strict mode,
  profile selection, and skip status for missing tools.

#### 0.0.11 - 2026-10-27

- Add boundary configs for TypeScript, Python, Go, and Java plus a trimmed
  AGENTS.md template.

#### 0.0.12 - 2026-10-27

- Add a TS and Python reference feature with api/domain/persistence split,
  boundary validation, and behavioral tests.

#### 0.0.13 - 2026-10-27

- Seed the small-fix bug on demand, keep the fixture otherwise green, and
  record baseline and skill eval results.

#### 0.0.14 - 2026-10-27

- Add README with install, quick start, verify, limits, and uninstall.
- Keep verify.sh compatible with Bash 3.2.

#### 0.1.0 - 2026-10-27

First release.
- Ship the Local Reasoning style, four language profiles, preflight and review
  workflows, boundary templates, verify.sh, reference feature, and eval results.
- Enforcement is advisory. SimpleGuard and CI gates start in 0.2.0.

#### 0.1.1 - 2026-10-27

- Rewrite README and SKILL.md around the decision-policy framing.
- Replace file-path gate triggers with architectural approval gates.
- Add review procedure, finding detail, and hard-fail versus review-prompt
  split. Require unreported or skipped checks to be stated, not implied.
- Make contract, standards, and profiles advisory where repository
  conventions are clear. Drop the AGENTS.md template.

#### 0.1.2 - 2026-10-27

- Add JavaScript profile and stack marker.
- Require TypeScript source for the TypeScript marker so plain JavaScript
  repositories are not misclassified.

#### 0.1.3 - 2026-10-27

- Add C# profile and NetArchTest boundary template.

#### 0.1.4 - 2026-10-27

- Add Rust profile, cargo-deny starter, and Cargo marker.
- Report the actual missing subcommand tool for `npx` and `cargo deny`.

#### 0.1.5 - 2026-10-27

- Add SQL profile, migration marker, and SQLFluff starter.
- State that SQL ownership is a review rule; SQLFluff checks style only.

#### 0.1.6 - 2026-10-27

- Add C++ profile, CMake layering guard, clang-tidy starter, and C++ marker.
- Generate compile commands in the verify block so clang-tidy can resolve
  targets.

#### 0.1.7 - 2026-10-27

- Add C profile and C marker.
- Use clang-tidy with compile commands for C; keep cppcheck as the fallback
  when no compile database exists.

#### 0.1.8 - 2026-10-27

- Add all ten language profiles: TypeScript, Python, Go, Java, JavaScript,
  C#, Rust, SQL, C, and C++.
- Add profile consistency check and document profile coverage and limits.

#### 0.1.9 - 2026-10-28

- Adopt upfront coding standards and bounded legacy rules; align language profiles, examples, boundary templates, evaluations, and verifier regression checks.

#### 0.2.0 - 2026-11-02

- Replace preflight/approval routing with one recursive design loop, on-demand standards disclosure, and `scripts/frontier.mjs`; rewrite evals around the loop.

#### 0.2.1 - 2026-11-02

- Reduce the skill to `SKILL.md`, `references/`, and `languages/`; remove scripts, templates, evals, examples, workflows, and standards.
- Move the contract to `references/contract.md` and fix the SKILL reference.
- Trim language profiles to Structure, Preferred, and Disallowed.
- Rewrite README for the decision-only scope, manual invocation, and no runtime dependencies.

#### 0.2.2 - 2026-11-02

- Rewrite `SKILL.md` around an explicit precedence chain, reference-loading triggers, and a handoff step; enable model invocation.
- Tighten `references/defaults.md` and `references/contract.md` to one line per rule.
- Rewrite README for users: problem, proof, why decide first, and before/after.

#### 0.2.3 - 2026-11-02

- Add `languages/agent-instructions.md` profile for skills, `AGENTS.md`, and `CLAUDE.md`.
- Route SKILL reference loading and README language coverage to the new profile.

#### 0.2.4 - 2026-11-02

- Make `SKILL.md` write every loop step to `.agents/design/decisions.md`, add a condense prerequisite, and loop steps 2-4 to a stop test.
- Move the record format above the example and retarget the handoff to a readability edit pass.

#### 0.2.5 - 2026-11-02

- Restate `references/contract.md` rules as questions, add a one-line ownership summary, and spell out the three resource owners.

#### 0.2.6 - 2026-11-02

- Expand `references/defaults.md` rules 2-4 with drift, local-reasoning, and boundary-detail clarifications.

#### 0.2.7 - 2026-11-02

- Use "SWE" instead of "competent implementers" in the Challenge step.

#### 0.2.8 - 2026-11-02

- README: lead with "Unslop your project"; credit Matt Pocock's grilling skill as loop inspiration; drop the sample record block.

#### 0.2.9 - 2026-11-03

- Add `scripts/designflow.py` state machine to drive the loop; prompts carry precedence and absolute paths to defaults, contract, and language profiles.
- Slim `SKILL.md` to purpose, run steps, and record format; loop text now owned by the script.
- Record moves to `.agents/design/decisions.json`: one set per goal (G#), decisions keep D#, status, optional `after`/`rationale`. Schema at `references/decisions.schema.json`; script validates it.
- `start` replaces any existing `workflow.json`; finishing deletes it. Drop `next`/`reset` and the condense step.
- Handoff deletes `decisions.md` and has the agent rewrite it once from the JSON in ASD-STE100 Simplified Technical English.
- Add `tests/test_designflow.py` (stdlib unittest).
- README: Python 3.9+ requirement, script loop section, updated file table.

#### 0.2.10 - 2026-11-03

- Rename `languages/agent-instructions.md` to `languages/skills.md`; skills only. Two structures: Progressive Disclosure and Workflow, chosen by what the agent holds at once. Add `references/workflow.py` template and tests.

#### 0.3.0 - 2026-11-03

- README rewritten around intent, the script-driven loop, and honest open questions; trim install, quick start, and file table.

#### 0.3.1 - 2026-11-03

- Windows support: docs give `python` alongside `python3`; printed `done` commands quote paths with double quotes on Windows so the full interpreter path is runnable there.
- Tests cover printed command interpreter and Windows quoting.

#### 0.3.2 - 2026-11-03

- Permanent design sessions in `workflow.json`: `s1`, `s2`, ...; `status`, `status --session`, `done --session`, and `abandon`; one active session per goal; atomic `workflow.lock`; migration from old single-run state. Remove the `handoff` phase and `decisions.md`; zero-gap challenge prints the session close summary. Update `SKILL.md`, `README.md`, `languages/skills.md`, and tests.

#### 0.3.3 - 2026-11-04

- Agent edits the record only through the CLI: `done` reads a JSON payload on stdin (goal fields plus `decisions` rows upserted by `id`; `null` removes a field; `drop` deletes; `status` derived from `answer`), applies it to the session's goal under the lock, and writes nothing on error. Each step prints the session goal as JSON and the next free D#. Remove `--goal` and `--gaps`: ground creates or reuses a goal from the payload. Challenge closes only on an unchanged goal; any change starts a fresh challenge, via decide when rows are open. `SKILL.md` drops its Files and Format sections; prompts no longer name `decisions.json` or the schema. Update `README.md`, `languages/skills.md`, and tests.

#### 0.3.4 - 2026-11-04

- Split `scripts/designflow.py` into a CLI entry point plus `scripts/designlib/` (`flow`, `steps`, `sessions`, `record`, `storage`, `config`), one owner each; a test enforces one-way imports.
- Challenge limit: optional `metadata.max-challenges` in `SKILL.md` frontmatter, default 3. At the limit the session closes; open gaps from the last challenge get one final decide; summary lists remaining open questions. Step header shows `LOOP: n/max`.

#### 0.3.5 - 2026-11-05

- Replace `languages/skills.md` with `references/instructions.md`: semantic instruction design framework for any agent instructions (skills, prompts, `AGENTS.md`, `CLAUDE.md`). Decide routes agent-instruction questions there; language list no longer special-cases it.
- Remove `references/workflow.py` and its tests; workflow-skill scaffolding now lives in a separate skill.
