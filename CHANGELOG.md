# Changelog

All notable changes to this skill are recorded here. One line per commit.
Releases are tagged.

## 0.0.1 - 2026-10-27

- Scaffold repository, license, version, and directory tree.

## 0.0.2 - 2026-10-27

- Add eval fixture, four tasks, rubric, and results directory.

## 0.0.3 - 2026-10-27

- Add local-reasoning style rationale and enforceable style contract.

## 0.0.4 - 2026-10-27

- Add preflight checks, gate triggers, plan template, and review criteria.

## 0.0.5 - 2026-10-27

- Add TypeScript language profile.

## 0.0.6 - 2026-10-27

- Add Python language profile.

## 0.0.7 - 2026-10-27

- Add Go language profile.

## 0.0.8 - 2026-10-27

- Add Java language profile.

## 0.0.9 - 2026-10-27

- Add SKILL.md with routing, loop, gate, verify, and missing-profile rules.

## 0.0.10 - 2026-10-27

- Add verify.sh with entry-point resolution, stack detection, strict mode,
  profile selection, and skip status for missing tools.

## 0.0.11 - 2026-10-27

- Add boundary configs for TypeScript, Python, Go, and Java plus a trimmed
  AGENTS.md template.

## 0.0.12 - 2026-10-27

- Add a TS and Python reference feature with api/domain/persistence split,
  boundary validation, and behavioral tests.

## 0.0.13 - 2026-10-27

- Seed the small-fix bug on demand, keep the fixture otherwise green, and
  record baseline and skill eval results.

## 0.0.14 - 2026-10-27

- Add README with install, quick start, verify, limits, and uninstall.
- Keep verify.sh compatible with Bash 3.2.

## 0.1.0 - 2026-10-27

First release.
- Ship the Local Reasoning style, four language profiles, preflight and review
  workflows, boundary templates, verify.sh, reference feature, and eval results.
- Enforcement is advisory. SimpleGuard and CI gates start in 0.2.0.

## 0.1.1 - 2026-10-27

- Rewrite README and SKILL.md around the decision-policy framing.
- Replace file-path gate triggers with architectural approval gates.
- Add review procedure, finding detail, and hard-fail versus review-prompt
  split. Require unreported or skipped checks to be stated, not implied.
- Make contract, standards, and profiles advisory where repository
  conventions are clear. Drop the AGENTS.md template.

## 0.1.2 - 2026-10-27

- Add JavaScript profile and stack marker.
- Require TypeScript source for the TypeScript marker so plain JavaScript
  repositories are not misclassified.

## 0.1.3 - 2026-10-27

- Add C# profile and NetArchTest boundary template.

## 0.1.4 - 2026-10-27

- Add Rust profile, cargo-deny starter, and Cargo marker.
- Report the actual missing subcommand tool for `npx` and `cargo deny`.

## 0.1.5 - 2026-10-27

- Add SQL profile, migration marker, and SQLFluff starter.
- State that SQL ownership is a review rule; SQLFluff checks style only.

## 0.1.6 - 2026-10-27

- Add C++ profile, CMake layering guard, clang-tidy starter, and C++ marker.
- Generate compile commands in the verify block so clang-tidy can resolve
  targets.

## 0.1.7 - 2026-10-27

- Add C profile and C marker.
- Use clang-tidy with compile commands for C; keep cppcheck as the fallback
  when no compile database exists.

## 0.1.8 - 2026-10-27

- Add all ten language profiles: TypeScript, Python, Go, Java, JavaScript,
  C#, Rust, SQL, C, and C++.
- Add profile consistency check and document profile coverage and limits.

## 0.1.9 - 2026-10-28

- Adopt upfront coding standards and bounded legacy rules; align language profiles, examples, boundary templates, evaluations, and verifier regression checks.

## 0.2.0 - 2026-11-02

- Replace preflight/approval routing with one recursive design loop, on-demand standards disclosure, and `scripts/frontier.mjs`; rewrite evals around the loop.

## 0.2.1 - 2026-11-02

- Reduce the skill to `SKILL.md`, `references/`, and `languages/`; remove scripts, templates, evals, examples, workflows, and standards.
- Move the contract to `references/contract.md` and fix the SKILL reference.
- Trim language profiles to Structure, Preferred, and Disallowed.
- Rewrite README for the decision-only scope, manual invocation, and no runtime dependencies.

## 0.2.2 - 2026-11-02

- Rewrite `SKILL.md` around an explicit precedence chain, reference-loading triggers, and a handoff step; enable model invocation.
- Tighten `references/defaults.md` and `references/contract.md` to one line per rule.
- Rewrite README for users: problem, proof, why decide first, and before/after.

## 0.2.3 - 2026-11-02

- Add `languages/agent-instructions.md` profile for skills, `AGENTS.md`, and `CLAUDE.md`.
- Route SKILL reference loading and README language coverage to the new profile.

## 0.2.4 - 2026-11-02

- Make `SKILL.md` write every loop step to `.agents/design/decisions.md`, add a condense prerequisite, and loop steps 2-4 to a stop test.
- Move the record format above the example and retarget the handoff to a readability edit pass.

## 0.2.5 - 2026-11-02

- Restate `references/contract.md` rules as questions, add a one-line ownership summary, and spell out the three resource owners.

## 0.2.6 - 2026-11-02

- Expand `references/defaults.md` rules 2-4 with drift, local-reasoning, and boundary-detail clarifications.

## 0.2.7 - 2026-11-02

- Use "SWE" instead of "competent implementers" in the Challenge step.

## 0.2.8 - 2026-11-02

- README: lead with "Unslop your project"; credit Matt Pocock's grilling skill as loop inspiration; drop the sample record block.

## 0.2.9 - 2026-11-03

- Add `scripts/designflow.py` state machine to drive the loop; prompts carry precedence and absolute paths to defaults, contract, and language profiles.
- Slim `SKILL.md` to purpose, run steps, and record format; loop text now owned by the script.
- Record moves to `.agents/design/decisions.json`: one set per goal (G#), decisions keep D#, status, optional `after`/`rationale`. Schema at `references/decisions.schema.json`; script validates it.
- `start` replaces any existing `workflow.json`; finishing deletes it. Drop `next`/`reset` and the condense step.
- Handoff deletes `decisions.md` and has the agent rewrite it once from the JSON in ASD-STE100 Simplified Technical English.
- Add `tests/test_designflow.py` (stdlib unittest).
- README: Python 3.9+ requirement, script loop section, updated file table.

## 0.2.10 - 2026-11-03

- Rename `languages/agent-instructions.md` to `languages/skills.md`; skills only. Two structures: Progressive Disclosure and Workflow, chosen by what the agent holds at once. Add `references/workflow.py` template and tests.

## 0.3.0 - 2026-11-03

- README rewritten around intent, the script-driven loop, and honest open questions; trim install, quick start, and file table.

## 0.3.1 - 2026-11-03

- Windows support: docs give `python` alongside `python3`; printed `done` commands quote paths with double quotes on Windows so the full interpreter path is runnable there.
- Tests cover printed command interpreter and Windows quoting.

## 0.3.2 - 2026-11-03

- Permanent design sessions in `workflow.json`: `s1`, `s2`, ...; `status`, `status --session`, `done --session`, and `abandon`; one active session per goal; atomic `workflow.lock`; migration from old single-run state. Remove the `handoff` phase and `decisions.md`; zero-gap challenge prints the session close summary. Update `SKILL.md`, `README.md`, `languages/skills.md`, and tests.

## 0.3.3 - 2026-11-04

- Agent edits the record only through the CLI: `done` reads a JSON payload on stdin (goal fields plus `decisions` rows upserted by `id`; `null` removes a field; `drop` deletes; `status` derived from `answer`), applies it to the session's goal under the lock, and writes nothing on error. Each step prints the session goal as JSON and the next free D#. Remove `--goal` and `--gaps`: ground creates or reuses a goal from the payload. Challenge closes only on an unchanged goal; any change starts a fresh challenge, via decide when rows are open. `SKILL.md` drops its Files and Format sections; prompts no longer name `decisions.json` or the schema. Update `README.md`, `languages/skills.md`, and tests.

## 0.3.4 - 2026-11-04

- Split `scripts/designflow.py` into a CLI entry point plus `scripts/designlib/` (`flow`, `steps`, `sessions`, `record`, `storage`, `config`), one owner each; a test enforces one-way imports.
- Challenge limit: optional `metadata.max-challenges` in `SKILL.md` frontmatter, default 3. At the limit the session closes; open gaps from the last challenge get one final decide; summary lists remaining open questions. Step header shows `LOOP: n/max`.
