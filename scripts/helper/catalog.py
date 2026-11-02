"""Declarative public table catalog. Dependencies drive execution and schema help."""
from dataclasses import dataclass
from . import commit_links, edit_hunks, git_file_history, repo_files
from .graph_queries import TABLES
from .projection import FIELDS


@dataclass(frozen=True)
class Table:
    columns: dict
    provider: str
    grain: str
    keys: tuple = ()
    retention: str = "source"


EVENT_COLUMNS = {name: "TEXT" for name in (*FIELDS, "cite", "repo_path")}
EVENT_COLUMNS.update({name: "INTEGER" for name in ("exit_code", "text_chars", "text_start", "text_omitted", "is_shell")})
SESSION_COLUMNS = {name: "TEXT" for name in (
    "session", "parent_session", "independent_session", "harness", "harness_version", "recording_id", "root",
    "started_at", "ended_at", "first_request", "first_request_cite")}
SESSION_COLUMNS.update({name: "INTEGER" for name in ("events", "user_messages", "tool_calls", "failed_calls",
                                                       "repo_paths")})
CATALOG = {
    "nodes": Table(TABLES["nodes"], "graph", "one source node", ("id",)),
    "edges": Table(TABLES["edges"], "graph", "one typed relationship", ("id",)),
    "gaps": Table(TABLES["gaps"], "graph", "one unresolved occurrence"),
    "files": Table({**TABLES["files"], "content": "TEXT", "lines": "INTEGER", "language": "TEXT"},
                   "graph", "one captured source path", ("path",)),
    "code_items": Table({**repo_files.ITEM_COLUMNS, "id": "TEXT", "ref": "TEXT"}, "graph",
                        "one captured symbol (legacy imports remain available through sessions.py)", ("id",)),
    "events": Table(EVENT_COLUMNS, "recordings", "one recorded event", ("recording_id", "event_id"), "transient"),
    "sessions": Table(SESSION_COLUMNS, "recordings", "one recorded session file; join events USING(recording_id)",
                      ("recording_id",), "transient"),
    "commits": Table({**git_file_history.COMMIT_COLUMNS, "ref": "TEXT"}, "git", git_file_history.COMMIT_GRAIN, ("repo_id", "sha")),
    "changes": Table(git_file_history.CHANGE_COLUMNS, "git", git_file_history.CHANGE_GRAIN, ("repo_id", "sha", "path")),
    "commit_links": Table(commit_links.COLUMNS, "links", commit_links.GRAIN, (), "transient"),
    "edit_hunks": Table(edit_hunks.HUNK_COLUMNS, "edits", edit_hunks.HUNK_GRAIN, (), "transient"),
    "edit_symbols": Table(edit_hunks.SYMBOL_COLUMNS, "edits", edit_hunks.SYMBOL_GRAIN, (), "transient"),
    "file_status": Table(repo_files.FILE_COLUMNS, "status", "one live Git worktree path", ("path",)),
}
# Compatibility event alias. No positional t0/rows aliases for unrelated built-ins.
CATALOG["rows"] = CATALOG["events"]
DEPENDENCIES = {"graph": (), "recordings": (), "git": (), "links": ("recordings",),
                "edits": ("recordings", "graph"), "status": ()}


def providers_for(names):
    ordered = []
    def visit(name):
        for required in DEPENDENCIES[name]:
            visit(required)
        if name not in ordered:
            ordered.append(name)
    for name in sorted(names):
        if name in CATALOG:
            visit(CATALOG[name].provider)
    return ordered


def describe(name=None):
    if name and name not in CATALOG:
        raise ValueError(f"Unknown table {name!r}; tables: {', '.join(CATALOG)}")
    return [{"name": key, "columns": item.columns, "grain": item.grain, "keys": list(item.keys),
             "provider": item.provider, "dependencies": list(DEPENDENCIES[item.provider]), "retention": item.retention}
            for key, item in CATALOG.items() if name is None or key == name]
