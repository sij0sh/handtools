# 0002. Engine never writes the target instruction

- Status: accepted (retroactive)
- Date: 2026-11-11

## Context

The engine coordinates phases by storing state under `.agents/semantic-instructions.json` and printing the next prompt. A target instruction is user content; an automated write during framing or composing would be destructive. Revision is the calling agent's decision, not an automatic loop.

## Decision

The engine writes only its own state. It emits an output contract after the challenge phase and leaves the target write or inline return to the agent. It fingerprints the target when framing and rejects a challenge result if the target changed first. Challenge runs once; both pass and revise results complete the run, and a revise result records the finding and suggested fix for the calling agent to act on.

## Consequences

- Target edits are always the agent's action, so safety depends on the agent following the output contract.
- State is local to the target project and should stay gitignored.
- A revise recommendation is reported, not automatically applied.
- `tests/test_semantic_flow.py` asserts the target is absent after completion.
