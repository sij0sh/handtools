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
recon/ is the shared reconnaissance package; it declares its own graph in recon/__init__.py.
"""
