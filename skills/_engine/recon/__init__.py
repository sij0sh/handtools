"""Shared reconnaissance: evidence-backed records of a project and its ecosystem. A library with a
command-line front end (cli.py); no SKILL.md, no trigger, never invokes a skill.

Records live in the engine journal (<state root>/recon/<project key>/events.sqlite3), one run per
snapshot (snap-N). Collectors produce candidates only; accepted records come from `record`.

Allowed local imports (checked by tests/test_bundle.py):
  records -> none
  reduce -> records
  sources -> none
  collect -> sources
  query -> records
  store -> records, reduce, sources
  guide -> none
  cli -> collect, guide, query, records, store
"""
