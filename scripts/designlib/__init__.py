"""simple-by-design loop internals. Allowed imports (checked by tests):

  flow     -> storage, sessions, record, config, steps
  steps    -> sessions, record
  sessions -> record, storage
  record   -> storage
  config, storage -> none
"""
