"""Declarative operation registry: one definition per CLI operation drives parsers, help, routing and delivery.

Each argument is defined once with the operations it applies to. remember.py parsers
(legacy graph and common runtime views) are generated from it.
"""
import argparse
from dataclasses import dataclass


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
    family: str          # graph | runtime
    help: str
    route: str           # runtime | graph | describe
    delivery: str        # common | retained
    tier: str = "advanced"
    summary: str = ""    # common-interface description, when it differs from help


OPERATIONS = {op.name: op for op in (
    Operation("map", "graph", "List source files, directories or symbols and graph coverage (default).",
              "graph", "retained", "common", "Orient in current source."),
    Operation("find", "graph", "Locate names, paths and literal source occurrences; matches are candidates.",
              "graph", "retained", "common", "Locate a concrete anchor."),
    Operation("show", "graph", "Expand retained source, nodes, edges or report pages without refreshing them.",
              "runtime", "common", "common", "Expand evidence or execute a returned continuation."),
    Operation("query", "graph", "Run one read-only SQLite SELECT/CTE over nodes, edges, files and gaps.",
              "runtime", "common", "common", "Query built-in and custom tables; dependencies load automatically."),
    Operation("describe", "graph", "Describe commands, predicates and SQL tables without scanning source.", "describe", "common"),
    Operation("activity", "runtime", "Chronological recorded operations for one file or symbol target, with outcomes and witnesses.",
              "runtime", "common", "common", "See what was read, written, run and committed for a target."),
    Operation("recall", "runtime", "Rank past commits like a planned feature, with linked requests and current path state.",
              "runtime", "common", "common", "Before building: find prior similar work to extend."),
    Operation("inspect", "runtime", "Collect source, consumers, dependencies and relevant history.",
              "runtime", "common", "common", "Collect source, consumers, dependencies and relevant history."),
)}


def names(family):
    return tuple(n for n, op in OPERATIONS.items() if op.family == family)


GRAPH = names("graph")
COMMON = {n: op.summary for n, op in OPERATIONS.items() if op.tier == "common"}


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

    def applies(self, name):
        return self.ops is None or name in self.ops

    def resolved(self, name):
        return {k: v.get(name) if isinstance(v, Per) else v for k, v in self.options.items()}


def arg(*flags, ops=None, **options):
    return Arg(flags, options, frozenset((ops,) if isinstance(ops, str) else ops) if ops is not None else None)


def defaults(ops, **values):
    """A set_defaults entry for the listed operations."""
    return arg(ops=ops, _defaults=values)


def every(*excluded, family=GRAPH + ("inspect", "recall")):
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
    arg("--limit", type=positive, help="Rows per page (query: 200, others: 30); also raises query retention"),
    arg("--offset", type=nonnegative, help="Delivered row offset (0)"),
    arg("--max-bytes", type=positive, help="JSON response budget, at least 2048 (12000)"),
    arg("--format", choices=("json", "table"), help="Result format; bare map defaults to text"),
    arg("--fields", help="Comma-separated result columns; full reports remain retained"),
    arg("--verbose", action="store_true",
        help="Full rows: ids, keys, digests, witness endpoints"),
)

TARGET_HISTORY = ("inspect",)
ACTIVITY = ("activity",)
RECALL = ("recall",)
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
    arg("target", ops=TARGET_HISTORY),
    arg("target", ops=ACTIVITY, help="Repository-relative path, path::qualified.name, or returned node ref"),
    arg("--recordings", ops=TARGET_HISTORY + ACTIVITY, action="append", default=[], help="Recording file/directory; repeatable"),
    arg("--project-root", ops=TARGET_HISTORY + ACTIVITY, action="append", default=[], help="Additional historical recording project root"),
    arg("--history-repo", ops=TARGET_HISTORY, action="append", default=[], help="Explicit old Git repository and path prefix: REPO=PREFIX"),
    arg("--root-map", ops=TARGET_HISTORY + ACTIVITY, action="append", default=[], help="Rewrite recorded path prefix OLD=NEW; discovery uses --project-root"),
    arg("--exclude-session", ops=TARGET_HISTORY + ACTIVITY, action="append", default=[], help="Exclude session ID or recording path, including its lineage"),
    arg("--no-sessions", ops=TARGET_HISTORY, action="store_true"),
    arg("--max-commits", ops=TARGET_HISTORY, type=positive, default=30),
    arg("--max-recordings", ops=TARGET_HISTORY + ACTIVITY, type=positive, default=25, help="Per-harness recording limit"),
    arg("--max-candidates", ops=TARGET_HISTORY + ACTIVITY, type=positive, default=20000,
        help="Per-harness discovery header limit (20000, as sessions.py with a project filter)"),
    arg("--max-scan-bytes", ops=TARGET_HISTORY + ACTIVITY, type=positive, default=64 * 1024 * 1024, help="Per-harness scan byte limit"),
    arg("--max-events", ops=TARGET_HISTORY + ACTIVITY, type=positive, default=25000, help="Per-harness event limit"),
    arg("ref", ops="show", help="Returned snapshot/report/source/node/edge reference"),
    arg("--start-line", ops="show", type=positive, default=1),
    arg("--lines", ops="show", type=positive, default=80),
    arg("--sql", ops="query", required=False),
    arg("--param", ops="query", action="append", default=[], help="Bind NAME=VALUE to :NAME"),
    arg("--max-query-rows", ops="query", type=positive),
    arg("--seconds", ops="query", type=positive, default=5),
    # Query: positional SQL, custom inputs, planning and recording scope.
    arg("sql_text", ops="query", nargs="?", help="Read-only SQLite SELECT/CTE; --sql is a compatibility alias"),
    arg("--input", ops="query", action="append", default=[], metavar="NAME=FILE",
        help="Register JSON/JSONL rows (or - for stdin)"),
    arg("--type", ops="query", action="append", default=[], metavar="TABLE.COLUMN=TYPE"),
    arg("--plan", ops="query", action="store_true", help="Validate SQL and show dependencies before loading providers"),
    *(arg("--" + name, ops="query", action="append", default=[])
      for name in ("recordings", "project-root", "root-map", "exclude-session")),
    *(arg("--" + name, ops="query", type=positive)
      for name in ("max-recordings", "max-candidates", "max-scan-bytes", "max-events", "max-commits")),
    arg("table", ops="describe", nargs="?", help="Focused public table schema"),
    arg("--intent", ops="inspect", choices=("change", "bug", "review"), default="change"),
    arg("--plan", ops="inspect", action="store_true", help="Describe retrieval stages without reading source/history"),
    arg("--depth", ops="inspect", type=positive, default=2),
    arg("--max-nodes", ops="inspect", type=positive, default=1000),
    arg("text", ops=RECALL, nargs="+", help="Feature words, e.g. 'export csv button'"),
    *(arg("--" + name, ops=RECALL, action="append", default=[])
      for name in ("recordings", "project-root", "root-map", "exclude-session")),
    *(arg("--" + name, ops=RECALL, type=positive)
      for name in ("max-recordings", "max-candidates", "max-scan-bytes", "max-events", "max-commits")),
    arg("--no-sessions", ops=RECALL, action="store_true", help="Git only; skip recordings"),
    arg("--budget", ops=("query", "inspect", "show", "recall", "activity"), choices="POLICIES", default="standard"),
)

def constants():
    """Values owned by other modules, resolved when a parser is built (avoids import cycles)."""
    from .budget import POLICIES
    from .graph_build import PREDICATES
    from .whole_repo import MAX_BYTES, MAX_LINES, TEXT_BYTES
    return {"PREDICATES": tuple(PREDICATES), "POLICIES": tuple(POLICIES),
            "MAX_LINES": MAX_LINES, "MAX_BYTES": MAX_BYTES, "TEXT_BYTES": TEXT_BYTES}


def add(parser, args, name=None):
    names = constants()
    for item in args:
        if not item.applies(name):
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

    def parse_args(self, args=None, namespace=None):
        args, extra = self.parse_known_args(args, namespace)
        if extra:
            choices = next((a.choices for a in self._actions if isinstance(a, argparse._SubParsersAction)), {})
            (choices.get(getattr(args, "action", None)) or self).error("unrecognized arguments: " + " ".join(extra))
        return args


def graph_parser():
    """remember.py: every operation, one parser."""
    shared = add(argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS), GRAPH_SHARED)
    p = GraphParser(description="Remember: recall, map, find, inspect, activity, show, query.", parents=[shared])
    sub = p.add_subparsers(dest="action")
    for name in GRAPH + ("inspect", "recall", "activity"):
        op = OPERATIONS[name]
        text = op.summary if name in ("inspect", "recall", "activity") else op.help
        q = sub.add_parser(name, help=text, description=text, parents=[shared])
        add(q, GRAPH_ARGS, name)
    sub.choices["query"].description = COMMON["query"] + " SQL dialect: SQLite."
    return p
