# 0002. Standard-library-only Python scripts

- Status: accepted (retroactive)
- Date: 2026-11-06

## Context

`scripts/` is copied with the skill and must run from a checkout without an install step. The scripts claim Python 3.9+ support.

## Decision

`audit.py`, `validate.py`, `workflow.py`, and `workflowlib/` import only the Python standard library. Optional checks degrade to `skipped` when `tomllib` (Python 3.11+) or PyYAML is unavailable.

## Consequences

- The skill has no runtime dependencies or dependency lockfile; `mise` pins only the development toolchain.
- Feature detection is required: TOML validation on Python 3.9/3.10 and YAML validation without PyYAML are skipped, not failed.
- Reviewers must keep this rule when editing `scripts/`; `tests/test_imports.py` enforces the import edges and standard-library-only rule.
