"""One bounded JSON envelope, coverage summary, and display clipping."""
import json

SCHEMA_VERSION = 1


def clip(text, chars=400, needle=None, tail=False, match_at=None):
    text = str(text)
    if tail:
        start = max(0, len(text) - chars)
    elif match_at is not None and match_at >= 0:
        start = max(0, match_at - chars // 3)
    elif needle and needle.casefold() in text.casefold():
        import re
        m = re.search(re.escape(needle), text, re.IGNORECASE)
        start = max(0, (m.start() if m else 0) - chars // 3)
    else:
        start = 0
    shown = text[start:start + chars]
    return {"text": shown, "text_chars": len(text), "text_start": start,
            "text_omitted": len(text) - len(shown)}


def omitted_rows(omissions):
    """Rows an envelope dropped by paging or budget: these make aggregates undercount."""
    if not isinstance(omissions, dict):
        return 0
    return sum(v for k, v in omissions.items() if isinstance(v, int) and not isinstance(v, bool)
               and k in ("selection", "results_budget", "rows_budget", "links_budget", "upstream_rows"))


def incomplete(value, scope):
    """Reasons an envelope reports it is known to be incomplete; [] means none reported, not complete."""
    reasons = []
    if scope.get("scan_complete") is False:
        reasons.append("scan_limit")
    if scope.get("discovery_complete") is False:
        reasons.append("discovery_limit")
    if scope.get("project_unknown"):
        reasons.append("project_unknown")
    repository = scope.get("repository") if isinstance(scope.get("repository"), dict) else {}
    if any(isinstance(part, dict) and part.get("complete") is False for part in repository.values()):
        reasons.append("repository")
    omissions = value.get("omissions") if isinstance(value.get("omissions"), dict) else {}
    if omissions.get("more_query_rows") is True:
        reasons.append("query_limit")
    if omissions.get("envelope_omitted"):
        reasons.append("output_budget")
    elif omitted_rows(omissions):
        # Truncated delivery is harmless to its reader but not to a consumer treating it as the whole set.
        reasons.append("rows_omitted")
    if value.get("status") == "partial":
        reasons.append("upstream_partial")
    return reasons


def coverage(value):
    """A small summary of an input envelope's coverage, not a copy of its scope."""
    scope = value.get("scope", {}) if isinstance(value.get("scope"), dict) else {}
    groups = value.get("harnesses") if isinstance(value.get("harnesses"), list) else []
    omissions = {k: v for k, v in value.get("omissions", {}).items() if v} if isinstance(value.get("omissions"), dict) else {}
    for g in groups:
        for k, v in (g.get("omissions", {}) if isinstance(g, dict) else {}).items():
            if v:
                omissions[f"{g.get('harness')}.{k}"] = v
    dropped = omitted_rows(value.get("omissions", {})) + sum(omitted_rows(g.get("omissions", {})) for g in groups)
    summary = {"scope": {k: scope[k] for k in ("files_scanned", "scan_complete", "discovery_complete",
                                              "project_filter", "harnesses", "text_complete",
                                              "text_truncated_events") if k in scope},
               "matched": value.get("matched"), "rows_omitted": dropped, "omissions": omissions}
    if value.get("status"):
        summary["status"] = value["status"]
    reasons = incomplete(value, scope)
    if reasons:
        # Known incompleteness only: an envelope that reports nothing stays unknown, not complete.
        summary["complete"] = False
        summary["incomplete_reasons"] = reasons
    if scope.get("text_complete") is False:
        summary["status"] = "partial"
        summary["text_truncated_events"] = scope.get("text_truncated_events", 0)
        summary["omissions"]["text_truncated_events"] = summary["text_truncated_events"]
    return summary


def load_rows(raw):
    """Parse an envelope, array or JSONL into rows; unknown envelopes are errors."""
    try:
        value = json.loads(raw)
    except ValueError:
        try:
            return [json.loads(line) for line in raw.splitlines() if line.strip()], {}
        except ValueError:
            raise ValueError("Input is not JSON, a JSON envelope, or JSONL object rows") from None
    if isinstance(value, dict):
        version = value.get("schema_version")
        if isinstance(version, int) and version > SCHEMA_VERSION:
            raise ValueError(f"Envelope schema_version {version} is newer than supported {SCHEMA_VERSION}")
        omissions = value.get("omissions") if isinstance(value.get("omissions"), dict) else {}
        if omissions.get("envelope_omitted"):
            # A coverage-only envelope lost its rows to the byte budget: unavailable, never zero rows.
            more = value.get("detail", {}).get("more_bytes") if isinstance(value.get("detail"), dict) else None
            raise ValueError("Input envelope omitted its rows to fit --max-bytes; rerun the producer with "
                             + (f"--max-bytes {more} or more" if more else "a larger --max-bytes"))
        if isinstance(value.get("harnesses"), list) and not isinstance(value.get("results"), list):
            # Grouped sessions.py envelopes (overview): one table of all harnesses' rows, each row tagged.
            rows = []
            for group in value["harnesses"]:
                if not isinstance(group, dict):
                    raise ValueError("harnesses[] entries must be objects")
                body = group.get("results", group.get("rows", group.get("links")))
                if not isinstance(body, list):
                    raise ValueError("Every harness group must hold results[], rows[], or links[]")
                rows.extend(body)
            return rows, coverage(value)
        body = value.get("results", value.get("rows", value.get("links")))
        if not isinstance(body, list):
            raise ValueError("Expected a JSON envelope with results[] or rows[] (or links[]), an array, or JSONL object rows")
        return body, coverage(value)
    if not isinstance(value, list):
        raise ValueError("Expected a JSON envelope, array, or JSONL object rows")
    return value, {}


# Sections shed before the rows a command was asked for: ref-bearing examples first, then
# ref-free aggregates, which cost little per entry.
