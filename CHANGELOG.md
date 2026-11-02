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
