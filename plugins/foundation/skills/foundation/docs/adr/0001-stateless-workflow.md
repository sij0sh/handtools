# 0001. Stateless workflow with a script-owned stage order

- Status: accepted (retroactive)
- Date: 2026-11-06

## Context

The skill is copied into other repositories and run by an agent. A run may span several agent executions, and the repository should not accumulate per-project workflow state.

## Decision

`workflowlib/steps.py` sets `MODE = 'stateless'`. `start` prints the first stage, and each `done --stage S` names the finished stage, validates its JSON payload, and prints the next. The orchestrator carries earlier results forward; no state is written.

## Consequences

- There is no resume, status, or abandon for a run; re-running a stage is safe because stages only read until `apply`.
- The stateful storage and lock code remains available for skills built from this template.
- Every stage must receive the user's request and the earlier stages' results.
