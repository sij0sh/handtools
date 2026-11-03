"""Target-scoped recorded signals: leads with refs, never verdicts (D67-D73).

Four kinds over the scheduled scan's operations for one file or symbol:
failed_exchange, correction_candidate, checkpoint_gap, repeated_read. Python grouping over
provider rows; nothing is persisted. Repeated reads do not prove waste; errors do not prove
reusable pitfalls; a correction is matched by phrasing only.
"""
import json

from . import trace
from .file_observations import read_pairs
from .investigate import _key, locator, noise
from .message_segments import prose, visible
from .profiles import PROFILES
from .projection import human
from .reader import message_graph
from .target_history import CORRECTION

KINDS = ("failed_exchange", "correction_candidate", "checkpoint_gap", "repeated_read")
MAX_REFS = 5
CHECKPOINT_HARNESSES = frozenset(name for name, profile in PROFILES.items()
                                 if '"emit": "checkpoint"' in json.dumps(profile))


def plan():
    return [{"step": "resolve", "detail": "one file or symbol target; ambiguity returns candidates"},
            {"step": "scan", "detail": "scheduled recording scan; invocation totals across harnesses"},
            {"step": "select", "detail": "operations on the exact repository path (symbol: mapped edit events)"},
            {"step": "group", "detail": ", ".join(KINDS)},
            {"step": "order", "detail": "round-robin across kinds, newest first within a kind"}]


def _ref(ref):
    return locator(ref) if isinstance(ref, dict) else None


def _unique(rows):
    """One row per operation; association rows of the same call share an outcome."""
    seen, out = set(), []
    for row in rows:
        if row.get("operation_id") not in seen:
            seen.add(row.get("operation_id"))
            out.append(row)
    return out


def _row(kind, anchor, excerpt, count, tools, ref, recording, **fields):
    return {"section": "signal", "id": f"{kind}:{ref}", "categories": [kind], "excerpt": excerpt,
            "count": count, "tools": sorted(t for t in tools if t), "ref": ref,
            "session": recording.get("session") if recording else None,
            "timestamp": anchor.get("timestamp") if anchor else None, **fields}


def failed_exchanges(ops, files, by_ref):
    groups = {}
    for op in ops:
        groups.setdefault((op.get("recording_id"), op.get("lane"), _key(op.get("request_ref"))
                           or op.get("turn")), []).append(op)
    rows, skipped = [], 0
    for group in groups.values():
        failures = []
        for op in group:
            if op.get("outcome") != "failed":
                continue
            result = by_ref.get(_key(op.get("result_ref")))
            detail = visible(result.get("text") if result else "")
            if not detail and op.get("exit_code") == 1:
                skipped += 1  # grep/diff style "no match" (investigate rule)
                continue
            failures.append((op, detail))
        if not failures:
            continue
        op, detail = failures[0]
        last = max(group, key=lambda o: o.get("order") or 0).get("outcome") or "unknown"
        ref = _ref(op.get("result_ref") or op.get("call_ref"))
        rows.append(_row("failed_exchange", op, f"{op.get('tool') or op.get('action')} failed: "
                         f"{detail[:160] or 'no output'}", len({o.get('operation_id') for o, _ in failures}),
                         {o.get("tool") for o, _ in failures}, ref, files.get(op.get("recording_id")),
                         last_outcome=last, trace=_ref(op.get("request_ref")) or ref,
                         meaning="recorded failures in one exchange; not a confirmed pitfall or cause"))
    return rows, skipped


def corrections(ops, files, by_ref):
    exchanges = {}
    for op in ops:
        request = by_ref.get(_key(op.get("request_ref")))
        if request is not None:
            exchanges[(op.get("recording_id"), _key(request["ref"]))] = (request, op)
    rows = []
    for (file, _), (request, op) in exchanges.items():
        recording = files.get(file)
        if recording is None:
            continue
        lane, after = request.get("lane"), request.get("order") or 0
        prior, following = None, None
        for event in recording["events"]:
            if event.get("lane") != lane or (event.get("order") or 0) <= after:
                continue
            if event["kind"] == "assistant_message" and prose(event):
                prior = event
            elif human(event):
                following = event
                break
        if following is None:
            continue
        text = prose(following)
        if noise(text) or not CORRECTION.search(text[:300]):
            continue
        rows.append(_row("correction_candidate", following, text[:240], 1, {op.get("tool")},
                         _ref(following["ref"]), recording, corrects=_ref(prior["ref"]) if prior else None,
                         after_request=_ref(request["ref"]), basis="phrasing",
                         meaning="next human message after an exchange on the target; phrasing match only"))
    return rows


def checkpoint_gaps(ops, files, checkpoints):
    rows, unresolved = [], 0
    by_recording = {}
    for op in ops:
        by_recording.setdefault(op.get("recording_id"), []).append(op)
    for checkpoint in checkpoints:
        mine, recording = by_recording.get(checkpoint.get("recording_id")), files.get(checkpoint.get("recording_id"))
        if not mine or recording is None:
            continue
        graph = message_graph(recording["events"])
        gap = trace._gap(recording, checkpoint, graph)
        if gap["status"] != "observed":
            unresolved += 1
            continue
        events = {e.get("event_id"): e for e in recording["events"]}
        publication = events.get(checkpoint.get("publication_event_id"))
        chain, _ = graph["chain"](trace._mid(publication))
        path = set(chain) | {trace._mid(publication)}
        after = [op for op in mine if gap["lower_order"] < (op.get("order") or 0) < gap["upper_order"]
                 and op.get("call_event_id") in events and trace._mid(events[op["call_event_id"]]) in path]
        if not after:
            continue
        rows.append(_row("checkpoint_gap", checkpoint, f"{len(after)} target operations after the checkpoint's "
                         "coverage boundary, before its publication", len(after), {o.get("tool") for o in after},
                         _ref(checkpoint.get("publication_ref")), recording,
                         boundary_status=checkpoint.get("boundary_status"), ops_after=len(after),
                         refs=[_ref(o.get("call_ref")) for o in after[:MAX_REFS]],
                         meaning="the checkpoint claim does not cover this target work"))
    return rows, unresolved


def repeated_reads(ops, files, observations=()):
    ids = {op.get("operation_id") for op in ops}
    states = {}
    for _, later, state in read_pairs([o for o in observations if o["operation_id"] in ids]):
        states.setdefault(later["recording_id"], []).append(state)
    sessions = {}
    for op in ops:
        if op.get("action") == "file_read":
            sessions.setdefault(op.get("recording_id"), []).append(op)
    rows = []
    for file, reads in sessions.items():
        if len(reads) < 2:
            continue
        reads.sort(key=lambda o: o.get("order") or 0)
        rows.append(_row("repeated_read", reads[-1], f"{len(reads)} reads of the target in one session",
                         len(reads), {o.get("tool") for o in reads}, _ref(reads[-1].get("call_ref")), files.get(file),
                         reads=len(reads), extra_reads=len(reads) - 1,
                         turns=len({o.get("turn") for o in reads}), first=_ref(reads[0].get("call_ref")),
                         unchanged_pairs=states.get(file, []).count("unchanged"),
                         changed_pairs=states.get(file, []).count("changed"),
                         meaning="unchanged_pairs: same extent, same content hash; not waste"))
    return rows


def order(by_kind):
    """Round-robin across kinds in KINDS order; newest first within a kind; ref tiebreak."""
    pools = [sorted(by_kind.get(kind, []), key=lambda r: r.get("ref") or "")
             for kind in KINDS]
    pools = [sorted(pool, key=lambda r: r.get("timestamp") or "", reverse=True) for pool in pools]
    out = []
    while any(pools):
        for pool in pools:
            if pool:
                out.append(pool.pop(0))
    return out


def views(by_kind, providers, sessions):
    recordings = providers.coverage.get("recordings", {})
    harnesses = {r.get("harness") for r in providers.recordings}
    out = {}
    for kind in KINDS:
        eligible = len(by_kind.get(kind, []))
        if eligible:
            state = "leads_found"
        elif not sessions:
            state = "not_searched"
        elif recordings.get("state") == "unavailable" or (
                kind == "checkpoint_gap" and not harnesses & CHECKPOINT_HARNESSES):
            state = "unavailable"
        else:
            state = "none_found_in_scanned_scope"
        out[kind] = {"state": state, "eligible": eligible}
    return out


def collect(providers, selected):
    """(rows in delivery order, by_kind, selection coverage)."""
    providers.load({"checkpoints", "file_observations"})
    files = {r["file"]: r for r in providers.recordings}
    by_ref = {_key(e["ref"]): e for r in providers.recordings for e in r["events"]}
    ops = _unique(sorted(selected, key=lambda r: (r.get("recording_id") or "", r.get("order") or 0)))
    failed, empty_exits = failed_exchanges(ops, files, by_ref)
    gaps, unresolved = checkpoint_gaps(ops, files, providers.tables.get("checkpoints", []))
    by_kind = {"failed_exchange": failed, "correction_candidate": corrections(ops, files, by_ref),
               "checkpoint_gap": gaps, "repeated_read": repeated_reads(ops, files, providers.tables.get("file_observations", []))}
    coverage = {"operations": len(ops), "empty_nonzero_exits_skipped": empty_exits,
                "checkpoints_unresolved": unresolved,
                "deferred": ["failure_after_fix"],
                "meaning": "signals are leads with refs; they do not establish waste, cause or fix"}
    return order(by_kind), by_kind, coverage
