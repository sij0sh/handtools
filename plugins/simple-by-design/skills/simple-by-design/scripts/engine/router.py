"""Fixed prompt transitions; no ledger or agent-selected next step."""

from copy import deepcopy
import re
import uuid


class DispatchError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DispatchError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


# Required result fields, beside the transitions they support.
DECISION = ("id", "choice", "basis", "alternative", "tradeoff", "revisit")
GAP = ("check", "witness", "decision")
RESOLUTION = ("witness", "answer", "basis")
CHECKS = ("pair", "defeater", "decision", "unknown")
CANDIDATE = ("summary", "criteria", "decisions")
RESULTS = {
    "draft": {"candidate": CANDIDATE},
    "review": {"pass": (*CHECKS, "basis"), "revise": ("gaps",)},
    "resolve": {"resolved": (*CANDIDATE, "resolutions"), "blocked": ("question", "needs")},
}
# One pass, no loops: draft → review → complete, or review → resolve → complete.
PHASES = ("draft", "review", "resolve", "blocked", "complete")
PROMPTS = {"draft": "draft", "review": "review", "resolve": "resolve", "blocked": "resolve"}


def record(value, keys, name):
    require(isinstance(value, dict) and set(value) == set(keys)
            and all(text(value[key]) for key in keys),
            f"{name} requires only nonempty {', '.join(keys)}")
    return value


def items(value, name, check, empty=False):
    require(isinstance(value, list) and (empty or value), f"{name} must be a{'' if empty else ' nonempty'} list")
    for item in value:
        check(item)
    return value


def decisions(value):
    items(value, "decisions", lambda item: record(item, DECISION, "decision"), empty=True)
    ids = [item["id"] for item in value]
    require(len(ids) == len(set(ids)), "decision ids must be unique")


def gap(value):
    record(value, GAP, "gap")
    require(value["check"] in CHECKS, f"gap check must be {' | '.join(CHECKS)}")


SHAPES = {
    "criteria": lambda value: items(value, "criteria", lambda item: require(text(item), "criteria must be nonempty text")),
    "decisions": decisions,
    "gaps": lambda value: items(value, "gaps", gap),
    "resolutions": lambda value: items(value, "resolutions", lambda item: record(item, RESOLUTION, "resolution")),
}


def covers(gaps, resolutions):
    require(sorted(item["witness"] for item in resolutions) == sorted(item["witness"] for item in gaps),
            "resolutions must answer each gap once, quoting its witness")


def new(request):
    require(text(request), "--request must be nonempty text")
    return {"schema_version": 5, "phase": "draft", "ticket": uuid.uuid4().hex,
            "request": request}


def prompt(document):
    require(document["phase"] in PROMPTS, "checkpoint is not awaiting a result")
    return PROMPTS[document["phase"]]


def validate(document):
    require(isinstance(document, dict), "invalid checkpoint")
    version = document.get("schema_version")
    if type(version) is int and version in (1, 2, 3, 4):
        raise DispatchError(
            f"legacy checkpoint (schema {version}); move .agents/decision.json aside, "
            "then start with --request")
    require(type(version) is int and version == 5,
            "unsupported checkpoint schema; move .agents/decision.json aside, "
            "then start with --request")
    phase = document.get("phase")
    require(isinstance(phase, str) and phase in PHASES, "invalid checkpoint phase")

    required = {"schema_version", "phase", "request"}
    if phase != "complete":
        required.add("ticket")
    if phase != "draft":
        required.add("candidate")
    if phase in ("resolve", "blocked"):
        required.add("gaps")
    if phase == "blocked":
        required.add("blocked_on")
    if phase == "complete":
        required.update(("review",) if "review" in document else ("gaps", "resolutions"))
    require(set(document) == required, "invalid checkpoint fields")

    if "ticket" in document:
        ticket = document["ticket"]
        require(isinstance(ticket, str) and re.fullmatch(r"[0-9a-f]{32}", ticket),
                "invalid checkpoint ticket")
    require(text(document["request"]), "invalid checkpoint request")
    if "candidate" in document:
        require(isinstance(document["candidate"], dict), "invalid checkpoint candidate")
        check_result("draft", {"status": "candidate", **document["candidate"]})
    if "gaps" in document:
        SHAPES["gaps"](document["gaps"])
    if "blocked_on" in document:
        record(document["blocked_on"], ("question", "needs"), "blocked_on")
    if "resolutions" in document:
        SHAPES["resolutions"](document["resolutions"])
        covers(document["gaps"], document["resolutions"])
    if "review" in document:
        require(isinstance(document["review"], dict), "invalid checkpoint review")
        check_result("review", {"status": "pass", **document["review"]})
    return document


def check_result(prompt, result):
    require(isinstance(result, dict), "result must be a JSON object")
    status = result.get("status")
    require(isinstance(status, str) and status in RESULTS[prompt],
            f"{prompt} status must be {' | '.join(RESULTS[prompt])}")
    fields = RESULTS[prompt][status]
    require(set(result) == {"status", *fields}, f"{status} requires only status and {', '.join(fields)}")
    for key in fields:
        if key in SHAPES:
            SHAPES[key](result[key])
        else:
            require(text(result[key]), f"{key} must be nonempty text")
    return status


def body(result):
    return {key: value for key, value in result.items() if key != "status"}


def advance(document, result):
    validate(document)
    require(document["phase"] != "complete", "run is not accepting results")
    status = check_result(prompt(document), result)
    result = body(deepcopy(result))  # Never alias caller-owned lists into the checkpoint.
    updated = deepcopy(document)
    updated["ticket"] = uuid.uuid4().hex
    if status == "candidate":
        updated.update(phase="review", candidate=result)
    elif status == "pass":
        updated.update(phase="complete", review=result)
    elif status == "revise":
        updated.update(phase="resolve", gaps=result["gaps"])
    elif status == "blocked":
        updated.update(phase="blocked", blocked_on=result)
    elif status == "resolved":
        covers(document["gaps"], result["resolutions"])
        updated.update(phase="complete", resolutions=result.pop("resolutions"), candidate=result)
        updated.pop("blocked_on", None)
    if updated["phase"] == "complete":
        updated.pop("ticket")
    return validate(updated)
