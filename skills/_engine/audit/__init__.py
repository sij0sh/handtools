"""Shared audit bookkeeping: obligations (what to examine), candidates (claims under validation),
evidence references, check packs and budgets. Pure functions over plain dicts kept in a workflow's
run state. A library: no SKILL.md, no trigger, never invokes a skill.

It judges nothing. Each workflow passes its own verdict function when a candidate is settled, so
bug rules (review) and security rules (M3) stay with their workflows. Check packs are data in
packs/*.json.

Allowed local imports (checked by tests/test_bundle.py):
  evidence -> none
  packs -> none
  budgets -> none
  obligations -> evidence, packs
  candidates -> evidence
"""
