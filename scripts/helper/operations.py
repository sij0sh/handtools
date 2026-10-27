"""Declarative operation registry: one definition per CLI operation drives parsers, help, routing and delivery.

Each argument is defined once with the operations it applies to. Parsers for remember.py
(legacy graph and common runtime views), sessions.py and rows.py are generated from it.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

SESSIONS = Path(__file__).resolve().parents[1] / "sessions.py"


def positive(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def nonnegative(value):
    value = int(value)
    if value < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return value


@dataclass(frozen=True)
class Operation:
    name: str
    family: str          # graph | session | rows
    help: str
    route: str           # runtime | graph | session | rows | describe
    delivery: str        # common | retained | history | envelope
    tier: str = "advanced"
    summary: str = ""    # common-interface description, when it differs from help


OPERATIONS = {op.name: op for op in (
    Operation("map", "graph", "List source files, directories or symbols and graph coverage (default).",
              "graph", "retained", "common", "Orient in current source."),
    Operation("analyze", "graph", "Rank structural candidates: fanin, orphans, cycles, untested, largest.", "graph", "retained"),
    Operation("snapshot", "graph", "Capture source and retain an immutable graph; return its ID.", "graph", "retained"),
    Operation("find", "graph", "Locate names, paths and literal source occurrences; matches are candidates.",
              "graph", "retained", "common", "Locate a concrete anchor."),
    Operation("neighbors", "graph", "Traverse typed incoming/outgoing relationships with witness paths.", "graph", "retained"),
    Operation("paths", "graph", "Find a shortest supported path between targets, within traversal bounds.", "graph", "retained"),
    Operation("impact", "graph", "Assess planned targets or the full delta between two retained snapshots.", "graph", "retained"),
    Operation("history", "graph", "Retrieve bounded Git and recording leads for a file or symbol; output is transient.",
              "graph", "history"),
    Operation("show", "graph", "Expand retained source, nodes, edges or report pages without refreshing them.",
              "runtime", "common", "common", "Expand evidence or execute a returned continuation."),
    Operation("query", "graph", "Run one read-only SQLite SELECT/CTE over nodes, edges, files and gaps.",
              "runtime", "common", "common", "Query built-in and custom tables; dependencies load automatically."),
    Operation("status", "graph", "Inspect graph coverage, producer capabilities and current source freshness.", "graph", "retained"),
    Operation("describe", "graph", "Describe commands, predicates and SQL tables without scanning source.", "describe", "common"),
    Operation("inspect", "runtime", "Collect source, consumers, dependencies and relevant history.",
              "runtime", "common", "common", "Collect source, consumers, dependencies and relevant history."),
    *(Operation(name, "session", "Advanced recording operation", "session", "envelope")
      for name in ("overview", "projects", "search", "select", "duplicates", "recurrence", "records", "edges",
                   "context", "payload", "raw", "cite", "describe-sessions")),
    Operation("rows", "rows", "Query disposable JSON rows through an in-memory DuckDB engine.", "rows", "envelope"),
)}
# sessions.py names its schema command describe; the registry keys it apart from remember.py describe.
SESSION_NAMES = {"describe-sessions": "describe"}


def names(family):
    return tuple(SESSION_NAMES.get(n, n) for n, op in OPERATIONS.items() if op.family == family)


GRAPH = names("graph")
SESSION_COMMANDS = tuple(n for n in names("session") if n != "describe")
COMMON = {n: op.summary for n, op in OPERATIONS.items() if op.tier == "common"}
DELIVERY = {n: op.delivery for n, op in OPERATIONS.items() if op.family in ("graph", "runtime")}


class Per:
    """An option value that differs by operation."""

    def __init__(self, values, default=None):
        self.values, self.default = values, default

    def get(self, name):
        return self.values.get(name, self.default)


@dataclass(frozen=True)
class Arg:
    flags: tuple
    options: dict
    ops: frozenset | None   # None: every operation of the family
    scope: str = "both"     # both | legacy | common (graph family: legacy remember.py vs common runtime)

    def applies(self, name, view):
        return (self.ops is None or name in self.ops) and self.scope in ("both", view)

    def resolved(self, name):
        return {k: v.get(name) if isinstance(v, Per) else v for k, v in self.options.items()}


def arg(*flags, ops=None, scope="both", **options):
    return Arg(flags, options, frozenset((ops,) if isinstance(ops, str) else ops) if ops is not None else None, scope)


def defaults(ops, **values):
    """A set_defaults entry for the listed operations."""
    return arg(ops=ops, _defaults=values)


def every(*excluded, family=GRAPH + ("inspect",)):
    return tuple(n for n in family if n not in excluded)


# Shared remember.py options; each subcommand repeats them so they work before or after the verb.
GRAPH_SHARED = (
    arg("--repo", help="Source root, including an ordinary directory; default current directory"),
    arg("--cache", help="Cache parent outside source tree; default $XDG_CACHE_HOME/remember"),
    arg("--snapshot", help="Use a retained snapshot instead of capturing current source"),
    arg("--exclude", action="append", help="Exclude relative-path/component glob; repeatable"),
    arg("--max-files", type=positive, help="Capture file count limit (20000)"),
    arg("--max-file-bytes", type=positive, help="Per-file read limit (1 MiB)"),
    arg("--max-total-bytes", type=positive, help="Total captured bytes (32 MiB)"),
    arg("--limit", type=positive, help="Rows per page (query: 200, analyze: 60, others: 30); also raises query retention"),
    arg("--offset", type=nonnegative, help="Delivered row offset (0)"),
    arg("--max-bytes", type=positive, help="JSON response budget, at least 2048 (analyze: 24000, others: 12000)"),
    arg("--format", choices=("json", "table"), help="Result format; bare map defaults to text"),
    arg("--fields", help="Comma-separated result columns; full reports remain retained"),
    arg("--verbose", action="store_true",
        help="Full rows: ids, keys, digests, witness endpoints; history: events and every counter"),
)

TARGET_HISTORY = ("history", "inspect")
GRAPH_ARGS = (
    arg("--kind", ops=("map", "find"), action="append", choices=("file", "directory", "symbol", "external", "occurrence")),
    # The primer belongs to map; elsewhere these flags are accepted and ignored.
    arg("--primer", "--no-primer", ops=every("map"), dest="ignored_primer", action="store_true", help=argparse.SUPPRESS),
    arg("path", ops="map", nargs="?", help="Limit rows to this file, directory or symbol's file"),
    arg("--whole-repo-lines", ops="map", type=nonnegative, default="MAX_LINES",
        help="Bare map prints every source file as text at or under this many lines; 0 disables"),
    arg("--whole", ops="map", action="store_true", help="Bare map: print whole source up to {MAX_BYTES} bytes (default cap {TEXT_BYTES})"),
    arg("--primer", ops="map", dest="primer", action="store_true", default=None,
        help="Include the recent-work primer in JSON map output; bare map text includes it by default"),
    arg("--no-primer", ops="map", dest="primer", action="store_false", help="Disable the recent-work primer on bare map text"),
    arg("--primer-depth", ops="map", type=nonnegative, default=3, help="Recent sessions and non-merge commits to show (3); 0 disables"),
    arg("--primer-bytes", ops="map", type=positive, default=2048, help="Text primer byte budget (2048)"),
    arg("--primer-root", ops="map", action="append", default=[], help="Recording project root for the primer; repeatable"),
    arg("--primer-merges", ops="map", action="store_true", default=False, help="Include merge commits in the primer"),
    arg("--exclude-session", ops="map", action="append", default=[], help="Exclude session ID or recording path, including its lineage"),
    arg("text", ops="find", nargs="?"),
    arg("--word", ops="find", action="store_true", help="Match whole words only"),
    arg("--case-sensitive", ops="find", action="store_true", help="Match case exactly (default ignores case)"),
    arg("--regex", ops="find", nargs="?", const=True, default=False, help="Python regex PATTERN; legacy TEXT --regex also works"),
    arg("--path", ops="find", action="append", help="Include result path glob or directory; repeatable"),
    arg("--not-path", ops="find", action="append", default=[], help="Exclude result path glob or directory; repeatable"),
    arg("--count-by", ops="find", choices=("path",), help="Count matching result rows per path"),
    arg("--depth", ops=("neighbors", "paths", "impact"), type=positive, default=2, help="Traversal depth; actual omitted frontier is reported"),
    arg("--max-nodes", ops=("neighbors", "paths", "impact"), type=positive, default=1000),
    arg("--seconds", ops=("neighbors", "paths", "impact"), type=positive, default=5, help="Deadline per traversal"),
    arg("--predicate", ops=("neighbors", "paths"), action="append", choices="PREDICATES",
        help="Repeat to choose edge types; default IMPORTS,CALLS_STATIC"),
    arg("--grain", ops=("neighbors", "paths"), choices=("file", "symbol"), default="file", help="File projection or original symbol graph"),
    arg("target", ops="neighbors"),
    arg("--direction", ops="neighbors", choices=("in", "out", "both"), default="in"),
    arg("source", ops="paths"),
    arg("target", ops="paths"),
    arg("targets", ops="impact", nargs="*"),
    arg("--target", ops="impact", action="append", default=[], help="Additional planned target"),
    arg("--base", ops="impact", help="Baseline snapshot for full comparison"),
    arg("--head", ops="impact", help="Candidate snapshot for full comparison"),
    arg("target", ops=TARGET_HISTORY),
    arg("--recordings", ops=TARGET_HISTORY, action="append", default=[], help="Recording file/directory; repeatable"),
    arg("--project-root", ops=TARGET_HISTORY, action="append", default=[], help="Additional historical recording project root"),
    arg("--history-repo", ops=TARGET_HISTORY, action="append", default=[], help="Explicit old Git repository and path prefix: REPO=PREFIX"),
    arg("--root-map", ops=TARGET_HISTORY, action="append", default=[], help="Rewrite recorded path prefix OLD=NEW; discovery uses --project-root"),
    arg("--exclude-session", ops=TARGET_HISTORY, action="append", default=[], help="Exclude session ID or recording path, including its lineage"),
    arg("--no-sessions", ops=TARGET_HISTORY, action="store_true"),
    arg("--max-commits", ops=TARGET_HISTORY, type=positive, default=30),
    arg("--max-recordings", ops=TARGET_HISTORY, type=positive, default=25, help="Per-harness recording limit"),
    arg("--max-candidates", ops=TARGET_HISTORY, type=positive, default=20000,
        help="Per-harness discovery header limit (20000, as sessions.py with a project filter)"),
    arg("--max-scan-bytes", ops=TARGET_HISTORY, type=positive, default=64 * 1024 * 1024, help="Per-harness scan byte limit"),
    arg("--max-events", ops=TARGET_HISTORY, type=positive, default=25000, help="Per-harness event limit"),
    arg("report", ops="analyze", choices="REPORTS"),
    arg("--grain", "--kind", ops="analyze", dest="grain", choices=("file", "symbol"), help="Rank files or symbols; --kind is an alias"),
    arg("--include-tests", ops="analyze", action="store_true"),
    arg("--include-generated", ops="analyze", action="store_true",
        help="Rank generated/vendored files too (dist/, vendor/, @generated, large .d.ts)"),
    arg("--include-type-only", ops="analyze", action="store_true",
        help="cycles: count TS `import type` edges, which are erased at runtime"),
    arg("--exclude-entrypoints", ops="analyze", action="store_true"),
    arg("--exclude-public", ops="analyze", action="store_true"),
    arg("ref", ops="show", help="Returned snapshot/report/source/node/edge reference"),
    arg("--start-line", ops="show", type=positive, default=1),
    arg("--lines", ops="show", type=positive, default=80),
    arg("--sql", ops="query", scope="legacy", required=True),
    arg("--sql", ops="query", scope="common", required=False),
    arg("--param", ops="query", action="append", default=[], help="Bind NAME=VALUE to :NAME"),
    arg("--max-query-rows", ops="query", type=positive),
    arg("--seconds", ops="query", type=positive, default=5),
    # Common runtime only: positional SQL, custom inputs, planning and recording scope.
    arg("sql_text", ops="query", scope="common", nargs="?", help="Read-only SQLite SELECT/CTE; --sql is a compatibility alias"),
    arg("--input", ops="query", scope="common", action="append", default=[], metavar="NAME=FILE",
        help="Register JSON/JSONL rows (or - for stdin)"),
    arg("--type", ops="query", scope="common", action="append", default=[], metavar="TABLE.COLUMN=TYPE"),
    arg("--plan", ops="query", scope="common", action="store_true", help="Validate SQL and show dependencies before loading providers"),
    *(arg("--" + name, ops="query", scope="common", action="append", default=[])
      for name in ("recordings", "project-root", "root-map", "exclude-session")),
    *(arg("--" + name, ops="query", scope="common", type=positive)
      for name in ("max-recordings", "max-candidates", "max-scan-bytes", "max-events", "max-commits")),
    arg("table", ops="describe", scope="common", nargs="?", help="Focused public table schema"),
    arg("--intent", ops="inspect", choices=("change", "bug", "review"), default="change"),
    arg("--plan", ops="inspect", action="store_true", help="Describe retrieval stages without reading source/history"),
    arg("--depth", ops="inspect", type=positive, default=2),
    arg("--max-nodes", ops="inspect", type=positive, default=1000),
    arg("--budget", ops=("query", "inspect", "show"), scope="common", choices="POLICIES", default="standard"),
)

SESSION_ALL = names("session")
SESSION_ROWS = tuple(n for n in SESSION_ALL if n not in ("payload", "raw", "describe"))
SCAN = ("overview", "search", "select", "duplicates", "recurrence", "records", "edges", "context")
SQL = ("select", "duplicates")
EVENT_SELECT = ("search", "select", "duplicates")
FILES_HELP = "JSONL files or directories; defaults to every harness in settings.json"
SESSION_ARGS = (
    arg("--format", choices=("json", "table"), default="json",
        help="json envelope, or a table of result rows (harness groups flattened)"),
    arg("--fields", default=Per({n: "session,harness,kind,role,turn,tool,path,command,outcome,exit_code,text,ref" for n in SQL}),
        help=Per({n: "Comma-separated result columns; event fields, read before --sql" for n in EVENT_SELECT},
                 "Comma-separated result columns")),
    arg("--repo", ops=SESSION_ROWS, help="Repository worktree: recordings filter when --project is absent; "
                                         "select git/files tables; cite commit checks. Defaults to the invocation directory"),
    arg("--limit", ops="cite", type=int, default=None, help="Rows per page (all)"),
    arg("--offset", ops="cite", type=int, default=0),
    # describe is one static schema document, read whole once; recurrence rows carry example refs.
    arg("--max-bytes", type=int, default=Per({"describe": 16384, "recurrence": 16384}, 8192),
        help="Total JSON response byte budget (shared by every harness group)"),
    arg("--harness", ops=every("describe", family=SESSION_ALL), choices="PROFILES", default="auto",
        help="Force one profile; with default recordings, read only that harness's archives"),
    arg("--max-record-bytes", ops=every("describe", family=SESSION_ALL), type=int, default=2 * 1024 * 1024),
    arg("files", ops="cite", nargs="+", help="Written reports whose citations are checked; - reads stdin"),
    arg("files", ops=SCAN, nargs="*", help=FILES_HELP),
    arg("--project", ops=SCAN, default=None, help="Match recorded cwd exactly; defaults to the invocation directory; '' disables"),
    arg("--max-files", ops=SCAN, type=int, default=None, help="Per harness; defaults to 25 with a project filter, else 8"),
    arg("--max-candidates", ops=SCAN, type=int, default=None,
        help="Per harness/source group; defaults to 20000 with a project filter, else 1000"),
    arg("--max-scan-bytes", ops=SCAN, type=int, default=64 * 1024 * 1024, help="Per harness"),
    arg("--max-events", ops=SCAN, type=int, default=25000, help="Projection limit per harness"),
    arg("--max-text-bytes", ops=SCAN, type=int, default=None,
        help="Full text stored per harness; defaults to the selected recordings' size, between 8 MiB and 32 MiB"),
    arg("--preview-chars", ops=SCAN, type=int, default=300),
    arg("--text", ops=SCAN, action="append", default=[], help="Case-insensitive literal; repeated terms are OR"),
    arg("--role", ops=SCAN, choices=("user", "assistant", "tool")),
    arg("--human", ops=("overview", *EVENT_SELECT), action="store_true",
        help="Human requests only: user_message rows with origin=human outside "
             "subagent and forked recordings (parent_session absent)"),
    arg("--kind", ops=SCAN, action="append", default=[]),
    arg("--path", ops=SCAN, help="Normalized recorded activity path prefix"),
    arg("--limit", ops=SCAN, type=int, default=Per({"select": None, "duplicates": 20, "context": None}, 8),
        help="Rows per page; select defaults to 30, or with --sql to the query's own LIMIT "
             "(capped at 1000); context defaults to the selected event +/- --radius"),
    arg("--offset", ops=SCAN, type=int, default=Per({"context": None}, 0),
        help="Page each harness's matched rows before response budgeting; "
             "context pages default to the window around the selected event"),
    arg("files", ops="projects", nargs="*", help=FILES_HELP),
    arg("--max-candidates", ops="projects", type=int, default=1000, help="Newest headers read per harness/source group"),
    arg("--limit", ops="projects", type=int, default=30),
    arg("--offset", ops="projects", type=int, default=0),
    defaults("projects", project="", max_files=1),
    arg("--ref", ops=("context", "payload", "raw"), required=True, help="A row's cite token (id@line#hash) or its JSON ref object"),
    arg("--mode", ops="context", choices=("turn", "exchange", "nearby", "request"), default="turn"),
    arg("--radius", ops="context", type=int, default=3, help="Neighbors each side of the selected event (3)"),
    arg("--compare-ref", ops="context", help="Second request ref for changed-components comparison"),
    arg("--tail", ops="context", type=int, metavar="N", help="Page the last N events of the turn or window"),
    arg("--start", ops=("payload", "raw"), type=int, default=0, help="Character offset for payload; byte offset for raw"),
    arg("--chars", ops=("payload", "raw"), type=int, default=1000),
    arg("--tail", ops=("payload", "raw"), action="store_true"),
    arg("--find", ops=("payload", "raw"), help="Literal search; show a matching span"),
    arg("--pointer", ops="payload", help="JSON pointer into the original record; defaults to ref.pointer"),
    arg("--native-type", ops="records", action="append", default=[], help="Filter raw native record type"),
    arg("--parse-status", ops="records", choices=("ok", "malformed_record", "oversized_record"),
        help="Filter decoded, malformed, or oversized raw records"),
    arg("--include-tools", ops="search", action="store_true",
        help="Keep tool_call and tool_result rows; hidden by default unless --kind or --role tool asks"),
    arg("--order", ops="search", choices=("rank", "time"), default="rank",
        help="rank: human requests, then assistant decisions, then the rest; time: recorded order"),
    arg("--recordings", ops="search", action="store_true",
        help="Include each harness group's recording list (overview always has it)"),
    arg("--field", ops=EVENT_SELECT, action="append", default=[], help="Additional alias=/raw/record/pointer"),
    arg("--by", ops="recurrence", choices=("error", "command"), default="error",
        help="Group failed results by normalized error line or by command; --text groups by term"),
    arg("--min-sessions", ops="recurrence", type=int, default=2,
        help="Independent sessions a derived group needs; --text terms are always shown"),
    arg("--examples", ops="recurrence", type=int, default=5, help="Example refs per group, one per independent session"),
    arg("--include-noise", ops="recurrence", action="store_true",
        help="Keep tool and environment failures (file read/edit errors, missing paths, "
             "absent commands); hidden by default unless --text names terms"),
    arg("--span", ops="duplicates", type=int, default=7, help="Normalized code lines per compared window"),
    arg("--min-chars", ops="duplicates", type=int, default=200, help="Skip windows shorter than this many characters"),
    arg("--sql", ops=SQL, help="Read-only SELECT or CTE over every matched row (view rows, all fields); "
                               "--limit, when given, caps the query output"),
    arg("--max-query-rows", ops=SQL, type=int, default=100000),
    arg("--query-seconds", ops=SQL, type=float, default=30.0, help="Deadline for one --sql query"),
    arg("--memory-limit", ops=SQL, default="512MB", help="DuckDB memory budget, such as 256MB"),
    arg("--type", ops=SQL, action="append", default=[], metavar="[VIEW.]COLUMN=TYPE",
        help="Declare a column type: BIGINT, DOUBLE, VARCHAR, BOOLEAN, or JSON"),
    arg("--param", ops=SQL, action="append", default=[], metavar="NAME=VALUE", help="Bind a named query parameter ($name)"),
    arg("--full-text", ops=SQL, action="store_true", help="Re-read budget-omitted text for matched rows before --sql"),
    arg("--include", ops=SQL, default="",
        help="Comma list of repository tables: git (commit_links, commits, changes), "
             "files, symbols (code_items; implies files), content (files.content), "
             "edits (edit_hunks, edit_symbols; implies symbols)"),
    arg("--max-commits", ops=SQL, type=int, default=2000, help="Commits read from HEAD history"),
    arg("--follow", ops=SQL, metavar="PATH", help="Limit commits/changes to one path's history across renames"),
    arg("--max-repo-files", ops=SQL, type=int, default=20000, help="Worktree paths in the files table"),
    arg("--max-file-bytes", ops=SQL, type=int, default=1024 * 1024, help="Larger files are listed but not read, hashed or parsed"),
    arg("--root-map", ops=SQL, action="append", default=[], metavar="OLD=NEW",
        help="Read paths recorded under OLD as NEW for repo_path and edit tables (a fork, "
             "rename or move); with a project filter, recordings rooted at OLD are also read"),
)

ROWS_ARGS = (
    arg("positional", nargs="*", metavar="SQL_OR_INPUT", help="Optional SELECT, then input files"),
    arg("--input", action="append", default=[], help="Input file or '-' (repeat for joins)"),
    arg("--view", action="append", default=[], metavar="NAME=COMMAND", help="Run a producer command and register its stdout as view NAME"),
    arg("--sql"),
    arg("--describe", action="store_true"),
    arg("--shell", action="store_true", help="Evaluate --view commands through a shell; argv is the default"),
    arg("--limit", type=int, help="Output rows; defaults to the query's own LIMIT, capped at 1000"),
    arg("--max-bytes", type=int, default=8192),
    arg("--max-input-bytes", type=int, default=16 * 1024 * 1024),
    arg("--max-input-rows", type=int, default=100000),
    arg("--query-seconds", type=float, default="DEFAULT_SECONDS"),
    arg("--producer-seconds", type=float, default=120.0),
    arg("--memory-limit", default="DEFAULT_MEMORY"),
    arg("--type", action="append", default=[], metavar="[VIEW.]COLUMN=TYPE",
        help="Declare a column type: BIGINT, DOUBLE, VARCHAR, BOOLEAN, or JSON"),
    arg("--param", action="append", default=[], metavar="NAME=VALUE", help="Bind a named query parameter ($name)"),
)


def constants():
    """Values owned by other modules, resolved when a parser is built (avoids import cycles)."""
    from .budget import POLICIES
    from .engine import DEFAULT_MEMORY, DEFAULT_SECONDS
    from .graph_build import PREDICATES
    from .graph_reports import REPORTS
    from .profiles import PROFILES
    from .whole_repo import MAX_BYTES, MAX_LINES, TEXT_BYTES
    return {"PREDICATES": tuple(PREDICATES), "REPORTS": tuple(REPORTS), "POLICIES": tuple(POLICIES),
            "PROFILES": ("auto", *PROFILES), "MAX_LINES": MAX_LINES, "DEFAULT_SECONDS": DEFAULT_SECONDS,
            "DEFAULT_MEMORY": DEFAULT_MEMORY, "MAX_BYTES": MAX_BYTES, "TEXT_BYTES": TEXT_BYTES}


def add(parser, args, name=None, view="both"):
    names = constants()
    for item in args:
        if not item.applies(name, view):
            continue
        options = item.resolved(name)
        if "_defaults" in options:
            parser.set_defaults(**options["_defaults"])
            continue
        for key in ("choices", "default"):
            if isinstance(options.get(key), str) and options[key] in names:
                options[key] = names[options[key]]
        if isinstance(options.get("help"), str) and "{" in options["help"]:
            options["help"] = options["help"].format(**names)
        parser.add_argument(*item.flags, **options)
    return parser


class GraphParser(argparse.ArgumentParser):
    """Unknown options are reported by the chosen subcommand, with that subcommand's usage."""

    def error(self, message):
        name = message.partition("invalid choice: '")[2].partition("'")[0]
        if name in SESSION_COMMANDS:
            message += f"; {name} is a sessions.py command: python3 {SESSIONS} {name} ..."
        super().error(message)

    def parse_args(self, args=None, namespace=None):
        args, extra = self.parse_known_args(args, namespace)
        if extra:
            action = getattr(args, "action", None)
            choices = next((a.choices for a in self._actions if isinstance(a, argparse._SubParsersAction)), {})
            hint = ("; impact is file-level, --grain applies to neighbors, paths and analyze"
                    if action == "impact" and any(a.startswith("--grain") for a in extra) else "")
            (choices.get(action) or self).error("unrecognized arguments: " + " ".join(extra) + hint)
        return args


class SessionParser(argparse.ArgumentParser):
    """Unknown options are reported by the chosen subcommand, with that subcommand's usage."""

    def parse_args(self, args=None, namespace=None):
        args, extra = self.parse_known_args(args, namespace)
        if extra:
            choices = next((a.choices for a in self._actions if isinstance(a, argparse._SubParsersAction)), {})
            (choices.get(getattr(args, "action", None)) or self).error("unrecognized arguments: " + " ".join(extra))
        return args


def subparsers(parser):
    return next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))


def graph_parser(view="legacy", description=None):
    """remember.py: legacy graph commands, or the common runtime view that adds inspect and session verbs."""
    from . import graph_cli
    shared = add(argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS), GRAPH_SHARED)
    p = GraphParser(description=description or graph_cli.__doc__, parents=[shared])
    sub = p.add_subparsers(dest="action")
    for name in GRAPH + (("inspect",) if view == "common" else ()):
        op = OPERATIONS[name]
        text = op.summary if name == "inspect" else op.help
        q = sub.add_parser(name, help=text, description=text, parents=[shared])
        add(q, GRAPH_ARGS, name, view)
    if view == "common":
        sub.choices["query"].description = COMMON["query"] + " SQL dialect: SQLite."
        recordings = subparsers(session_parser()).choices
        for name in SESSION_COMMANDS:
            sub.add_parser(name, parents=[recordings[name]], add_help=False, help=OPERATIONS[name].help)
    return p


def session_parser():
    from . import session_cli
    p = SessionParser(description=session_cli.__doc__)
    sub = p.add_subparsers(dest="action")
    for name in SESSION_ALL:
        add(sub.add_parser(name), SESSION_ARGS, name)
    return p


def rows_parser():
    from . import row_cli
    return add(argparse.ArgumentParser(description=row_cli.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter), ROWS_ARGS)
