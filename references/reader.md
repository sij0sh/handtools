# Setup and limits

The common runtime (`remember.py`, including cross-source SQL) needs Python 3.11+ and only the standard library.
Python AST extraction is built in. Optional tree-sitter packages add syntax/import
extraction for Rust, Go, TypeScript/JavaScript and shell; missing grammars are
reported, not installed automatically.

All SQL runs on stdlib SQLite.
`requirements.txt` holds only the optional tree-sitter grammars.

macOS: the Xcode `/usr/bin/python3` is 3.9; use Homebrew or python.org 3.11+.

All commands expose `--help`. Schemas come from `remember.py describe [TABLE]`.

Graph source, cache, parser and traversal limits: [graph.md](graph.md).
Historical source profiles live in `scripts/profiles`; recording roots in
`settings.json`. Profiles normalize Codex, Claude Code and pi JSONL. Unknown,
malformed and oversized records remain visible as gaps; recorded branch/parent
links are preserved where available. Text may be omitted by scan or output budgets.

Bare `map` orientation reuses the `investigate` scheduled scan; it is
printed, never saved. Controls and field details are in [history](history.md).

Historical output is one JSON envelope. `scope` records the scanned selection;
`omissions` records missing rows/inputs; `detail` records display clipping; `next`
provides continuations. SQL runs before output paging, but input scan/text limits
still apply. Non-graph derived history data is invocation-local.
