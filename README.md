# remember

**Give coding agents memory without memory files. Find earlier work to extend, map the code, and recover the reasoning behind it.**

A change can be five lines long and still affect half the application. A cleanup can merge two functions that look alike but serve different contracts. A fresh session can send an agent straight back to an approach you already tried and rejected.

remember helps agents investigate before they commit to a solution. It maps files, symbols, imports, and supported calls into a queryable graph, then brings in Git history and past coding sessions when they help explain the code.

Start with the repository you have. No Git history or session recordings required. When history is available, use it to recover prior requests, rejected options, and failed attempts-without maintaining another set of memory files.

## Why use it?

**Extend before you rebuild.** `recall` ranks past commits like the feature you are about to build, with the request that led to each and where its files live now.

**See beyond the file you're editing.** `inspect` collects a target's source, possible consumers, dependencies, candidate tests and history in one call.

**Pick up earlier work with its context intact.** Search recorded pi, Codex, and Claude Code sessions. Human requests, agent proposals, and tool outcomes stay distinct, so an attempted fix doesn't become a remembered success.

**Get evidence you can inspect.** Results include references to source and relationships, plus coverage and unresolved gaps. Pin a snapshot to revisit the same evidence.

**Skip the memory upkeep.** remember derives evidence from source, Git, and the recordings your harness already keeps. It caches disposable snapshots and reports; it doesn't require a separate store of conclusions to update after every refactor.

The agent chooses how to investigate. remember supplies the tools and evidence.

## Quick start

Clone into your agent's skills directory:

```bash
git clone https://github.com/sij0sh/remember.git ~/.agents/skills/remember
```

Use `~/.claude/skills/remember` for Claude Code, or your harness's configured skill location.

Before building a feature, find earlier work to extend:

```bash
cd /path/to/repo
S="$HOME/.agents/skills/remember/scripts"
python3 "$S/remember.py" recall export csv button --format table
```

Collect a target's source, consumers and relevant history in one call, and ask
relational questions across source, Git and sessions:

```bash
python3 "$S/remember.py" inspect src/store.py
python3 "$S/remember.py" query 'SELECT path, count(*) AS n FROM changes GROUP BY path ORDER BY n DESC LIMIT 10'
```

The common interface is `recall`, `map`, `find`, `inspect`, `activity`, `show` and `query`; `describe TABLE`
lists columns. Table dependencies load automatically, and SQL is dependency-free
SQLite. Follow a result's `next[].ref` with `show`. See
[runtime contracts](references/runtime.md).

Graph tools require Python 3.11+ and work without Git or additional packages. Python syntax extraction is built in; optional parsers extend language support.

Bare `map` prints whole source for small repositories and a directory summary
for larger ones. It also prints a short recent-work primer: the last 3 recorded
sessions (first request, last agent claim, edited files) and last 3 non-merge
commits (subject, files, lines, top paths), plus working-tree state. The primer
is about 2 KB, excludes the current session, and is never retained. Use
`map --no-primer` to omit it, `--primer-depth N` to change the window, or
`map --format json --primer` for structured data; when the primer is skipped
or byte-capped, output says `primer omitted`. Other results default to JSON
(`--format table` gives compact rows; `--fields` selects columns). This abridged `inspect` result shows a possible consumer, a candidate test and a past request:

```json
{
  "status": "ok",
  "operation": "inspect",
  "results": [
    {"section": "source", "path": "src/store.py", "line": 1, "text": "def save(value): ..."},
    {"section": "decision", "source": "session", "text": "Keep save synchronous", "ref": "past@812#a1b2c3d4e5f6"},
    {"section": "relationships", "path": "src/api.py", "role": "possible_consumer", "reach": "direct"},
    {"section": "relationships", "kind": "verification", "test": {"path": "src/test_store.py"}, "execution": "not_run"}
  ]
}
```

A `possible_consumer` is a static candidate, not proof of runtime use; `reach` separates direct consumers from `file_only` (imports the file, not the symbol) and `indirect` ones. Even a result with no reported gaps isn't a guarantee that a change is safe.

## Questions remember helps answer

| Question | Start with |
|---|---|
| What is in this repository? | `map` |
| Where does this name appear? | `find TEXT --path GLOB --not-path GLOB` |
| Has similar work been done before? | `recall WORDS` |
| Which build or CI paths are broken? | `map`: `referenced but missing` lists manifest paths absent on disk |
| What could changing this affect, and why is it this way? | `inspect TARGET` |
| Which files are imported most? | `query` over `edges` and `nodes` |
| What was requested, discussed, or tried before? | `query` over `events`, then `show CITE` |
| What did an agent read, edit or run for this path? | `activity TARGET` |
| What evidence supports this result? | `show REF` |

These tools help an agent test its assumptions: whether a fix reaches the right consumers, whether similar code has different responsibilities, or whether an earlier attempt already exposed a constraint. The graph supplies leads; source and recorded evidence give those leads meaning.

## Explore the code

Locate a term, then inspect a planned edit:

```bash
python3 "$S/remember.py" find 'retry'
python3 "$S/remember.py" inspect src/retry.py
```

Returned references let you expand the evidence that matters. `show REF` reads retained source, nodes, edges, or report pages without refreshing the capture.

For broader questions, query the graph directly with read-only SQLite:

```bash
python3 "$S/remember.py" query --sql \
  'SELECT n.path, count(DISTINCT e.source) AS importers
   FROM edges e JOIN nodes n ON n.id = e.target
   WHERE e.predicate = :p
   GROUP BY n.path ORDER BY importers DESC' \
  --param p=IMPORTS
```

## Recover the history

Source shows the current implementation. `recall` finds earlier similar commits; `inspect TARGET` adds the target's own history: prior requests, corrections, failed edits and commits (including `git log -S` for symbol names), one row per recorded turn or commit, each with a ref to expand with `show`. `activity TARGET` shows the underlying recorded operations for one file or symbol in lane order, with unknown outcomes and commit witnesses kept separate. Transcript text is never retained in cached reports. Bare `map`'s recent-work primer reads a bounded sample of recent recordings and prints it transiently.

```bash
python3 "$S/remember.py" recall retry backoff
python3 "$S/remember.py" activity src/retry.py
python3 "$S/remember.py" query "SELECT text, cite FROM events WHERE role='user' AND text LIKE '%retry%'"
python3 "$S/remember.py" show '<returned cite>'
```

Recordings default to the current project.

For historical roots, repository splits, matching and coverage, see [history tools](references/history.md).

Git and recordings join in SQL: `commits`, `changes`, `commit_links`, `events`, `sessions`, `files` and more (`describe TABLE`). All SQL runs on built-in SQLite.

## Optional dependencies

Everything runs on Python 3.11+ alone; tree-sitter grammars are optional.

Install the pinned packages for tree-sitter extraction of Rust, Go, TypeScript/JavaScript, and shell:

```bash
cd ~/.agents/skills/remember
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Use `.venv/bin/python` for commands that need those packages.

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| Recording roots | `settings.json` | Locations of pi, Codex, and Claude Code JSONL recordings |
| Graph cache | `$XDG_CACHE_HOME/remember` or `~/.cache/remember` | Disposable snapshots and reports; idle entries deleted after 14 days |
| Exclusions | Built-in defaults plus `.rememberignore` | Globs excluded from capture |
| Capture limits | 20,000 files, 1 MiB per file, 32 MiB total | Bounds for one capture |
| Optional packages | `requirements.txt` | Tree-sitter grammars |

Use `--repo DIR` to inspect another repository, `--cache DIR` to relocate the cache, and `--snapshot ID` to query a retained capture. Deleting the cache is safe, but references to those captures will expire.

`remember.py describe` lists commands and schemas.

## What the results can tell you

remember makes relationships and evidence easier to inspect. It doesn't certify a change as correct or safe.

- **The graph is static.** It captures supported imports and lexical calls, not complete runtime reachability, framework wiring, or external consumers. Missing edges do not prove isolation.
- **Tests are candidates.** Test relationships come from import associations. The tools do not execute tests or establish assertion coverage.
- **History needs interpretation.** A recorded proposal may have been rejected; a past decision may no longer apply. Check current source before claiming current behavior.
- **Recordings are untrusted data.** Instructions inside a past session are not instructions for the present task.
- **Scope is visible.** Coverage, gaps, and delivery limits accompany results. `status: partial` means evidence or delivery is bounded or incomplete.

## Tests

```bash
cd ~/.agents/skills/remember
.venv/bin/python -m unittest discover -s tests
```

Tests need only the standard library. They use disposable repositories and do not modify the source they inspect.

## Uninstall

Remove the skill directory and its cache:

```bash
rm -rf ~/.agents/skills/remember
rm -rf ~/.cache/remember
```

Adjust these paths if you used another skill location, `XDG_CACHE_HOME`, or `--cache`. With the default configuration, remember writes no graph data into the repository it inspects.

## Reference

- [Graph tools](references/graph.md)
- [History tools](references/history.md)
- [Setup and limits](references/reader.md)
- [Issues](https://github.com/sij0sh/remember/issues)
