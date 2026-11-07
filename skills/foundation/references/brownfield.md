# Brownfield rules

- Existing tools win. A gap is closed with what the repo already uses (asdf, nvm, Make, Dependabot, Terraform); propose replacing a tool only when it blocks a baseline outcome, and say what breaks if you do. mise reads `.tool-versions`, so consolidating there is additive.
- Record in `decisions` what must not change: deploy pipelines, integrations, public interfaces, developer workflows the user names.
- Infra: read `.tf`/state config only. Never run `plan`/`apply`, never touch remote state or production.
- Architecture: reverse-engineer a draft from code and config; mark it `Status: draft, inferred` until the user confirms.
- ADRs: record decisions already visible in the code under one goal such as "Record decisions already in the code", through simple-by-design's `designflow.py record`. Do not invent rationale: leave `rationale` out when it is unknown. Existing Markdown ADRs stay as they are unless the user approves converting them.
- Onboarding: compare README steps with actual config and report mismatches; run them only with approval.
- Changes: one capability per change, each reviewable on its own; never reformat or reorder existing config.
