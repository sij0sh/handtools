"""One delivery component: shared paging and byte fitting behind explicit, retention-aware adapters.

Adapter    Retention  Contract
retained   source     v1 graph report: saved once, paged by report ref without recomputation
common     transient  v2 runtime result: coverage separate from paging, typed continuations

Evidence coverage and output paging are independent in every adapter: paging and byte
budgets truncate delivery, only coverage gaps make a result partial.
"""
import copy
import sys
from .graph_store import canonical
from .graph_output import check_fields, compact_row, project_rows, render_table

# Operations whose results may carry transcript-derived text; they never reach the report store.
TRANSIENT_OPERATIONS = {"inspect"}
# Room for the continuation token itself when sizing a budget for an oversized row.
NEXT_MARGIN = 2048


def select(rows, args, fields, transform=None):
    """Validate --fields, take the requested page, then project it."""
    check_fields(fields, rows)
    page = rows[args.offset:args.offset + args.limit]
    return project_rows([transform(r) for r in page] if transform else page, fields)


def fit(output, finish, size, max_bytes):
    """Drop rows from the end until the rendering fits, so ranking and --offset paging hold. True if it fits."""
    while output["results"] and size() > max_bytes:
        output["results"].pop()
        finish()
    return size() <= max_bytes


def json_size(output):
    return len(canonical(output)) + 1


def render(output, args, fields):
    if getattr(args, "format", None) == "table":
        return render_table(output, fields).encode("utf-8") + b"\n"
    return canonical(output) + b"\n"


def retained(store, document, args):
    """Source-only graph report: saved whole, delivered by page."""
    if document.get("operation") in TRANSIENT_OPERATIONS or document.get("scope", {}).get("retention") == "transient":
        raise ValueError(f"{document.get('operation')} results are transient and cannot be retained")
    # Primer evidence is transient and must not be retained with the report.
    primer = document.pop("primer", None)
    limited = document.pop("incomplete", None)
    if limited is None:
        from .graph_cli import incomplete
        limited = incomplete(document)
    report = store.save("report", document)
    all_rows = document["results"]
    compact = not args.verbose and not args.fields and document["operation"] != "query"
    rows = select(all_rows, args, args.fields, compact_row if compact else None)
    output = {"schema_version": 1, "status": "partial" if limited else "ok", "report": report,
              "snapshots": document.get("snapshots", []), "operation": document["operation"],
              "scope": document["scope"], "coverage": document["coverage"], "results": rows,
              "gaps": {"count": len(document["gaps"]), "incomplete": len(limited), "ref": report+"/gaps"},
              "delivery": {"offset": args.offset, "total": len(all_rows)}}
    if document["scope"].get("assessment") == "unknown":
        output["status"] = "unknown"
    if primer is not None:
        if args.format == "table" and isinstance(primer, dict):
            from .primer import render as render_primer
            primer = render_primer(primer, args.primer_bytes)
        output["primer"] = primer
    query_limited = any(g.get("area") == "query" and g.get("reason") == "row_limit" for g in document["gaps"])

    def finish():
        # A page is complete when it reaches the last row; earlier pages were delivered by earlier calls.
        following = args.offset + len(output["results"])
        output["delivery"].update(returned=len(output["results"]), complete=following >= len(all_rows))
        missing = max(0, len(all_rows) - following)
        output["omissions"] = {"selection": missing}
        output.pop("results_truncated", None)
        if missing or query_limited:
            output["results_truncated"] = (f"{len(output['results'])} of {len(all_rows)} retained rows shown; "
                f"--offset {following} or raise --limit N / --max-bytes N"
                + ("; query retention capped: rerun query with a larger --limit" if query_limited else ""))
        if missing and not output["results"] and args.offset < len(all_rows):
            output["omissions"]["envelope_omitted"] = True
        output["next"] = ({"action": "show", "ref": report, "repo": store.root,
                           "cache": str(store.path.parent), "offset": following}
                          if following < len(all_rows) else None)
        if output["next"] and not output["results"]:
            output["next"]["hint"] = "Increase --max-bytes; this row does not fit."
    finish()
    # Keep complete evidence on disk; trim delivery without recomputing analysis.
    if json_size(output) > args.max_bytes:
        output["scope"] = {"ref": report+"/scope", "freshness": document["scope"].get("freshness")}
        output["coverage"] = {"ref": report+"/coverage"}
    # A requested primer that would crowd out every row says so instead of vanishing.
    if isinstance(output.get("primer"), (dict, list)) and json_size({**output, "results": output["results"][:1]}) > args.max_bytes:
        output["primer"] = f"omitted: byte cap; raise --max-bytes above {args.max_bytes}"
    if not fit(output, finish, lambda: json_size(output), args.max_bytes):
        output = {"schema_version": 1, "status": "partial", "report": report, "results": [],
                  "results_truncated": "Metadata exceeds budget; increase --max-bytes",
                  "omissions": {"envelope_omitted": True},
                  "delivery": {"complete": False, "reason": "metadata_budget", "total": len(all_rows)},
                  "next": {"action": "show", "ref": report, "hint": "Increase --max-bytes"}}
    return render(output, args, args.fields)




def page(document, args, continuation=None):
    """Common v2 result; returns (output, bytes). The caller owns source retention: nothing is persisted here."""
    output = copy.deepcopy(document)
    rows = output.pop("results", [])
    fields = args.fields
    total = len(rows)
    output.setdefault("status", "ok")
    output["schema_version"] = 2
    output.setdefault("scope", {}).setdefault("retention", "transient")
    selected = select(rows, args, fields)
    output["results"] = list(selected)  # fit() pops from this list; selected stays whole.
    more = bool(output.pop("more_rows", False))
    original_next = output.get("next") or []
    if not isinstance(original_next, list): original_next = [original_next]

    def finish():
        following = args.offset + len(output["results"])
        output["delivery"] = {"offset": args.offset, "returned": len(output["results"]),
                              "complete": following >= total and not more,
                              "total": None if more else total}
        output["next"] = list(original_next)
        if not output["delivery"]["complete"] and continuation:
            # Blocking coverage recovery ranks before paging; paging before optional expansion.
            at = sum(1 for item in original_next if isinstance(item, dict) and item.get("effect") == "coverage")
            # A row too large for the budget: ask for enough bytes to deliver it in one step.
            need = (len(render({**output, "results": selected[:1]}, args, fields)) + NEXT_MARGIN
                    if not output["results"] and selected else None)
            output["next"].insert(at, continuation(following, not output["results"], need))
        if not output["delivery"]["complete"]:
            output["results_truncated"] = "More computed rows exist; follow next. Coverage is reported separately."
    finish()
    size = lambda: len(render(output, args, fields))
    if not fit(output, finish, size, args.max_bytes):
        # Keep the operation, coverage state and executable continuation rather than an oversized envelope.
        output["coverage"] = {"summary_omitted": True, "state": output["status"]}
        output["scope"] = {"retention": output["scope"].get("retention", "transient")}
        for key in ("target", "steps", "gaps", "snapshots", "plan", "notes"):
            output.pop(key, None)
    if size() > args.max_bytes:
        # Never silently discard a selected evidence payload or emit malformed/truncated JSON.
        raise ValueError("Result metadata/continuation exceeds --max-bytes; increase the output budget")
    return output, render(output, args, fields)


def write(raw):
    sys.stdout.flush()
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def deliver(kind, document, args=None, store=None, continuation=None):
    """Render and write one result through its adapter."""
    if kind == "retained":
        raw = retained(store, document, args)
    elif kind == "common":
        raw = page(document, args, continuation)[1]
    else:
        raise ValueError(f"Unknown delivery adapter {kind!r}")
    write(raw)
