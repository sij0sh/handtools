# 0002. Engine never writes the target instruction

- Status: accepted (retroactive)
- Date: 2026-11-11

## Context

The engine coordinates phases by storing state under `.agents/semantic-instructions.json` and printing the next prompt. A target instruction is user content; an automated write during framing or composing would be destructive. Revision quality is bounded by time and passes.

## Decision

The engine writes only its own state. It emits an output contract after the challenge phase and leaves the target write or inline return to the agent. It fingerprints the target when framing and rejects a challenge result if the target changed first. Revision is capped at two passes; a third defect completes the run with the defect recorded as an unresolved risk.

## Consequences

- Target edits are always the agent's action, so safety depends on the agent following the output contract.
- State is local to the target project and should stay gitignored.
- A defect found after two revisions is reported, not fixed.
- `tests/test_semantic_flow.py` asserts the target is absent after completion.
