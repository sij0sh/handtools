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
NEED = ("type", "question", "witness", "consequence")
RESULTS = {
    "draft": {"candidate": ("summary", "criteria", "decisions"), "need": NEED},
    "resolve": {"resolved": ("answer", "basis"), "blocked": ("question", "needs")},
    "review": {"pass": ("pair", "defeater", "decision", "basis"), "revise": ("gaps",),
               "need": NEED},
}
DECISION = ("id", "choice", "basis", "alternative", "tradeoff", "revisit")
GAP = ("check", "witness", "decision")
CHECKS = ("pair", "defeater", "decision")
TYPES = ("intent", "fact")
PHASES = ("draft", "resolve", "blocked", "review", "complete")
PROMPTS = {"draft": "draft", "resolve": "resolve", "blocked": "resolve", "review": "review"}


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


def need(value):
    record(value, NEED, "need")
    require(value["type"] in TYPES, f"need type must be {' | '.join(TYPES)}")


def open_gap(value):
    require(isinstance(value, dict), "invalid checkpoint open")
    keys = set(NEED)
    if "blocked_on" in value:
        keys.add("blocked_on")
    require(set(value) == keys, "invalid checkpoint open fields")
    need({key: value[key] for key in NEED})
    if "blocked_on" in value:
        record(value["blocked_on"], ("question", "needs"), "blocked_on")


def resolution(value):
    record(value, ("type", "question", "answer", "basis"), "resolution")
    require(value["type"] in TYPES, "invalid resolution type")


SHAPES = {
    "criteria": lambda value: items(value, "criteria", lambda item: require(text(item), "criteria must be nonempty text")),
    "decisions": decisions,
    "gaps": lambda value: items(value, "gaps", gap),
    "type": lambda value: require(value in TYPES, f"type must be {' | '.join(TYPES)}"),
}


def new(request):
    require(text(request), "--request must be nonempty text")
    return {"schema_version": 4, "phase": "draft", "ticket": uuid.uuid4().hex,
            "request": request}


def prompt(document):
    require(document["phase"] in PROMPTS, "checkpoint is not awaiting a result")
    return PROMPTS[document["phase"]]


def validate(document):
    require(isinstance(document, dict), "invalid checkpoint")
    version = document.get("schema_version")
    if type(version) is int and version in (1, 2, 3):
        raise DispatchError(
            f"legacy checkpoint (schema {version}); move .agents/decision.json aside, "
            "then start with --request")
    require(type(version) is int and version == 4,
            "unsupported checkpoint schema; move .agents/decision.json aside, "
            "then start with --request")
    phase = document.get("phase")
    require(isinstance(phase, str) and phase in PHASES, "invalid checkpoint phase")

    allowed = {"schema_version", "phase"}
    required = {"schema_version", "phase"}
    if phase == "complete":
        allowed.update(("request", "candidate", "review", "resolutions"))
        required.update(("request", "candidate", "review"))
    else:
        allowed.update(("ticket", "request"))
        required.update(("ticket", "request"))
        if phase == "draft":
            allowed.update(("candidate", "gaps", "resolutions"))
        elif phase in ("resolve", "blocked"):
            allowed.update(("candidate", "gaps", "resolutions", "open"))
            required.add("open")
        elif phase == "review":
            allowed.update(("candidate", "resolutions"))
            required.add("candidate")
    require(set(document) <= allowed, "invalid checkpoint fields")
    require(required <= set(document), "missing checkpoint fields")

    if "ticket" in document:
        ticket = document["ticket"]
        require(isinstance(ticket, str) and re.fullmatch(r"[0-9a-f]{32}", ticket),
                "invalid checkpoint ticket")
    if "request" in document:
        require(text(document["request"]), "invalid checkpoint request")
    if "candidate" in document:
        require(isinstance(document["candidate"], dict), "invalid checkpoint candidate")
        check_result("draft", {"status": "candidate", **document["candidate"]})
    if "gaps" in document:
        items(document["gaps"], "gaps", gap)
    if "open" in document:
        open_gap(document["open"])
        require((phase == "blocked") == ("blocked_on" in document["open"]),
                "checkpoint open/phase mismatch")
    if "resolutions" in document:
        items(document["resolutions"], "resolutions", resolution)
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
    require(document["phase"] in ("draft", "resolve", "blocked", "review"),
            "run is not accepting results")
    status = check_result(prompt(document), result)
    result = deepcopy(result)  # Never alias caller-owned lists into the checkpoint.
    updated = deepcopy(document)
    if status == "candidate":
        updated.update(phase="review", candidate=body(result))
        updated.pop("gaps", None)
    elif status == "need":
        updated.update(phase="resolve", open=body(result))
    elif status == "resolved":
        source = document["open"]
        updated["resolutions"] = updated.get("resolutions", []) + [{
            "type": source["type"], "question": source["question"],
            "answer": result["answer"], "basis": result["basis"]}]
        updated["phase"] = "draft"
        updated.pop("open", None)
    elif status == "blocked":
        updated["open"] = {**updated["open"], "blocked_on": body(result)}
        updated["phase"] = "blocked"
    elif status == "revise":
        updated.update(phase="draft", gaps=result["gaps"])
    elif status == "pass":
        updated.update(phase="complete", review=body(result))
        updated.pop("ticket", None)
    if status != "pass":
        updated["ticket"] = uuid.uuid4().hex
    return validate(updated)
