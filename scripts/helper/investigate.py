"""Investigate packet: four evidence views (pitfalls, invariants, task state, decisions) over loaded facts.

Providers own discovery, reads and budgets; this module only matches, classifies and orders.
Leads are bounded excerpts with refs, not accepted rules, lessons or task verdicts. Nothing is persisted.
"""
import hashlib
import json
import os
import re
from pathlib import Path

from . import cite, commit_links, operation_facts, reconciliation, recall
from .budget import check
from .graph_store import digest
from .options import ScanOptions
from .projection import human
from .reader import scan_file
from .records import new_scope
from .target_history import CORRECTION, relative

CATEGORIES = ("pitfall", "invariant", "task", "decision")
EXCERPT = 240
ACTIVE_SHARE = 4  # the active recording may use at most 1/4 of the scan byte allowance

# Human requirement language. Negations count only as imperatives, not as "I don't know".
REQUIRE = re.compile(r"\b(must|make sure|ensure|required|requirement|invariant|mandatory|should never|"
                     r"must not|is not allowed|never (?:change|break|remove|use|commit|push|delete|edit|touch))\b"
                     r"|(?:^|[.;:!?\n]\s*|\bplease\s+)(?:don'?t|do not|never|always)\b", re.I)
CHOICE = re.compile(r"\b(decided|decision|we(?:'ll| will) (?:go with|use)|go with|chose|choose|instead of|"
                    r"rather than|trade-?off|opted|in favou?r of|prefer(?:red)? (?:to|over))\b", re.I)
ACK = re.compile(r"^\W*(ok(ay)?|yes|yep|yeah|y|no|nope|thanks?( you)?|ty|go( ahead)?|continue|proceed|sure|do it|"
                 r"lgtm|great|nice|done|perfect|cool|good)\W*$", re.I)
WRAPPER = re.compile(r"<(system-reminder|command-[a-z-]+|local-command-[a-z-]+|user-prompt-submit-hook|"
                     r"task-notification|bash-[a-z-]+)\b[^>]*>.*?</\1>", re.S | re.I)
COPIED = re.compile(r'"schema_version"\s*:|"operation"\s*:\s*"(investigate|inspect|recall|trace)"')


def strip(text):
    """Visible human/assistant prose: harness wrappers removed, whitespace collapsed."""
    return " ".join(WRAPPER.sub(" ", str(text or "")).split())


def noise(text):
    """Suppression reason for text that cannot be an independent lead, else None."""
    if not text:
        return "wrapper_only"
    if COPIED.search(text):
        return "copied_packet"
    if ACK.match(text) or len(text) < 12:
        return "acknowledgement"
    if text.startswith("/") and len(text.split()) <= 3:
        return "command_echo"
    return None


def excerpt(text, match=None):
    if match is None or len(text) <= EXCERPT:
        return text[:EXCERPT]
    start = max(0, match.start() - EXCERPT // 3)
    return ("..." if start else "") + text[start:start + EXCERPT]


def lead_id(ref):
    raw = json.dumps([ref.get("file"), ref.get("offset"), ref.get("item", 0)], separators=(",", ":"))
    return "lead:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def locator(ref):
    """Cite token when the line is known (works with show/trace), else the JSON ref."""
    if ref.get("line") is not None and ref.get("sha256"):
        return cite.token(ref)
    return json.dumps({k: ref[k] for k in ("file", "offset", "item", "sha256") if k in ref}, separators=(",", ":"))


def _key(ref):
    return (ref.get("file"), ref.get("offset"), ref.get("item", 0)) if isinstance(ref, dict) else None


# Active recording: identity and frozen frontier, captured before archive work.

def _newline_before(stream, end):
    """Index of the last newline strictly before end, or -1."""
    step = 65536
    while end > 0:
        start = max(0, end - step)
        stream.seek(start)
        at = stream.read(end - start).rfind(b"\n")
        if at >= 0:
            return start + at
        end = start
    return -1


def _last_complete(path, size):
    """(byte end, sha256) of the last newline-terminated record within the first size bytes."""
    with open(path, "rb") as stream:
        last = _newline_before(stream, size)
        if last < 0:
            return 0, None
        begin = _newline_before(stream, last) + 1
        stream.seek(begin)
        return last + 1, hashlib.sha256(stream.read(last - begin)).hexdigest()


def frontier_arg(value):
    path, sep, rest = value.rpartition("@")
    end, sep2, sha = rest.partition(":")
    if not sep or not sep2 or not end.isdigit() or not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise ValueError("--frontier takes FILE@END:SHA256 from a returned continuation")
    return path, int(end), sha


def identify(args, providers):
    """The active recording: explicit --session ref, a pinned --frontier, or validated harness identity."""
    pinned = getattr(args, "frontier", None)
    if pinned:
        path, end, sha = frontier_arg(pinned)
        return {"state": "pinned", "file": path, "end": end, "sha256": sha,
                "event": getattr(args, "session_event", None)}
    if getattr(args, "session", None):
        ref = cite.ref_argument(args.session)
        if not isinstance(ref.get("file"), str) or not ref.get("sha256"):
            raise ValueError("--session takes a returned event JSON ref or cite token, not a bare session id")
        end, sha = _last_complete(ref["file"], ref["offset"] + _record_length(ref["file"], ref["offset"]))
        return {"state": "explicit", "file": ref["file"], "end": end, "sha256": sha,
                "event": [ref["offset"], ref.get("item", 0)]}
    from .recording_scan import env_sessions
    ids = env_sessions()
    session_file = os.environ.get("PI_SESSION_FILE")
    if not ids and not session_file:
        return {"state": "unknown", "reason": "no harness session identity; pass --session REF"}
    try:
        groups = providers.candidate_recordings()
    except ValueError as error:
        return {"state": "unknown", "reason": f"discovery unavailable: {error}"}
    found = sorted({name for _, files, _ in groups for name in files
                    if cite.recording_id(name) in ids
                    or (session_file and os.path.abspath(name) == os.path.abspath(session_file))})
    if not found:
        return {"state": "unknown", "reason": "harness identity matched no recording of this repository"}
    if len(found) > 1:
        return {"state": "ambiguous", "reason": "identity matches several recordings", "candidates": found[:5]}
    size = os.stat(found[0]).st_size
    end, sha = _last_complete(found[0], size)
    return {"state": "validated", "file": found[0], "end": end, "sha256": sha, "event": None}


def _record_length(path, offset):
    with open(path, "rb") as stream:
        stream.seek(offset)
        return len(stream.readline())


def read_active(identity, args):
    """Scan the frozen prefix (its tail, within the active allowance). Changed bytes invalidate it."""
    path, end = identity["file"], identity["end"]
    try:
        before = os.stat(path)
        got_end, sha = _last_complete(path, end)
    except OSError as error:
        return None, {**identity, "state": "unavailable", "reason": str(error)}
    if got_end != end or sha != identity["sha256"]:
        return None, {**identity, "state": "changed", "reason": "recording prefix changed since the frontier was captured"}
    cap = max(1, args.max_scan_bytes // ACTIVE_SHARE)
    start = max(0, end - cap)
    scope = new_scope()
    options = ScanOptions(harness="auto", max_scan_bytes=cap + 2 * 1024 * 1024, max_events=args.max_events,
                          max_text_bytes=8 * 1024 * 1024)
    recording = scan_file(path, options, scope, [(start, end)])
    after = os.stat(path)
    if (after.st_ino, after.st_dev) != (before.st_ino, before.st_dev) or after.st_size < end:
        return None, {**identity, "state": "changed", "reason": "recording replaced or truncated during capture"}
    events = recording["events"]
    boundary = "explicit_ref" if identity.get("event") else "unknown"
    if identity.get("event"):
        wanted = tuple(identity["event"])
        target = next((e for e in events if (e["ref"]["offset"], e["ref"].get("item", 0)) == wanted), None)
        if target is None:
            return None, {**identity, "state": "unavailable", "reason": "session ref outside the active allowance"}
        lane = target.get("lane")
        events = [e for e in events if e["order"] <= target["order"] and (lane is None or e.get("lane") in (lane, None))]
    else:
        # Drop the invoking tool call and everything after it, when recognizable.
        call = next((e for e in reversed(events) if e["kind"] == "tool_call"
                     and "investigate" in str(e.get("command") or e.get("text") or "")
                     and "remember" in str(e.get("command") or e.get("text") or "")), None)
        if call is not None:
            events = [e for e in events if e["order"] < call["order"]]
            boundary = "invoking_call_excluded"
    recording["events"] = events
    lanes = {}
    for e in events:
        if human(e) and noise(strip(e.get("text"))) is None:
            lanes[e.get("lane")] = e
    state = {**identity, "boundary": boundary, "prefix": "tail" if start else "whole",
             "bytes_read": scope["bytes_scanned"], "state": "active"}
    if not identity.get("event") and len(lanes) > 1:
        tips = sorted(lanes.values(), key=lambda e: e["order"])[-5:]
        state.update(state="branch_ambiguous", candidates=[locator(e["ref"]) for e in tips])
    return recording, state


# Candidate extraction over loaded recordings.

class Packet:
    def __init__(self, providers, goal, paths, errors, active=None):
        self.providers = providers
        self.goal, self.paths, self.errors = goal, paths, [e.lower() for e in errors]
        self.words = recall.terms(goal) if goal else []
        self.active = active
        self.suppressed = {}
        self.leads = {}

    def suppress(self, reason):
        self.suppressed[reason] = self.suppressed.get(reason, 0) + 1

    def relevance(self, text, op_paths=()):
        low = text.lower()
        bases = []
        if any(p in text for p in self.paths):
            bases.append("path")
        elif any(p in op_paths for p in self.paths):
            bases.append("path_activity")
        if any(e in low for e in self.errors):
            bases.append("error")
        hits = sum(w in low for w in self.words)
        if hits:
            bases.append("goal")
        return bases, hits

    def add(self, event, category, kind, evidence, text, match=None, recording=None, op_paths=(),
            relations=None, extra=None, active=False):
        ref = event["ref"]
        key = _key(ref)
        bases, hits = self.relevance(text, op_paths)
        applicability = self.applicability(recording)
        if not bases:
            if applicability != "repository":
                self.suppress("scope_unknown_unmatched")
                return
            bases = ["repo_context"]
        lead = self.leads.get(key)
        if lead is None:
            lead = self.leads[key] = {
                "section": "lead", "id": lead_id(ref), "categories": [], "kinds": [], "excerpt": excerpt(text, match),
                "evidence": evidence, "applicability": applicability, "relevance": bases, "goal_hits": hits,
                "session": event.get("session") or (recording or {}).get("session"),
                "lane": event.get("lane"), "timestamp": event.get("timestamp"), "ref": locator(ref),
                "relations": {}}
            if active:
                lead["active_context"] = True
        if category not in lead["categories"]:
            lead["categories"].append(category)
            lead["kinds"].append(kind)
        lead["relations"].update(relations or {})
        lead.update(extra or {})

    def applicability(self, recording):
        root = (recording or {}).get("root")
        if not root:
            return "scope_unknown"
        from .discovery import normalized_root
        if normalized_root(root) == normalized_root(self.providers.store.root):
            return "repository"
        return "historical_root"

    def scan(self, recordings, operations, witnesses, checkpoints, active=False, deadline=None):
        by_ref = {}
        for recording in recordings:
            for event in recording["events"]:
                by_ref[_key(event["ref"])] = event
        turn_paths = {}
        for op in operations:
            if op.get("path"):
                turn_paths.setdefault((op.get("recording_id"), op.get("turn")), set()).add(op.get("repo_path") or op["path"])
        files = {r["file"]: r for r in recordings}
        for recording in recordings:
            humans = [e for e in recording["events"] if human(e)]
            assistant_last = {}
            for index, event in enumerate(recording["events"]):
                if index % 500 == 0:
                    check()
                kind = event["kind"]
                if kind not in ("user_message", "assistant_message"):
                    continue
                text = strip(event.get("text"))
                if kind == "user_message":
                    if not human(event):
                        continue
                    reason = noise(text)
                    if reason:
                        self.suppress(reason)
                        continue
                    if active and self.active is not None:
                        continue  # active humans feed the task view only
                    paths = turn_paths.get((recording["file"], event.get("turn")), ())
                    prior = assistant_last.get(event.get("lane"))
                    if CORRECTION.search(text[:300]) and prior is not None:
                        self.add(event, "pitfall", "correction", "human", text, recording=recording, op_paths=paths,
                                 relations={"corrects": locator(prior["ref"])})
                    found = REQUIRE.search(text)
                    if found:
                        self.add(event, "invariant", "human_requirement", "human", text, found, recording, paths)
                    found = CHOICE.search(text)
                    if found:
                        self.add(event, "decision", "human_choice", "human", text, found, recording, paths)
                else:
                    if not text:
                        continue
                    assistant_last[event.get("lane")] = event
                    found = CHOICE.search(text)
                    if found and not active:
                        later = next((h for h in humans if h.get("lane") == event.get("lane")
                                      and h["order"] > event["order"]), None)
                        relations = {}
                        if later is not None and CORRECTION.search(strip(later.get("text"))[:300]):
                            relations["later_rejection"] = locator(later["ref"])
                        self.add(event, "decision", "assistant_proposal", "assistant_claim", text, found, recording,
                                 turn_paths.get((recording["file"], event.get("turn")), ()), relations)
        seen_ops = set()
        for op in operations:
            if op.get("outcome") != "failed" or op.get("operation_id") in seen_ops:
                continue
            seen_ops.add(op.get("operation_id"))
            event = by_ref.get(_key(op.get("result_ref"))) or by_ref.get(_key(op.get("call_ref")))
            if event is None:
                continue
            result = by_ref.get(_key(op.get("result_ref")))
            detail = strip(result.get("text") if result else "")
            if not detail and op.get("exit_code") == 1:
                self.suppress("empty_nonzero_exit")  # grep/diff style "no match", not a failure lead
                continue
            what = " ".join(str(op.get("command") or op.get("path") or op.get("action") or "").split())
            # Failure detail first: it is what the next attempt must avoid.
            text = f"{op.get('tool') or op.get('action')} failed: {detail[:160] or 'no output'} | {what[:120]}"
            self.add(event, "pitfall", "failed_operation", "tool_observation", text,
                     recording=files.get(op.get("recording_id")), op_paths={op.get("path")}, active=active,
                     extra={"path": op.get("path")} if op.get("path") else None)
        for checkpoint in checkpoints:
            event = by_ref.get(_key(checkpoint.get("publication_ref")))
            if event is None:
                continue
            claims = reconciliation.claims_for(checkpoint)
            text = "; ".join(c.get("excerpt") or str(c.get("value")) for c in claims[:3]) or strip(event.get("text"))
            self.add(event, "task", "checkpoint_claim", "checkpoint_claim", text,
                     recording=files.get(checkpoint.get("recording_id")), active=active,
                     extra={"boundary_status": checkpoint.get("boundary_status")})
        if not active:
            for recording in recordings:
                self.unfinished(recording, operations, witnesses)

    def unfinished(self, recording, operations, witnesses):
        """Last substantive request per lane whose own recorded work was edited but not verified or committed."""
        last = {}
        for event in recording["events"]:
            if human(event) and noise(strip(event.get("text"))) is None:
                last[event.get("lane")] = event
        for request in last.values():
            dims = self.dimensions(recording, request, operations, witnesses)
            edited = dims["edited"]["state"] == "observed"
            open_ = dims["verified"]["state"] == "unknown" and dims["committed"]["state"] == "unknown"
            key = _key(request["ref"])
            own = [o for o in operations if o.get("recording_id") == recording["file"]
                   and _key(o.get("request_ref")) == key]
            ended_failed = bool(own) and max(own, key=lambda o: o.get("order") or 0).get("outcome") == "failed"
            if edited and open_ or ended_failed:
                self.add(request, "task", "unverified_request", "human", strip(request.get("text")),
                         recording=recording, extra={"dimensions": {k: v["state"] for k, v in dims.items()}})

    @staticmethod
    def dimensions(recording, request, operations, witnesses, checkpoints=()):
        key = _key(request["ref"])
        ops = [o for o in operations if o.get("recording_id") == recording["file"] and _key(o.get("request_ref")) == key]
        links = [w for w in witnesses if w.get("recording_id") == recording["file"] and _key(w.get("request_ref")) == key]
        observations = reconciliation.observations(request, ops, links, checkpoints)
        claims = [c for cp in checkpoints for c in reconciliation.claims_for(cp)]
        return reconciliation.summarize(observations, claims)

    def active_task(self, recording, state, cache):
        """The active branch's latest request with per-dimension observed/claimed/unknown states."""
        ops, _ = operation_facts.operations([recording], cache)
        checkpoints, _ = operation_facts.checkpoints([recording], cache)
        resolver = self.providers.resolver
        witnesses = commit_links.witnesses([recording], resolver, cache, resolver.repo(self.providers.store.root))
        if state["state"] == "active":
            requests = [e for e in recording["events"] if human(e) and noise(strip(e.get("text"))) is None]
            if requests:
                request = requests[-1]
                lane = request.get("lane")
                cps = [c for c in checkpoints if c.get("lane") == lane]
                dims = self.dimensions(recording, request, ops, witnesses, cps)
                self.add(request, "task", "active_request", "human", strip(request.get("text")), recording=recording,
                         active=True, extra={"dimensions": {k: v["state"] for k, v in dims.items()}})
        self.scan([recording], [o for o in ops if o.get("outcome") == "failed"], witnesses, checkpoints, active=True)


def rank_key(lead):
    # The active request leads the task view; other active-session evidence is already in the agent's
    # context, so archive leads rank ahead of it.
    current = "active_request" in lead["kinds"]
    if current:
        return (-1,)
    applic = {"repository": 0, "historical_root": 1}.get(lead["applicability"], 2) + (3 if lead.get("active_context") else 0)
    exact = any(b in ("path", "error") for b in lead["relevance"])
    loose = "path_activity" in lead["relevance"]
    context = lead["relevance"] == ["repo_context"]
    direct = 0 if lead["evidence"] in ("human", "tool_observation") else 1
    flagged = bool(lead["relations"].get("corrects") or lead["relations"].get("later_rejection")
                   or "unverified_request" in lead["kinds"])
    return (applic, not exact, not loose, -lead["goal_hits"], context, direct, not flagged)


def order(leads, prior):
    """Round robin: one lead per category (pitfall, invariant, task, decision), a repo-context slot,
    the strongest prior-work row, then further rounds preferring unseen recordings at equal rank."""
    pools = {}
    ranked = sorted(leads, key=lambda r: r["ref"])
    ranked.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    ranked.sort(key=rank_key)
    for lead in ranked:
        pools.setdefault(lead["categories"][0], []).append(lead)
    out, taken, prior = [], set(), list(prior)

    def pick(pool, seen):
        live = [lead for lead in pool if lead["id"] not in taken]
        if not live:
            return None
        best = rank_key(live[0])
        for lead in live:
            if rank_key(lead) != best:
                break
            if lead.get("session") not in seen:
                return lead
        return live[0]
    first = True
    while any(lead["id"] not in taken for pool in pools.values() for lead in pool) or prior:
        seen = set()
        round_rows = []
        for category in CATEGORIES:
            lead = pick(pools.get(category, []), seen)
            if lead:
                taken.add(lead["id"])
                seen.add(lead.get("session"))
                round_rows.append(lead)
        if first and not any(r["relevance"] == ["repo_context"] for r in round_rows):
            extra = next((lead for lead in ranked if lead["id"] not in taken and lead["relevance"] == ["repo_context"]), None)
            if extra:
                taken.add(extra["id"])
                round_rows.append(extra)
        out += round_rows
        if prior:
            out.append(prior.pop(0))
        first = False
    return out


def prior_work(goal, providers):
    """Ranked commits with every recorded request associated by witness ancestry (not newest timestamp)."""
    tables = providers.tables
    try:
        _, rows = recall.rank(goal, tables.get("commits", []), tables.get("changes", []), [], [], providers.store.root)
    except ValueError:
        return []
    events = {_key(e.get("ref")): e for e in tables.get("events", []) if isinstance(e.get("ref"), dict)}
    asks = {}
    for link in tables.get("commit_links", []):
        request = events.get(_key(link.get("request_ref")))
        if link.get("sha") and request is not None and human(request):
            item = {"request": strip(request.get("text"))[:200], "ref": locator(request["ref"]),
                    "basis": link.get("basis"), "confidence": link.get("confidence")}
            bucket = asks.setdefault(link["sha"], [])
            if item["ref"] not in {b["ref"] for b in bucket}:
                bucket.append(item)
    return [{"section": "prior_work", "id": "commit:" + row["sha"], "sha": row["sha"], "subject": row["subject"],
             "date": row["date"], "score": row["score"], "paths": row["paths"], "paths_more": row["paths_more"],
             "requests": asks.get(row["sha"], []), "ref": row["sha"]} for row in rows]


def views(leads, providers, sessions):
    out = {}
    recordings = providers.coverage.get("recordings", {})
    for category in CATEGORIES:
        eligible = sum(category in lead["categories"] for lead in leads)
        if eligible:
            state = "leads_found"
        elif not sessions:
            state = "not_searched"
        elif recordings.get("state") == "unavailable":
            state = "unavailable"
        else:
            state = "none_found_in_scanned_scope"
        out[category] = {"state": state, "eligible": eligible}
    return out


def plan():
    return [{"step": "frontier", "detail": "freeze active recording identity and last complete record"},
            {"step": "discover", "detail": "one project-matched discovery; investigate totals across harnesses"},
            {"step": "schedule", "detail": "half newest-first match lane, half age-diverse context lane"},
            {"step": "git", "detail": "commits/changes for prior work; HEAD and worktree status for scope"},
            {"step": "classify", "detail": "pitfall, invariant, task, decision recognizers; noise suppressed"},
            {"step": "order", "detail": "category rounds, repo-context slot, prior work after round one"}]


def git_scope(providers):
    resolver = providers.resolver
    root = resolver.repo(providers.store.root)
    if not root:
        return {"state": "unavailable"}
    head = (resolver.run(root, "rev-parse", "HEAD") or "").strip() or None
    status = resolver.run(root, "status", "--porcelain", "--untracked-files=no") or ""
    return {"head": head, "dirty_paths": len(status.splitlines()),
            "status_digest": digest(status)[:16], "basis": "observed at invocation; historical leads do not certify it"}


def validate_paths(paths):
    return [relative(p) for p in paths]


def summary_text(views_):
    return {k: v["state"] for k, v in views_.items()}


def collect(args, providers, deadline, goal, paths, errors, sessions=True):
    """Shared lifecycle: freeze the active frontier, one scheduled scan, classify. Returns (packet, active state)."""
    packet = Packet(providers, goal, paths, errors)
    if not sessions:
        return packet, {"state": "not_searched"}
    identity = identify(args, providers)
    state, active = identity, None
    if identity.get("file"):
        active, state = read_active(identity, args)
        providers.exclude_files = (identity["file"],)
        if active is not None:
            # The active read is charged to the same total allowance.
            args.max_scan_bytes = max(1, args.max_scan_bytes - state["bytes_read"])
    packet.active = active
    providers.scheduled = True
    providers.load({"recordings", "operations", "checkpoints", "commit_links"})
    deadline.check()
    tables = providers.tables
    packet.scan(providers.recordings, tables.get("operations", []), tables.get("commit_links", []),
                tables.get("checkpoints", []))
    if active is not None:
        deadline.check()
        packet.active_task(active, state, providers.cache)
    return packet, state


def frontier_token(state, active):
    if active is None or not state.get("end"):
        return None
    return f"{state['file']}@{state['end']}:{state['sha256']}"
