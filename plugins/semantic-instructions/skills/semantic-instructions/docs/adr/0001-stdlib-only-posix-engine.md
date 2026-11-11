# 0001. Stdlib-only Python engine on POSIX

- Status: accepted (retroactive)
- Date: 2026-11-11

## Context

The skill is distributed by copying or symlinking this directory into an agent skills folder. Its engine must run wherever `python3` exists, with no package install, virtualenv, or lockfile. The engine persists state with `flock`, fsync, and atomic replaces.

## Decision

Target Python 3.11+ on POSIX systems, standard library only. `scripts/semantic_flow.py` imports `fcntl`; tests use `unittest`; there is no dependency manifest.

## Consequences

- No install step; consumers need only `python3`.
- Windows is unsupported.
- Third-party libraries are unavailable to the engine, including linters and test frameworks.
- Python 3.11 is the supported floor; CI must cover it.
