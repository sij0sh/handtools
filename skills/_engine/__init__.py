"""The one workflow engine for handtools skills. Not a skill: it has no SKILL.md.

  storage  -> none      per-user state root, project key, state dirs, JSON, lock
  cli      -> none      quoting, rerun command, stdin payload, error printing
  flow     -> storage   single-run commands; takes the skill's steps module
  sessions -> storage   multi-session registry (sN)

A launcher finds this folder by walking up from its own path to the first ancestor holding
_engine/__init__.py: a vendored <skill>/scripts/_engine/ (copied by build-skills) or the
handtools skills/_engine/. Never edit a vendored copy; build-skills refreshes it.
"""
