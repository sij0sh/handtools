#!/usr/bin/env python3
"""Explore original coding-session JSONL; all derived data is invocation-local."""
import json
import sys

from . import actions
from .delivery import deliver
from .graph_output import check_fields, render_table
from .projection import FIELDS
from .operations import SessionParser, session_parser


# Commands that return result rows take the same paging, projection and repository flags as remember.py.
ROWS = ("overview", "projects", "search", "select", "duplicates", "recurrence", "records", "edges", "context", "cite")
SHARED = ("--format", "--fields", "--repo", "--limit")


Parser = SessionParser


COLUMNS = ("harness", "session", "kind", "role", "turn", "tool", "path", "command", "outcome", "exit_code", "text", "cite")


def table(action, fields):
    """Result rows of every harness group as one table, each tagged with its harness."""
    def render(result):
        flat = isinstance(result.get("results"), list) or not isinstance(result.get("harnesses"), list)
        groups = [result] if flat else result["harnesses"]
        rows = [{**({"harness": g.get("harness")} if g is not result else {}), **r}
                for g in groups for r in (g.get("results") or []) if isinstance(r, dict)]
        present = list(dict.fromkeys(k for r in rows for k in r))
        known = [k for k in COLUMNS if k in present]
        columns = fields or (known if len(known) >= 3 else [k for k in present if k != "ref" or "cite" not in present])
        delivery = result.get("delivery") or {}
        view = {"status": "fail" if result.get("check") == "fail" else result.get("status", "ok"), "operation": action, "results": rows, "report": "transient",
                "delivery": {"total": result.get("matched", len(rows))}, "next": result.get("next")}
        if delivery.get("complete") is False:
            view["results_truncated"] = "incomplete: " + (", ".join(delivery.get("incomplete_reasons", [])) or "unknown")
        # Hidden tool rows are a count to act on, not an absence of matches.
        hidden = sum(n for g in [result, *(result.get("harnesses") or [])] if isinstance(g, dict) for k, n in (g.get("excluded") or {}).items() if isinstance(n, int))
        if hidden:
            view["next"] = [f"{hidden} tool_call/tool_result rows hidden; add --include-tools", *(view["next"] or [])]
        return render_table(view, columns)
    return render


def project(result, fields):
    """--fields for commands whose rows are built before projection; a selected row keeps its marker."""
    for holder in [result, *(result.get("harnesses") or [])]:
        if isinstance(holder, dict) and isinstance(holder.get("results"), list):
            holder["results"] = [{k: r[k] for k in [*fields, "selected"] if k in r} if isinstance(r, dict) else r
                                 for r in holder["results"]]


def parser():
    return session_parser()


def main(argv=None):
    p = parser()
    # Bare invocation is the bounded overview over local recordings.
    args = p.parse_args((sys.argv[1:] if argv is None else argv) or ["overview"])
    for key, value in vars(args).items():
        if key in ("max_bytes", "max_record_bytes", "max_scan_bytes", "max_files", "max_candidates",
                   "max_events", "max_text_bytes", "preview_chars", "limit", "chars", "max_query_rows",
                   "query_seconds", "max_commits", "max_repo_files", "max_file_bytes", "min_sessions", "examples") and value is not None and value <= 0:
            p.error(f"--{key.replace('_', '-')} must be positive")
        if key == "tail" and args.action == "context" and value is not None and value <= 0:
            p.error("--tail must be positive")
        if key in ("offset", "start", "radius") and value is not None and value < 0:
            p.error(f"--{key} must be nonnegative")
    if args.action == "context" and args.tail is not None and args.offset is not None:
        p.error("--tail and --offset both choose the page; use one")
    for mapping in getattr(args, "root_map", []):
        old, sep, new = mapping.partition("=")
        if not sep or not old or not new:
            p.error("--root-map takes OLD=NEW")
    if args.action == "select" and args.limit is None and not args.sql:
        args.limit = 30
    if args.action == "context" and args.limit is None:
        args.limit = 8 if args.mode == "request" else 2 * args.radius + 1
    # remember.py history calls the same column date.
    fields = [{"date": "timestamp"}.get(f.strip(), f.strip()) for f in args.fields.split(",") if f.strip()] if args.fields else None
    if fields:
        args.fields = ",".join(fields)
    try:
        if args.action in ("search", "select", "duplicates"):
            # Event fields are projected before rows exist; --field aliases and --include columns join them.
            include = {part.strip() for part in getattr(args, "include", "").split(",")}
            check_fields(fields, None, [*FIELDS, "cite", *(d.partition("=")[0] for d in args.field),
                                        *(["git"] if "git" in include else []),
                                        *(["repo_path", "file"] if include & {"files", "symbols", "edits"} else [])])
        result = actions.run(args)
        if fields and args.action not in ("search", "select", "duplicates"):
            check_fields(fields, [r for h in [result, *(result.get("harnesses") or [])] if isinstance(h, dict)
                                  for r in (h.get("results") if isinstance(h.get("results"), list) else ())])
            project(result, fields)
        if args.action == "cite" and (args.offset or args.limit):
            rows = result["results"]
            result["results"] = rows[args.offset:args.offset + args.limit if args.limit else None]
            result.setdefault("omissions", {})["selection"] = len(rows) - len(result["results"])
        deliver("envelope", result, max_bytes=args.max_bytes, view=table(args.action, fields) if args.format == "table" else None)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        deliver("envelope", {"status": "error", "results": [{"error": str(error)[:500]}]}, max_bytes=max(1024, args.max_bytes))
        return 2
    # A citation check that found problems fails like a test, after its rows are printed.
    return 1 if result.get("check") == "fail" else 0
