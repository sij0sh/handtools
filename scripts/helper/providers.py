"""Invocation-local provider registry; shared source, Git and recording datasets."""
import os
from pathlib import Path
from types import SimpleNamespace
from . import catalog, cite, commit_links, edit_hunks, git_file_history, graph_cli, graph_queries, repo_files
from .discovery import candidate_files
from .engine import Input
from .enrichment import remap, parse_root_map
from .git_resolve import GitResolver
from .graph_store import digest
from .options import DiscoveryOptions, ScanOptions
from .projection import clean
from .recording_scan import lineages, scan_group, text_budget
from .records import RecordCache


class Providers:
    def __init__(self, args, store, deadline):
        self.args, self.store, self.deadline = args, store, deadline
        self.loaded, self.tables, self.coverage = [], {}, {}
        self.graph = None
        self.recordings = []
        self.resolver = GitResolver()
        self.cache = RecordCache(2 * 1024 * 1024)
        self.root_map = parse_root_map(getattr(args, "root_map", []))
        self.worktree = store.root
        self.repo_id = None
        self.roots = {}
        self.mapped_events = set()

    def load(self, names):
        for provider in catalog.providers_for(names):
            if provider not in self.loaded:
                self.deadline.check()
                getattr(self, "load_" + provider)()
                self.loaded.append(provider)
                self.deadline.check()

    def input(self, name):
        definition = catalog.CATALOG[name]
        return Input(name, self.tables[name], self.coverage[definition.provider],
                     list(definition.columns), definition.columns, definition.grain)

    def load_graph(self):
        self.graph = graph_cli.get_graph(self.store, self.args)
        for item in graph_queries.inputs(self.graph):
            self.tables[item.name] = item.rows
        self.tables["files"] = [{**row, "content": row.get("text"),
                                  "lines": len(row["text"].splitlines()) if row.get("text") is not None else None,
                                  "language": (self.graph.files.get(row["path"]) or {}).get("language")}
                                 for row in self.tables["files"]]
        self.tables["code_items"] = [{**self.graph.public(n), "kind": n.get("symbol_kind"), "repo_id": self.store.root}
                                     for n in self.graph.nodes.values() if n["kind"] == "symbol"]
        self.by_path = {row["path"]: row for row in self.tables["files"]}
        self.items_by_path = {}
        for item in self.tables["code_items"]:
            self.items_by_path.setdefault(item["path"], []).append(item)
        doc = self.graph.document("query", [])
        gaps = graph_cli.incomplete(doc, self.graph)
        self.coverage["graph"] = {"complete": not gaps, "incomplete_reasons": sorted({g["area"] for g in gaps}),
                                  "snapshot": self.graph.snapshot, "gaps": len(self.graph.body["gaps"])}

    def load_recordings(self):
        args = self.args
        scope, groups = {"duplicates_skipped": 0}, []
        options = DiscoveryOptions(files=tuple(getattr(args, "recordings", [])), project=self.store.root,
                                   also_roots=tuple(getattr(args, "project_root", [])),
                                   max_files=args.max_recordings, max_candidates=args.max_candidates)
        policy = SimpleNamespace(max_text_bytes=None, max_scan_bytes=args.max_scan_bytes)
        try:
            candidates = candidate_files(options, scope)
        except ValueError as error:
            if getattr(args, "recordings", []):
                raise
            self.tables["events"] = self.tables["rows"] = []
            self.coverage["recordings"] = {"complete": False, "state": "unavailable", "error": str(error)}
            return
        for harness, files, counters in candidates:
            self.deadline.check()
            scan = ScanOptions(harness=harness, max_scan_bytes=args.max_scan_bytes, max_events=args.max_events,
                               max_text_bytes=text_budget(policy, files, counters))
            self.recordings.extend(scan_group(files, scan, counters))
            groups.append(counters)
        keys = lineages(self.recordings)
        excluded = set(getattr(args, "exclude_session", []))
        excluded.update(v for v in (os.environ.get("CODEX_THREAD_ID"), os.environ.get("PI_SESSION_ID"), os.environ.get("CLAUDE_SESSION_ID")) if v)
        self.recordings = [r for r in self.recordings if not ({r["session"], r["file"], keys[r["file"]]} & excluded)]
        self.roots = {r["file"]: r.get("root") for r in self.recordings}
        rows = []
        for recording in self.recordings:
            for event in recording["events"]:
                event["independent_session"] = keys[recording["file"]]
                row = clean(event, complete=True)
                row = cite.tagged(row, event["ref"])
                row.update(repo_path=self.repo_path(event))
                rows.append(row)
        self.tables["events"] = self.tables["rows"] = rows
        reasons = []
        if not scope.get("discovery_complete", True): reasons.append("discovery_limit")
        if any(not g.get("scan_complete", True) for g in groups): reasons.append("scan_limit")
        if any(not g.get("text_complete", True) for g in groups): reasons.append("text_limit")
        if any(g.get("project_unknown") for g in groups): reasons.append("project_unknown")
        self.coverage["recordings"] = {"complete": not reasons, "incomplete_reasons": reasons,
                                       "files_scanned": sum(g.get("files_scanned", 0) for g in groups),
                                       "project": self.store.root, "current_session_exclusion": "configured" if excluded else "unknown",
                                       "signature": digest([g.get("snapshot", []) for g in groups])}

    def load_git(self):
        root = self.resolver.repo(self.store.root)
        self.repo_id = self.resolver.identity(root)
        if root:
            commits, changes, coverage = git_file_history.history(self.resolver, root, self.args.max_commits, None)
        else:
            commits, changes, coverage = [], [], {"complete": False, "error": "not a Git repository"}
        self.tables["commits"] = [{**row, "ref": row["sha"]} for row in commits]
        self.tables["changes"] = changes
        self.coverage["git"] = coverage

    def load_links(self):
        rows = commit_links.witnesses(self.recordings, self.resolver, self.cache, self.resolver.repo(self.store.root))
        self.tables["commit_links"] = rows
        missing = sum(row.get("confidence") == "unresolved" for row in rows)
        self.coverage["links"] = {"complete": not missing and self.coverage["recordings"]["complete"], "unresolved": missing}

    def load_edits(self):
        self.repo_id = self.resolver.identity(self.resolver.repo(self.store.root)) or self.store.root
        hunks, symbols, coverage = edit_hunks.derive(self.recordings, self.cache, self)
        self.tables["edit_hunks"], self.tables["edit_symbols"] = hunks, symbols
        coverage["complete"] = coverage.get("complete", True) and all(self.coverage[p]["complete"] for p in ("recordings", "graph"))
        coverage["source_basis"] = "pinned_source"
        self.coverage["edits"] = coverage

    def load_status(self):
        root = self.resolver.repo(self.store.root)
        if root:
            rows, _, coverage = repo_files.snapshot(self.resolver, root, self.args.max_files, self.args.max_file_bytes)
        else:
            rows, coverage = [], {"complete": False, "error": "not a Git repository"}
        self.tables["file_status"], self.coverage["status"] = rows, coverage

    def repo_path(self, event):
        path, location = event.get("path"), event.get("path_location")
        if not path or location not in ("repository", "external"):
            return None
        if location == "repository":
            root = self.roots.get(event.get("recording_id"))
            if not root: return None
            path = os.path.join(root, path)
        path, _ = remap(path, self.root_map)
        path = os.path.abspath(path)
        try:
            if os.path.commonpath([path, self.store.root]) == self.store.root:
                return os.path.relpath(path, self.store.root).replace(os.sep, "/")
        except ValueError:
            pass
        return None

    def current_lines(self, path):
        row = self.by_path.get(path, {})
        return (edit_hunks.split_lines(row["content"]), None) if row.get("content") is not None else (None, "source_unavailable")

    def has_items(self, path):
        return (self.graph.files.get(path) or {}).get("parse_state") in ("parsed", "parsed_with_errors")

    def items_for(self, path):
        return self.items_by_path.get(path, [])
