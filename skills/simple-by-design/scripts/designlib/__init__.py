"""simple-by-design loop internals. Allowed imports (checked by tests):

  flow     -> storage, sessions, record, config, steps, gitcheck
  steps    -> sessions, record
  sessions -> record, storage
  record   -> storage
  gitcheck -> storage
  config, storage -> none
"""
