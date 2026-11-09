"""build-skills internals. Allowed imports (checked by tests/test_bundle.py):

  flow     -> config, prompts, sessions, stages
  stages   -> config, payload, sessions, skill
  prompts  -> config, sessions
  sessions -> config
  skill    -> config
  config, payload -> none

The engine (cli, storage, sessions registry) is handtools' skills/_engine/.
"""
