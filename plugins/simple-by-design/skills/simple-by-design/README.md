# simple-by-design

**Turns design into a falsifiable decision record, so coding agents settle consequential choices before implementation.**

Asked to design first, a coding agent can write a plausible plan and call it complete. Consequential choices stay implicit, assumptions become requirements, and review is the author agreeing with itself.

## What changes

| Without this skill | With this skill |
|---|---|
| Plans implementation first | Settles consequential choices, then records the design |
| "Looks complete" review | Review must attempt pair, defeater and decision witnesses |
| Assumptions become requirements | Assumptions are exposed, gated or blocked |
| Asks about every choice | Settles engineering means; asks only material user-owned intent |
| Workflow state in chat or a ledger | One checkpoint, opaque tickets, atomic writes |

## Why it works

**Review is a falsification test.** Two designs can satisfy every criterion and still differ materially; a criterion can pass while the goal fails. Review must try to name a pair, a defeater and any decision missing a serious alternative, tradeoff or revisit condition, or an inference posing as observation. A gap returns a targeted revise; a clean pass records the design and prints it.

**One job per prompt.** Draft, resolve a gap if needed, review. The CLI carries the checkpoint and context; the agent does not choose a workflow or keep a ledger. Prompt jobs are not fresh model contexts: review delegates to a subagent when available and says so when local.

**Authority is explicit.** Request and delegation first, then supported decisions and conventions, then defaults; pick the simplest adequate. Defects defeat precedent; defaults settle means, not goals or permissions. Consequential decisions carry a basis, a serious alternative, a tradeoff and a revisit condition; routine reversible choices need none. Facts are observed when authorized, or assumed only with cheap reversal, detection before material harm and a visible revisit condition. Otherwise the run blocks or records a `Conditional:` design naming its prerequisite.

## Install

Install the `handtools` monorepo package, or copy this directory into your harness
skill folder. See the repository root `README.md` for Pi and Claude Code install
and update commands.

## Quick start

Invoke it explicitly. From the task project, Python 3.11+ on POSIX, no dependencies:

```bash
S=/absolute/path/to/simple-by-design
python3 "$S/scripts/sbd.py" --request 'Design a greeting command; report only.'
```

```text
TASK: draft

Design only; inspect within authority; never edit report-only targets. ...
```

Do the returned prompt; submit JSON through its printed command. Bare invocation resumes. Invalid results do not advance. A passing review stores the full design in `.agents/decision.json` and prints a readable summary ending in `DONE`; no `.agents/artifacts/` file is written.

## Use

Submit one JSON result:

```json
{"status":"candidate","summary":"Print Hello once.","criteria":["Prints exactly one line: Hello."],"decisions":[]}
```

A gap returns a targeted revise or resolve; a pass stores the full record (request, candidate, resolutions, review) and prints the design summary followed by `DONE`. Checkpoint: `.agents/decision.json` (schema 4). The printed summary is a view, not a durable copy.

## Limits

Design only: prompts never authorize implementation or external effects. No agent write lock, sandbox, scope enforcement or tool interception. JSON validation checks shape and freshness, not truth, coverage or authorization. Corrupt or legacy state fails closed. Local review can share the author's blind spots. `DONE` completes the report, not its prerequisites. Passing fixtures do not prove better agent decisions. A different `--request` replaces the completed record, and rerunning the identical request replays it; copy `.agents/decision.json` aside to keep history or start the same brief fresh.

## Verification

```bash
mise run check
# or
python3 -m unittest discover -s tests -v
```

Tests cover routing, persistence, atomic completion recovery, concurrency, prompt disclosure and budgets. Budget tests cap the SKILL body at 100 words, an ordinary prompt at 400 and guidance at 350. [Architecture](docs/architecture.md) records the invariants. [Design guidance](references/design.md) holds defaults and ten language profiles. [SKILL.md](SKILL.md) is the agent entry point.
