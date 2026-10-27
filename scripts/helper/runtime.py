"""Single entrypoint runtime: deterministic plans, lazy providers and evidence expansion.

The common query path is SQLite, including graph, Git, recordings and custom
inputs. Legacy sessions/rows DuckDB interfaces remain compatibility adapters.
"""
import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from . import catalog, continuations, delivery, graph_cli, session_cli, target_history
from .bindings import parse_params, parse_types, types_for
from .budget import Deadline, POLICIES
from .engine import Input, SQLiteQuery, IDENTIFIER, infer_type
from .envelope import load_rows
from .graph_queries import DEPENDENCIES, reference, impact
from .graph_store import Store, digest
from .operations import COMMON, GRAPH, OPERATIONS, SESSION_COMMANDS, graph_parser
from .providers import Providers


@dataclass(frozen=True)
class Request:
    args: argparse.Namespace
    argv: tuple
    expected_signature: str | None = None


@dataclass
class Result:
    document: dict
    signature: str | None = None
    argv: list | None = None


def parser():
    return graph_parser("common", "Remember: map, find, inspect, show, query. Other commands remain advanced compatibility operations.")


def normalize_prefix(argv):
    """Move recognized leading global flags after the verb, respecting option values."""
    p = graph_cli.parser()
    index = 0
    while index < len(argv):
        token = argv[index]
        if not token.startswith('-'):
            break
        name = token.split('=', 1)[0]
        option = p._option_string_actions.get(name)
        if option is None or name in ('--help', '-h'):
            break
        index += 1
        if '=' not in token and option.nargs != 0:
            index += 1
    if index and index < len(argv) and argv[index] in {*GRAPH, *SESSION_COMMANDS, "inspect"}:
        return [argv[index], *argv[:index], *argv[index + 1:]]
    return argv


def normalize(args, argv):
    args = graph_cli.defaults(args)
    if args.action in ("query", "inspect", "show"):
        policy = POLICIES[args.budget]
        for key, value in policy.items():
            flag = '--' + key.replace('_', '-')
            if not any(token == flag or token.startswith(flag + '=') for token in argv):
                setattr(args, key, value)
        # Continuations always carry an absolute scope, independent of the next cwd.
        args.repo = str(Path(args.repo).expanduser().resolve())
    if args.action == "query":
        if args.sql and args.sql_text:
            raise ValueError("Give the query once: positionally or with --sql")
        args.sql = args.sql or args.sql_text
        if not args.sql:
            raise ValueError("Supply query SQL; describe TABLE lists columns")
    return args


def custom_inputs(args):
    result, remaining = {}, 16 * 1024 * 1024
    declared = parse_types(args.type)
    for definition in args.input:
        name, sep, path = definition.partition('=')
        if not sep or not IDENTIFIER.fullmatch(name) or not path:
            raise ValueError("Use --input NAME=FILE (JSON, JSONL or -)")
        if name.lower() in {n.lower() for n in (*catalog.CATALOG, *result)}:
            raise ValueError(f"Reserved or duplicate input table: {name}")
        if path == '-':
            raw = sys.stdin.buffer.read(remaining + 1)
        else:
            with open(Path(path).expanduser(), 'rb') as stream:
                raw = stream.read(remaining + 1)
        remaining -= len(raw)
        if remaining < 0:
            raise ValueError("Custom inputs exceed the combined 16 MiB limit")
        rows, upstream = load_rows(raw.decode('utf-8'))
        if len(rows) > args.max_query_rows or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Custom inputs require object rows within the row budget")
        overrides = types_for(declared, name)
        names = sorted({key for row in rows for key in row} | set(overrides))
        if not names:
            raise ValueError(f"Empty table {name} needs --type {name}.COLUMN=TYPE")
        if len(names) > 200:
            raise ValueError("Custom tables allow at most 200 columns")
        types = {column: overrides.get(column) or {"str": "TEXT", "int": "INTEGER", "float": "REAL", "bool": "BOOLEAN"}[
                    infer_type([row.get(column) for row in rows])] for column in names}
        result[name] = Input(name, rows, upstream, names, types, "one supplied row")
    unknown = {view for view, _, _ in declared} - set(result)
    if unknown:
        raise ValueError(f"--type applies to supplied tables only: {', '.join(sorted(unknown))}")
    if sum(len(item.rows) for item in result.values()) > args.max_query_rows:
        raise ValueError("Custom inputs exceed the combined row budget")
    return result


# inspect bounds: source preview, history leads, executable candidate choices.
PREVIEW_LINES, HISTORY_LEADS, CANDIDATE_CHOICES = 80, 8, 5


class Runtime:
    def __init__(self, request):
        self.request = request
        self.args = request.args
        self.store = Store(self.args.repo, self.args.cache)

    def base_argv(self):
        argv = list(self.request.argv)
        argv = continuations.replace_option(argv, '--repo', self.store.root)
        argv = continuations.replace_option(argv, '--cache', str(self.store.path.parent))
        # Normalize both --flag VALUE and --flag=VALUE without shell parsing.
        for index, token in enumerate(argv):
            flag, equal, inline = token.partition('=')
            if flag not in ('--input', '--recordings', '--project-root'):
                continue
            at = index if equal else index + 1
            if at >= len(argv): continue
            value = inline if equal else argv[at]
            if flag == '--input':
                name, sep, path = value.partition('=')
                if sep and path != '-': value = name + '=' + str(Path(path).expanduser().resolve())
            else:
                value = str(Path(value).expanduser().resolve())
            argv[at] = flag + '=' + value if equal else value
        return argv

    def recovery(self, argv, purpose):
        """Widen the scan boundary once: standard to deep, dropping explicit limits the deep policy replaces."""
        if self.args.budget != 'standard' or argv is None:
            return None
        for key in POLICIES['deep']:
            argv = continuations.replace_option(argv, '--' + key.replace('_', '-'), None)
        argv = continuations.replace_option(argv, '--offset', None)
        return continuations.encode(continuations.replace_option(argv, '--budget', 'deep'), None,
                                    purpose + '; changes the scan boundary to --budget deep', 'coverage')

    def history_argv(self, ref, snapshot):
        """Target history with this request's recording scope and resolved limits, pinned to the inspected source."""
        args = self.args
        argv = ['history', ref, '--repo', self.store.root, '--cache', str(self.store.path.parent), '--snapshot', snapshot]
        for name in ('recordings', 'project-root', 'history-repo', 'root-map', 'exclude-session'):
            for value in getattr(args, name.replace('-', '_')):
                if name in ('recordings', 'project-root'):
                    value = str(Path(value).expanduser().resolve())
                argv += ['--' + name, value]
        if args.no_sessions:
            argv.append('--no-sessions')
        for key in ('max_commits', 'max_recordings', 'max_candidates', 'max_scan_bytes', 'max_events'):
            argv += ['--' + key.replace('_', '-'), str(getattr(args, key))]
        return argv

    def query(self, deadline):
        args = self.args
        supplied = custom_inputs(args)
        schemas = {name: item.columns for name, item in catalog.CATALOG.items()}
        schemas.update({name: item.types for name, item in supplied.items()})
        with SQLiteQuery(schemas, deadline.remaining()) as engine:
            try:
                reads = engine.plan(args.sql, parse_params(args.param))
            except ValueError as error:
                raise ValueError(f"{error}; use describe TABLE for columns (SQLite dialect)") from None
            names = set(reads)
            plan = {"tables": reads, "providers": catalog.providers_for(names), "budget": args.budget,
                    "limits": {key: getattr(args, key) for key in POLICIES[args.budget]},
                    "dialect": "sqlite", "retention": "transient"}
            if args.plan:
                return Result({"operation": "query", "results": [{"table": name, "columns_read": columns,
                                "provider": catalog.CATALOG[name].provider if name in catalog.CATALOG else "supplied"}
                               for name, columns in reads.items()], "plan": plan}, argv=self.base_argv())
            providers = Providers(args, self.store, deadline)
            providers.load(names)
            count = 0
            fingerprint = []
            for name in sorted(names):
                item = supplied[name] if name in supplied else providers.input(name)
                count += len(item.rows)
                if count > args.max_query_rows:
                    raise ValueError("Required inputs exceed the row budget; narrow source scope or use --budget deep")
                fingerprint.append({"name": name, "rows": digest(item.rows), "coverage": item.upstream})
                engine.load(item)
            # SQL runs against full loaded inputs. Delivery paging happens afterwards.
            cap = min(args.max_query_rows, max(1000, args.offset + args.limit))
            output = engine.evaluate(cap)
        coverage = dict(providers.coverage)
        for name in names & set(supplied):
            upstream = supplied[name].upstream
            coverage[name] = {**upstream, "complete": upstream.get("complete"),
                              "basis": "supplied rows only; external completeness is not assumed"}
        partial = any(c.get("complete") is not True for c in coverage.values())
        argv = self.base_argv()
        if providers.graph:
            argv = continuations.replace_option(argv, '--snapshot', providers.graph.snapshot)
        recover = None
        if any(c.get("complete") is False for c in providers.coverage.values()):
            recover = self.recovery(argv, "Rerun with wider provider limits")
        return Result({"operation": "query", "status": "partial" if partial else "ok", "next": [recover] if recover else [],
                       "results": output["results"], "more_rows": not output["query_complete"],
                       "coverage": coverage, "scope": {"engine": "sqlite", "retention": "transient",
                       "providers": providers.loaded, "counting_scope": "full bounded provider selections before delivery"}},
                      digest(fingerprint), argv)

    def inspect(self, deadline):
        args = self.args
        stages = ['resolve', 'source', 'relationships', 'history', 'expand']
        if args.plan:
            return Result({"operation": "inspect", "results": [{"stage": s} for s in stages],
                           "plan": {"intent": args.intent, "budget": args.budget, "limits": POLICIES[args.budget],
                                    "history": "disabled sessions" if args.no_sessions else "target-scoped"}})
        graph = graph_cli.get_graph(self.store, args)
        matches = graph.resolve(args.target)
        if len(matches) != 1:
            candidates = [graph.public(graph.nodes[n]) for n in matches]
            argv = continuations.replace_option(self.base_argv(), '--snapshot', graph.snapshot)
            at = argv.index(args.target, 1) if args.target in argv[1:] else None
            # One executable choice per candidate, pinned to the snapshot that produced the ambiguity.
            choices = [continuations.encode(argv[:at] + [c['ref']] + argv[at+1:], None,
                                            f"Inspect candidate {c['ref']}", "expansion")
                       for c in candidates[:CANDIDATE_CHOICES]] if at else []
            if len(candidates) > len(choices) or not matches:
                choices.append({"purpose": "Choose one candidate ref, then inspect it" if matches
                                else "Use map or find to locate the target"})
            return Result({"operation": "inspect", "status": "partial", "results": candidates,
                           "coverage": {"target": {"complete": False, "reason": "ambiguous" if matches else "unresolved",
                                                   "candidates": len(candidates)}},
                           "next": choices})
        node = graph.public(graph.nodes[matches[0]])
        if node['kind'] not in ('file', 'symbol'):
            raise ValueError("inspect requires a file or symbol; use map for a directory")
        pinned = copy.copy(args)
        pinned.snapshot, pinned.target = graph.snapshot, node['ref']
        rows, steps, coverage = [], [], {}
        src = next(r for r in graph.body['source']['files'] if r['path'] == node['path'])
        text = (src.get('text') or '').splitlines()
        start, end = node.get('line') or 1, node.get('end_line') or len(text)
        source_ref = reference(graph.snapshot, 'source', node['path'])
        rows.append({"section": "source", "path": node['path'], "line": start,
                     "text": '\n'.join(text[start-1:min(end, start+PREVIEW_LINES-1)]), "ref": source_ref,
                     "text_complete": src.get('text') is not None and end < start+PREVIEW_LINES})
        steps += [{"stage": "resolve", "state": "completed"}, {"stage": "source", "state": "completed"}]
        deadline.check()
        if args.intent == 'change':
            rel = impact(graph, [node['ref']], depth=args.depth, max_nodes=args.max_nodes, seconds=deadline.remaining())
            rows += [{"section": "relationships", **r} for r in rel['results']]
            rel_incomplete = graph_cli.incomplete(rel, graph)
        else:
            grain = 'symbol' if node['kind'] == 'symbol' else 'file'
            found, limits = graph.walk(graph.seeds(node['ref'], grain), 'both', DEPENDENCIES, grain,
                                       args.depth, args.max_nodes, seconds=deadline.remaining())
            rows += [{"section": "relationships", **r} for r in found]
            rel = graph.document('neighbors', found, traversal=limits)
            if limits['bounds']: rel['gaps'] = [*rel['gaps'], {"area": "traversal", "reason": "bounded"}]
            rel_incomplete = graph_cli.incomplete(rel, graph)
        coverage['relationships'] = {"complete": not rel_incomplete, "gaps": rel_incomplete,
                                     "meaning": "static potential relationships; absence is not proof of safety"}
        steps.append({"stage": "relationships", "state": "bounded" if rel_incomplete else "completed"})
        deadline.check()
        history = target_history.run(pinned, self.store, lambda store, options, pin=None: graph)
        compact = target_history.compact(history['results'])
        rows += [{"section": "history", **r} for r in compact[:HISTORY_LEADS]]
        history_partial = any(c.get('state') in ('partial', 'unavailable') for c in history['coverage'].get('git', []))
        history_partial |= history['coverage'].get('sessions', {}).get('state') in ('partial', 'unavailable')
        coverage['history'] = {"complete": not history_partial, "details": target_history.summary(history['coverage']),
                               "leads_omitted": max(0, len(compact)-HISTORY_LEADS)}
        steps.append({"stage": "history", "state": "bounded" if history_partial else "completed"})
        # Expand one strongest session lead. The selected event remains distinguishable from previews.
        expanded = False
        for row in history['results']:
            ref = row.get('ref')
            if isinstance(ref, dict) or (isinstance(ref, str) and '@' in ref and '#' in ref):
                deadline.check()
                try:
                    selected = self.expand_session(ref)
                    for event in selected.get('results', []):
                        if event.get('selected'):
                            rows.append({"section": "evidence", **event})
                            expanded = True
                    coverage['expansion'] = {"complete": expanded}
                except (ValueError, OSError) as error:
                    coverage['expansion'] = {"complete": False, "reason": str(error)}
                break
        steps.append({"stage": "expand", "state": "completed" if expanded else "not_available"})
        argv = continuations.replace_option(self.base_argv(), '--snapshot', graph.snapshot)
        next_items = []
        if history_partial:
            recover = self.recovery(argv, "Rescan target history with wider recording limits")
            if recover: next_items.append(recover)
        if src.get('text') is not None and end >= start+PREVIEW_LINES:
            next_items.append(continuations.encode(
                ['show', source_ref, '--start-line', str(start+PREVIEW_LINES), '--lines', str(end-start-PREVIEW_LINES+1),
                 '--repo', self.store.root, '--cache', str(self.store.path.parent)], None,
                "Read the rest of the target source", "expansion"))
        if len(compact) > HISTORY_LEADS:
            next_items.append(continuations.encode(self.history_argv(node['ref'], graph.snapshot), None,
                                                   "Read all target history leads", "expansion"))
        document = {"operation": "inspect", "target": node, "results": rows, "steps": steps, "coverage": coverage,
                    "scope": {"intent": args.intent, "snapshot": graph.snapshot, "retention": "transient"},
                    "status": "partial" if any(c.get('complete') is False for c in coverage.values()) else "ok", "next": next_items}
        return Result(document, digest([graph.snapshot, history['results'], history['coverage']]), argv)

    def expand_session(self, ref):
        from . import actions
        value = json.dumps(ref) if isinstance(ref, dict) else ref
        args = session_cli.parser().parse_args(['context', '--ref', value, '--mode', 'exchange', '--repo', self.store.root])
        args.limit = 7
        return actions.run(args)

    def show(self, deadline):
        ref = self.args.ref
        if isinstance(ref, str) and (ref.startswith('{') or ('@' in ref and '#' in ref)):
            result = self.expand_session(ref)
            result['operation'] = 'show'
            from .envelope import incomplete
            reasons = incomplete(result, result.get('scope', {}))
            result['status'] = 'partial' if reasons else 'ok'
            result['coverage'] = {"session": {"complete": not reasons, "reasons": reasons}}
            return Result(result, digest(result.get('results', [])), self.base_argv())
        if re.fullmatch(r'(?:git:)?[0-9a-fA-F]{40}', ref):
            from .git_resolve import GitResolver
            sha = ref.removeprefix('git:')
            text = GitResolver().run(self.store.root, 'show', '--no-ext-diff', '--no-textconv', '--format=fuller', sha,
                                     timeout=deadline.remaining())
            if text is None: raise ValueError('Commit unavailable in the selected repository')
            rows = [{"line": i+1, "text": line, "ref": sha} for i,line in enumerate(text.splitlines())]
            return Result({"operation": "show", "results": rows, "coverage": {"commit": {"complete": True}}}, digest(text), self.base_argv())
        doc = graph_cli.show(self.store, self.args)
        return Result(doc, digest(doc), self.base_argv())

    def execute(self):
        with Deadline(getattr(self.args, 'seconds', 30)) as deadline:
            result = getattr(self, self.args.action)(deadline)
        if self.request.expected_signature and result.signature != self.request.expected_signature:
            raise ValueError("Continuation source changed; rerun the original request. Paging was not silently recomputed.")
        return result


def resume(p, args, argv, incoming):
    """Replace a continue: token with its saved request; presentation may change, evidence scope may not."""
    saved = continuations.decode(args.ref)
    argv = saved['argv']
    for flag in ('--max-bytes', '--format', '--fields', '--limit'):
        for index, token in enumerate(incoming):
            if token == flag and index + 1 < len(incoming):
                argv = continuations.replace_option(argv, flag, incoming[index + 1])
            elif token.startswith(flag + '='):
                argv = continuations.replace_option(argv, flag, token.split('=', 1)[1])
    if continuations.stdin_tables(argv) and sys.stdin.isatty():
        # Never block waiting on a terminal; the signature rejects different piped rows.
        raise ValueError("This continuation replays stdin: pipe the same input again")
    return normalize(p.parse_args(argv), argv), argv, saved.get('signature')


def legacy_query(args, argv):
    """The original graph-only query --sql shape keeps its retained v1 report; None when it does not apply."""
    if args.sql_text is not None or args.plan or args.input or args.type or '--budget' in argv:
        return None
    try:
        with SQLiteQuery(graph_cli.TABLES, args.seconds) as legacy_plan:
            legacy_plan.plan(args.sql, parse_params(args.param))
    except ValueError:
        return None  # Additional tables/columns use the canonical catalog.
    old_args, extra = graph_cli.parser().parse_known_args(argv)
    if extra:
        return None
    old_args = graph_cli.defaults(old_args)
    store = Store(old_args.repo, old_args.cache)
    delivery.deliver("retained", graph_cli.run(old_args, store), old_args, store)
    return 0


def run_describe(args, argv, expected):
    rows = catalog.describe(args.table)
    scope = {"common_commands": COMMON, "dialect": "sqlite"}
    if args.table is None:
        # The overview keeps its retained v1 report; schema rows hold no recorded data.
        rows = [{"kind": "command", "name": name, "description": description}
                for name, description in COMMON.items()] + [{"kind": "table", **r} for r in rows]
        doc = {"operation": "describe", "results": rows, "snapshots": [], "scope": scope, "gaps": [], "coverage": {}}
        delivery.deliver("retained", doc, args, Store(args.repo, args.cache))
    else:
        doc = {"operation": "describe", "results": rows, "snapshots": [], "scope": {**scope, "retention": "transient"}}
        delivery.deliver("common", doc, args)
    return 0


def run_runtime(args, argv, expected):
    if args.action == 'query' and expected is None:
        handled = legacy_query(args, argv)
        if handled is not None:
            return handled
    if args.action == 'show' and args.ref.startswith(('snapshot:', 'report:')) and expected is None:
        store = Store(args.repo, args.cache)
        delivery.deliver("retained", graph_cli.show(store, args), args, store)
        return 0
    result = Runtime(Request(args, tuple(argv), expected)).execute()

    def next_page(offset, empty, need=None):
        following = continuations.replace_option(result.argv, '--offset', offset)
        effect = 'delivery'
        if args.action == 'query' and offset >= args.max_query_rows:
            following = continuations.replace_option(following, '--max-query-rows', args.max_query_rows * 2)
            effect = 'coverage'
        if empty:
            following = continuations.replace_option(following, '--max-bytes', max(args.max_bytes * 2, need or 0))
        return continuations.mark_stdin(continuations.encode(following, result.signature,
            'Increase output budget to read the next row' if empty else 'Read the next page', effect))
    for item in result.document.get('next') or []:
        continuations.mark_stdin(item)
    delivery.deliver("common", result.document, args, continuation=next_page if result.argv else None)
    return 0


def run_graph(args, argv, expected):
    store = Store(args.repo, args.cache)
    doc = graph_cli.run(args, store)
    if 'text' in doc:
        sys.stdout.write(doc['text'])
    else:
        delivery.deliver(OPERATIONS[args.action].delivery, doc, args, store)
    return 0


def run_session(args, argv, expected):
    return session_cli.main(argv)


ROUTES = {"runtime": run_runtime, "describe": run_describe, "graph": run_graph, "session": run_session}


def main(argv=None):
    incoming = list(sys.argv[1:] if argv is None else argv)
    argv = normalize_prefix(incoming)
    # Legacy adapters share the package; never exec another CLI process.
    # Session operations own their parser; route them before the common parser sees their flags.
    if argv and argv[0] in OPERATIONS and OPERATIONS[argv[0]].route == "session":
        return run_session(None, argv, None)
    p = parser()
    try:
        args = normalize(p.parse_args(argv), argv)
        expected = None
        if args.action == 'show' and args.ref.startswith(continuations.PREFIX):
            args, argv, expected = resume(p, args, argv, incoming)
        return ROUTES[OPERATIONS[args.action].route](args, argv, expected)
    except (ValueError, OSError, RecursionError) as error:
        print(json.dumps({"schema_version": 2, "status": "error", "results": [], "error": str(error)[:4000]}))
        return 2
    except KeyboardInterrupt:
        # Cancellation is not partial evidence: nothing was delivered or retained for this request.
        print(json.dumps({"schema_version": 2, "status": "error", "results": [], "error": "cancelled"}))
        return 130
