"""Independent per-dimension observations and checkpoint claim comparisons.

An observation says what one piece of original evidence shows for one dimension:
requested, edited, verified, committed, pushed, live-confirmed or blocked/remaining.
Tool success, test success, commit, push and live confirmation never collapse into one
completion state. Checkpoint statements stay claims; a comparison is emitted only when
dimension, lane, branch and time scope make it deterministic.
"""
import json
import re

DIMENSIONS = ("requested", "edited", "verified", "committed", "pushed", "live_confirmed",
              "blocked_remaining")

TEST_COMMAND = re.compile(
    r"(?:\bpytest\b|\bpython[0-9.]*\s+-m\s+(?:pytest|unittest)\b|\bunittest\s+discover\b|"
    r"\bnpm\s+(?:run\s+)?test\b|\b(?:yarn|pnpm|bun)\s+(?:run\s+)?test\b|\bgo\s+test\b|"
    r"\bcargo\s+test\b|\bmake\s+test\b|\btox\b|\bmvn\s+test\b|\bgradle\w*\s+test\b)", re.IGNORECASE)
PUSH_COMMAND = re.compile(r"\bgit\s+push\b", re.IGNORECASE)
UNCOMMITTED = re.compile(r"\b(?:uncommitted|not\s+committed|needs?\s+commit|pending\s+commit)\b", re.IGNORECASE)
UNPUSHED = re.compile(r"\b(?:unpushed|not\s+pushed|needs?\s+push|pending\s+push)\b", re.IGNORECASE)

# Structured checkpoint fields that can be compared with recorded observations.
CLAIM_FIELDS = {
    "objective": None,
    "constraints": None,
    "completedWork": "edited",
    "modifiedFiles": "edited",
    "verificationState": "verified",
    "openIssues": "blocked_remaining",
    "nextActions": "blocked_remaining",
    "currentState": None,
    "continuedState": None,
    "continuationState": None,
    "decisions": None,
    "criticalContext": None,
}


def _text(value, limit=300):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=True)
    text = " ".join(str(value or "").split())
    return text[:limit]


def _excerpt(text, limit=220):
    text = " ".join(str(text or "").split())
    return text[:limit]


def command_kinds(command):
    """Every narrow recorded class a compound command names; unknown commands stay commands."""
    text = command or ""
    kinds = []
    if PUSH_COMMAND.search(text):
        kinds.append("push")
    if TEST_COMMAND.search(text):
        kinds.append("test")
    return kinds


def _obs(dimension, value, evidence_kind, basis, source, **extra):
    row = {"section": "observation", "observation_id": f"{source.get('recording_id')}#{source.get('operation_id') or source.get('witness_id') or source.get('ref')}",
           "dimension": dimension, "value": value, "evidence_kind": evidence_kind, "basis": basis,
           "recording_id": source.get("recording_id"), "lane": source.get("lane"),
           "branch": source.get("branch"), "order": source.get("order"),
           "timestamp": source.get("timestamp"),
           "ref": source.get("ref") or source.get("call_ref") or source.get("result_ref")}
    for key in ("operation_id", "witness_id", "sha", "subject", "excerpt", "paths"):
        if extra.get(key) is not None or source.get(key) is not None:
            row[key] = extra.get(key, source.get(key))
    return row


def _groups(operations):
    found = {}
    for row in operations:
        found.setdefault(row.get("operation_id"), []).append(row)
    return found


def observations(request_event, operations, witnesses, checkpoints=()):
    """One observation per dimension/evidence item; operation/path rows never multiply it."""
    rows = []
    if request_event is not None:
        row = _obs("requested", _excerpt(request_event.get("text"), 400), "human", "recorded_request",
                   request_event, excerpt=_excerpt(request_event.get("text")))
        row["observation_id"] = f"{request_event.get('recording_id')}#request:{request_event.get('event_id')}"
        rows.append(row)
    for operation_id, group in _groups(operations).items():
        base = group[0]
        paths = sorted({item.get("path") for item in group if item.get("path")})
        common = {"paths": paths[:8]} if paths else {}
        action, outcome = base.get("action"), base.get("outcome")
        if action == "file_edit" and outcome == "succeeded" and base.get("basis") == "recorded_tool":
            rows.append(_obs("edited", "confirmed_edit", "tool_observation", "successful_native_edit",
                             base, **common))
        elif action == "file_edit" and outcome == "succeeded" and base.get("basis") == "planning_snapshot":
            rows.append(_obs("edited", "observed_snapshot", "tool_observation", "planning_snapshot",
                             base, **common))
        elif action == "plan_snapshot" and outcome == "succeeded":
            rows.append(_obs("edited", "observed_snapshot", "tool_observation", "planning_snapshot",
                             base, **common))
        if outcome == "failed":
            rows.append(_obs("blocked_remaining", "failed_attempt", "tool_observation",
                             f"{base.get('tool') or action}_failed", base, **common))
        kinds = command_kinds(base.get("command")) if action == "command" else []
        if "test" in kinds and outcome in ("succeeded", "failed"):
            rows.append(_obs("verified", f"test_run_{'passed' if outcome == 'succeeded' else 'failed'}",
                             "tool_observation", "recorded_test_result", base,
                             excerpt=_excerpt(base.get("command"))))
        if "push" in kinds and outcome in ("succeeded", "failed"):
            rows.append(_obs("pushed", f"push_{'succeeded' if outcome == 'succeeded' else 'failed'}",
                             "tool_observation", "recorded_push_result", base,
                             excerpt=_excerpt(base.get("command"))))
    for witness in witnesses:
        if witness.get("relation", "commit") != "commit":
            continue
        value, kind, basis = "unresolved", "tool_observation", witness.get("basis") or "unresolved"
        if witness.get("failed"):
            value, basis = "commit_failed", "recorded_commit_failure"
        elif witness.get("confidence") == "recorded" and witness.get("sha"):
            value, kind, basis = witness["sha"], "git_fact", f"{witness.get('basis') or 'recorded'}_witness"
        elif witness.get("confidence") == "inferred" and witness.get("sha"):
            value, kind, basis = "subject_inferred", "context", "repo_subject_inference"
        row = _obs("committed", value, kind, basis, witness,
                   witness_id=witness.get("witness_id"), sha=witness.get("sha") or witness.get("recorded_sha"),
                   subject=witness.get("subject"))
        row["observation_id"] = f"{witness.get('recording_id')}#witness:{witness.get('witness_id')}"
        rows.append(row)
    for checkpoint in checkpoints:
        for claim in claims_for(checkpoint, include_commit_state=False):
            if claim.get("dimension") == "blocked_remaining":
                rows.append(_obs("blocked_remaining", claim["value"], "checkpoint_claim", "checkpoint_claim",
                                 {"recording_id": checkpoint.get("recording_id"),
                                  "lane": checkpoint.get("lane"), "branch": checkpoint.get("branch"),
                                  "order": checkpoint.get("order"), "timestamp": checkpoint.get("timestamp"),
                                  "ref": checkpoint.get("publication_ref"),
                                  "operation_id": checkpoint.get("checkpoint_id")},
                                 checkpoint_id=checkpoint.get("checkpoint_id"),
                                 excerpt=claim.get("excerpt")))
    return rows


def claims_for(checkpoint, include_commit_state=True):
    """Claims extracted from one original checkpoint; unsupported shapes yield no claims."""
    structured = checkpoint.get("structured")
    claims = []
    if not isinstance(structured, dict):
        return claims
    for field, dimension in CLAIM_FIELDS.items():
        value = structured.get(field)
        if value in (None, "", [], {}):
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            text = _text(item)
            if not text:
                continue
            claims.append({"kind": "claim", "checkpoint_id": checkpoint.get("checkpoint_id"),
                           "field": field, "dimension": dimension, "value": text,
                           "excerpt": _excerpt(text), "evidence_kind": "checkpoint_claim",
                           "ref": checkpoint.get("publication_ref")})
    if include_commit_state:
        for field in ("currentState", "continuedState", "continuationState", "openIssues", "nextActions"):
            value = structured.get(field)
            values = value if isinstance(value, list) else [value]
            for item in values:
                text = _text(item, 500)
                if not text:
                    continue
                if UNCOMMITTED.search(text):
                    claims.append({"kind": "commit_state", "checkpoint_id": checkpoint.get("checkpoint_id"),
                                   "field": field, "dimension": "committed", "value": "uncommitted",
                                   "excerpt": _excerpt(text), "evidence_kind": "checkpoint_claim",
                                   "ref": checkpoint.get("publication_ref")})
                if UNPUSHED.search(text):
                    claims.append({"kind": "commit_state", "checkpoint_id": checkpoint.get("checkpoint_id"),
                                   "field": field, "dimension": "pushed", "value": "unpushed",
                                   "excerpt": _excerpt(text), "evidence_kind": "checkpoint_claim",
                                   "ref": checkpoint.get("publication_ref")})
    return claims


def _positive(observation, dimension):
    if observation.get("dimension") != dimension:
        return False
    if dimension == "pushed":
        return (observation.get("evidence_kind") == "tool_observation"
                and observation.get("value") == "push_succeeded")
    if observation.get("evidence_kind") not in ("git_fact",):
        return False
    return observation.get("value") not in ("commit_failed", "unresolved", "subject_inferred", None)


def compare(checkpoint, claims, observations):
    """(comparisons) for one checkpoint; never rewrites the original claim."""
    rows = []
    for claim in claims:
        if claim.get("kind") != "commit_state":
            continue
        dimension = claim.get("dimension")
        matches = [item for item in observations if _positive(item, dimension)]
        for observation in matches:
            same_lane = observation.get("lane") == checkpoint.get("lane")
            same_branch = observation.get("branch") == checkpoint.get("branch")
            if not same_lane or not same_branch:
                relation, reason = "not_comparable", "parallel_lane_or_branch"
            elif checkpoint.get("boundary_status") != "resolved" or checkpoint.get("boundary_order") is None:
                relation, reason = "not_comparable", "unresolved_coverage_boundary"
            elif observation.get("order") is None:
                relation, reason = "not_comparable", "observation_without_order"
            elif observation["order"] <= checkpoint["boundary_order"]:
                relation, reason = "contradicts", "observation_inside_covered_range"
            elif observation["order"] < (checkpoint.get("order") or 0):
                relation, reason = "later_observation", "observation_after_coverage_boundary"
            else:
                relation, reason = "later_observation", "observation_after_publication"
            rows.append({"section": "comparison", "relation": relation, "reason": reason,
                         "dimension": dimension, "checkpoint_id": checkpoint.get("checkpoint_id"),
                         "claim": claim.get("value"), "claim_ref": claim.get("ref"),
                         "observation_id": observation.get("observation_id"),
                         "observation_ref": observation.get("ref"),
                         "observation_value": observation.get("value"),
                         "observation_order": observation.get("order"),
                         "boundary_order": checkpoint.get("boundary_order"),
                         "publication_order": checkpoint.get("order")})
    return rows


def summarize(observations, claims):
    """Every dimension with its supported state; claims are not observations."""
    summary = {}
    for dimension in DIMENSIONS:
        found = [item for item in observations if item.get("dimension") == dimension]
        said = [item for item in claims if item.get("dimension") == dimension]
        values = []
        for item in found:
            value = item.get("value")
            if value is not None and value not in values:
                values.append(value)
        state = "observed" if found else "claimed" if said else "unknown"
        summary[dimension] = {"state": state, "observations": len(found), "claims": len(said),
                              "values": values[:2]}
    return summary
