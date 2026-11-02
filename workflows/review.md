# Review

Findings and verification evidence for implement-phase work. `SKILL.md` owns the
loop; `standards/contract.md` owns the rules.

## Findings

Give location, consequence, and action:

- **Blocker:** correctness or safety defect, introduced check failure, unapproved
  requirement violation, or uncertainty that prevents confidence in correctness.
  Resolve before claiming completion.
- **Fix now:** in-scope correction required by the agreed change. Agree the scope
  first if fixing it would materially expand the change.
- **Note:** non-blocking follow-up or reproduced legacy finding outside scope.

A baseline failure is not automatically a blocker, but one that prevents safe
implementation or trustworthy verification still needs a decision. A reported
limitation is never a passing check.

## Evidence

Classify each required check as passed, introduced failure, reproduced baseline
failure, unavailable, or not run. Compare baseline findings by identity and
scope, never only by count, and never bless new failures by editing the baseline.
Non-strict skips and exit zero alone are not proof. Re-run affected checks after
fixes.

`scripts/verify.sh` runs with the target repository as working directory;
`--strict` fails on missing tools or undetected checks. A repository entrypoint
replaces profile fallbacks, so confirm its coverage instead of assuming it.
