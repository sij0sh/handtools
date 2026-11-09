"""The one statement of how an agent does reconnaissance. Workflow prompts include it; they do not copy it."""
from pathlib import Path

CLI = Path(__file__).resolve().parent / 'cli.py'

CONTRACT = """Reconnaissance establishes what exists and what is unknown; it judges nothing.
Progressive depth: orient (cheap inventory), map (contracts and critical paths the work needs),
deepen (one named gap or question, within budget). Stop at the depth the task needs.
1. `status`: reuse the newest closed snapshot when it is fresh and its depth and roots cover the
   need; when it is stale, `refresh --run snap-N`; when none exists, continue.
2. `orient` and `candidates` (read-only) list files and contract hints. Hints are not facts:
   open the cited lines before recording anything.
3. `start --request-id <new uuid> --depth map` (add `--related label=path` only for repositories
   the user supplied; never fetch or guess others). It prints the run id, snap-N.
4. Record verified facts with `record --run snap-N --expect-revision R --request-id <new uuid>`,
   stdin {"records": [...], "cost": {"files": F, "bytes": B, "commands": []}}; cost counts what you
   read for this batch. R is the revision printed by the previous command (start = 1).
5. `close --run snap-N --expect-revision R --request-id <new uuid>`, then `query summary|contracts|
   gaps|consumers --id X|neighbors --id X --direction downstream --depth 2|evidence --id X|stale`.
Records (ids are <type>:<natural key>, never line numbers):
- contract:<http|queue|schedule|schema|table|file|webhook|sdk>:<channel>, direction inbound|outbound|
  both|internal, producers/consumers: component ids, {"external": "name"} or {"unresolved":
  "consumer of <contract id>"}; optional owner, schema, version, compatibility, ordering, retries,
  idempotency, failure_recovery, migration, retention, authority. Leave unknown fields out.
- component:<repo>/<name> with responsibility, sources, entrypoints, state, commands.
- rel:<relation>:<from>-><to> with relation, from, to (record ids).
- obs:<slug> with claim; inferred patterns and conflicts (conflicts_with) are observations.
- decision:G#/D# only for an answered decision in .agents/design/decisions.json (classified declared).
- gap:<slug> with question, searched, missing, consequence, next_lookup, affected (ids).
Every record has classification observed|configured|declared|inferred|unknown and optional
confidence high|medium|low. Facts cite evidence [{"source": ".", "path": "app/x.py", "lines":
"10-14", "statement": "what these lines show"}]; the recorder hashes the file. depends_on lists
ids a conclusion rests on. A channel published with no subscriber evidence has consumer
{"unresolved": ...} plus a gap, never "no consumers". Configuration alone does not prove runtime
activity. Re-recording an id supersedes it; {"id": X, "drop": true, "reason": "..."} removes it.
Recon completeness never implies review coverage. Never edit project files during recon."""


def prompt(launcher=None):
    cli = launcher or f'python3 {CLI} --root .'
    return CONTRACT + f'\nRecon command: {cli} <command>'
