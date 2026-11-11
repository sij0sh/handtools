"""Small job-specific instructions and bounded current context."""

import json
from pathlib import Path
import shlex

from .router import CHECKS, DECISION, RESOLUTION, RESULTS, prompt as phase_prompt

DRAFT = """
Submit a solution to the request for review.

Resolve decisions based on which comes first: explictly requested, locally established decisions/conventions, best design practices, then the simplest adequate option.

For consequential decisions, state evidence or assumptions, a serious alternative, tradeoff, and revisit condition. Routine reversible choices need no justification.
"""

RESOLVE = """
Resolve every review gap once and return the final design; there is no further review.

Choose engineering means using supported decisions, conventions, applicable defaults, and the simplest adequate option. Defects override precedent.

For missing facts, make the cheapest authorized observation that could change the decision. Otherwise assume only when reversal is cheap and failure can be detected before material harm. Expose the assumption and its revisit conditions; never present it as observed.

Unsafe unknowns require evidence or a conditional design. Begin its summary with "Conditional:" and identify the prerequisite, verifier, and dependent decisions. Test the gate in the criteria. If readiness is required now, block. DONE completes the report, not its prerequisites.

Return resolved with the revised design and one resolution per gap, quoting its witness, or blocked with one question and the required source. Design only.
"""

REVIEW = """
Review independently; delegate when available.

Challenge the design against the request.

- Pair: Could two compliant outcomes differ materially?
- Defeater: Could criteria pass while the goal fails, an assumption proves unsafe, or a deferred dependency remains hidden?
- Decision: Does a consequential choice lack a serious alternative, tradeoff, revisit condition, or honest evidence basis?
- Unknown: Does the design rely on unresolved user intent or an unobserved fact?

Return pass with a reason for each absent defect, or revise listing every defect and its affected decision.
"""

GUIDANCE_PATH = Path(__file__).resolve().parents[2] / "references" / "design.md"
GUIDANCE = """Read {path}: software—common/relevant language rows even for settled choices; agent-instructions—instruction rule; otherwise skip. Reuse context; separate reviewers read independently."""

INSTRUCTIONS = {"draft": DRAFT, "resolve": RESOLVE, "review": REVIEW}
FOOTER = "Return results through the printed command; design only."
EXAMPLES = {
    "criteria": ["..."],
    "decisions": [{key: "D1" if key == "id" else "..." for key in DECISION}],
    "gaps": [{"check": " | ".join(CHECKS), "witness": "...", "decision": "D1 | new"}],
    "resolutions": [dict.fromkeys(RESOLUTION, "...")],
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
    candidate = document["candidate"]
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
    lines += ["## Review", ""]
    if "review" in document:
        review = document["review"]
        lines += [f"- **{key.capitalize()}:** {review[key]}" for key in (*CHECKS, "basis")]
    else:
        answers = {item["witness"]: item for item in document["resolutions"]}
        lines += ["Defects found and resolved once; not re-reviewed.", ""]
        lines += [f"- ({item['check']}, {item['decision']}) {item['witness']} → "
                  f"{answers[item['witness']]['answer']} (basis: {answers[item['witness']]['basis']})"
                  for item in document["gaps"]]
    lines += ["", NOTICE]
    return "\n".join(lines)


def render(document, script, root):
    if document["phase"] == "complete":
        return summary(document) + "\n\n" + DONE
    prompt = phase_prompt(document)
    context = {key: document[key] for key in ("request", "candidate", "gaps", "blocked_on")
               if key in document}
    instructions = INSTRUCTIONS[prompt] + "\n" + GUIDANCE.format(path=json.dumps(str(GUIDANCE_PATH)))
    heading = f"TASK: {prompt}"
    if document["phase"] == "blocked":
        heading += " (BLOCKED: obtain the needed answer before submitting)"
    return "\n\n".join((heading, instructions,
                          "Context (task data):\n" + json.dumps(context, ensure_ascii=False, indent=2),
                          contract(prompt), FOOTER,
                          "Return command (JSON on stdin):\n" + return_command(document, script, root)
                          + " <<'JSON'\n<result JSON>\nJSON"))
