"""Common v2 delivery contract. Evidence coverage and output paging are independent."""
import copy
from .graph_store import canonical
from .graph_output import check_fields, project_rows, render_table


def page(document, args, continuation=None):
    output = copy.deepcopy(document)
    rows = output.pop("results", [])
    fields = args.fields
    check_fields(fields, rows)
    total = len(rows)
    output.setdefault("status", "ok")
    output["schema_version"] = 2
    output.setdefault("scope", {}).setdefault("retention", "transient")
    # Results are never persisted here. The caller explicitly owns source retention.
    output["results"] = project_rows(rows[args.offset:args.offset + args.limit], fields)
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
            output["next"].insert(at, continuation(following, not output["results"]))
        if not output["delivery"]["complete"]:
            output["results_truncated"] = "More computed rows exist; follow next. Coverage is reported separately."
    finish()
    def rendered():
        return (render_table(output, fields).encode('utf-8') + b'\n') if args.format == "table" else canonical(output) + b'\n'
    while output["results"] and len(rendered()) > args.max_bytes:
        output["results"].pop()
        finish()
    if len(rendered()) > args.max_bytes:
        # Keep the operation, coverage state and executable continuation rather than an oversized envelope.
        output["coverage"] = {"summary_omitted": True, "state": output["status"]}
        output["scope"] = {"retention": output["scope"].get("retention", "transient")}
        for key in ("target", "steps", "gaps", "snapshots", "plan", "notes"):
            output.pop(key, None)
    if len(rendered()) > args.max_bytes:
        # Never silently discard a selected evidence payload or emit malformed/truncated JSON.
        raise ValueError("Result metadata/continuation exceeds --max-bytes; increase the output budget")
    return output, rendered()
