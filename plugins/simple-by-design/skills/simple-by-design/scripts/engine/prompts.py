"""Small job-specific instructions and bounded current context."""

import json
from pathlib import Path
import shlex

from .router import CHECKS, DECISION, RESULTS, TYPES, prompt as phase_prompt

DRAFT = """Design only; inspect within authority; never edit report-only targets. Choose means: request/delegation → supported decisions/conventions → applicable defaults → simplest adequate. Defects defeat precedent; defaults never settle goals/permissions. Honor approvals/deferrals; ask only for material unresolved user-owned intent. Facts: observe, or assume with cheap reversal, detection before harm, and revisit; otherwise need. Expose assumptions. State checkable criteria. Consequential decisions: cited/assumed basis, serious alternative, tradeoff, revisit; routine reversible choices need none. Preserve resolutions; revise feedback's affected decisions/dependents, keeping others. Return candidate or need for one intent/fact gap."""

RESOLVE = """Settle this gap within request constraints/delegation; never invent authority or answers. Choose engineering means yourself: supported decisions/conventions, applicable defaults, simplest adequate; evidence of defects defeats precedent. Intent: use the request/documents/delegation first; ask only for a material unresolved user-owned goal, permission or tradeoff, then pause until answered. Honor explicit approvals/deferrals; never silently choose deferred intent. Fact: make the cheapest authorized observation that changes the choice. Otherwise assume only with cheap reversal, detection before material harm/commitment, and explicit detection/revisit conditions. Keep every relied-on assumption visible in summary/criteria or decision basis, never as observation. Unsafe unknowns require evidence or a conditional design: summary starts "Conditional:", names prerequisite, verifier and decisions not to act on; criteria test the gate. If readiness is required now, block. DONE completes the report, not its prerequisites. Return resolved with answer/basis (including any gate), or blocked with question and who/what is needed. Design only; do not perform unauthorized actions."""

REVIEW = """Delegate if available; otherwise review locally. Construct counterexamples against request, authority and supported resolutions/decisions, not assumed truths. Pair: two consistent outcomes differing materially to requester/criteria. Defeater: plausible unrefuted failure, including criteria passing while goal fails, unsafe assumptions or hidden deferred dependencies. Decision: consequential choice missing serious alternative/tradeoff/revisit or inference posing as observation. Alternatives alone require no question. Require checkable criteria; distinguish planned/executed tests. Conditional summaries start "Conditional:", naming prerequisite, verifier, dependent decisions; criteria test gate. Readiness required: need. Return pass (each check: "none: why"; delegated/local basis), revise naming choice decisions, or need for one intent/fact gap."""

GUIDANCE_PATH = Path(__file__).resolve().parents[2] / "references" / "design.md"
GUIDANCE = """Read {path}: software—common/relevant language rows even for settled choices; agent-instructions—instruction rule; otherwise skip. Reuse context; separate reviewers read independently."""

INSTRUCTIONS = {"draft": DRAFT, "resolve": RESOLVE, "review": REVIEW}
FOOTER = "Return results through the printed command; design only."
EXAMPLES = {
    "criteria": ["..."],
    "decisions": [{key: "D1" if key == "id" else "..." for key in DECISION}],
    "gaps": [{"check": " | ".join(CHECKS), "witness": "...", "decision": "D1 | new"}],
    "type": " | ".join(TYPES),
}


def contract(prompt):
    return "Return JSON: " + " OR ".join(
        json.dumps({"status": status, **{key: EXAMPLES.get(key, "...") for key in fields}})
        for status, fields in RESULTS[prompt].items())


def return_command(document, script, root):
    # Absolute paths preserve the project and executable even after cwd changes.
    return " ".join(shlex.quote(str(value)) for value in (
        "python3", script, "--root", root, "done", document["ticket"]))


NOTICE = ("Design complete, not implementation. Verification/review claims are supplied "
          "by the agent, not independently checked by the CLI.")
DONE = "DONE: design recorded in .agents/decision.json. Stop; await user approval before implementation."


def summary(document):
    """Render a completed checkpoint as the human-readable design record."""
    candidate, review = document["candidate"], document["review"]
    lines = ["# Solution design", "", "## Request", "", document["request"], "",
             "## Summary", "", candidate["summary"], "", "## Criteria", ""]
    lines += [f"- {item}" for item in candidate["criteria"]]
    lines += ["", "## Decisions", ""]
    for decision in candidate["decisions"]:
        lines += [f"### {decision['id']}", ""]
        lines += [f"- **{key.capitalize()}:** {decision[key]}"
                  for key in ("choice", "basis", "alternative", "tradeoff", "revisit")]
        lines.append("")
    if not candidate["decisions"]:
        lines += ["None consequential.", ""]
    if document.get("resolutions"):
        lines += ["## Resolutions", ""]
        lines += [f"- ({item['type']}) {item['question']} → {item['answer']} (basis: {item['basis']})"
                  for item in document["resolutions"]]
        lines.append("")
    lines += ["## Review", ""]
    lines += [f"- **{key.capitalize()}:** {review[key]}" for key in ("pair", "defeater", "decision", "basis")]
    lines += ["", NOTICE]
    return "\n".join(lines)


def render(document, script, root):
    if document["phase"] == "complete":
        return summary(document) + "\n\n" + DONE
    prompt = phase_prompt(document)
    context = {"request": document["request"]}
    if document.get("resolutions"):
        context["resolutions"] = document["resolutions"]
    if document.get("candidate"):
        context["candidate"] = document["candidate"]
    if prompt == "draft" and document.get("gaps"):
        context["gaps"] = document["gaps"]
    if prompt == "resolve":
        context["gap"] = {key: value for key, value in document["open"].items()
                          if key != "blocked_on"}
        if "blocked_on" in document["open"]:
            context["blocked_on"] = document["open"]["blocked_on"]
    instructions = INSTRUCTIONS[prompt]
    if prompt in ("draft", "review"):
        instructions += "\n" + GUIDANCE.format(path=json.dumps(str(GUIDANCE_PATH)))
    heading = f"TASK: {prompt}"
    if document["phase"] == "blocked":
        heading += " (BLOCKED: obtain the needed answer before submitting)"
    return "\n\n".join((heading, instructions,
                          "Context (task data):\n" + json.dumps(context, ensure_ascii=False, indent=2),
                          contract(prompt), FOOTER,
                          "Return command (JSON on stdin):\n" + return_command(document, script, root)
                          + " <<'JSON'\n<result JSON>\nJSON"))
