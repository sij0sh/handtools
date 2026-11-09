"""Shared runtime, no skill entry point. Allowed local imports:
  planning -> none
  events -> planning
  recordings -> events
  storage -> events
  cli -> none
  flow -> storage, planning
  sessions -> storage
  effects -> storage
  engine -> none
recon/ (shared reconnaissance) and audit/ (shared audit bookkeeping and check packs) declare their own
graphs in their __init__.py.
"""
