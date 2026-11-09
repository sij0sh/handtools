# Implementation and validation

Release 0.1.1 · 9 November 2026

Implements v0.1.1 M1 (reconnaissance contract, G5 D1-D18): evidence-backed recon records in
`skills/_engine/recon/`, versioned `record.accepted` journal envelopes with reducers, bounded read-only
collectors, snapshot refresh and invalidation, remember projections, and foundation/untangle integration.
Design: `.agents/artifacts/v011.md`. Comparison report: `.agents/artifacts/v011-m1-report.md`.

## Validation

| Suite | Tests | Result |
|---|---:|---|
| Bundle guards | 18 | OK |
| Engine, planning, events, recon | 42 | OK |
| Build-skills | 33 | OK |
| Simple-by-design | 50 | OK |
| Foundation | 26 | OK |
| Untangle resume | 3 | OK |
| Remember (including workflow SQL views and recon projections) | 343 | FAILED (failures=8) |

All new and changed workflow suites pass. The eight Remember failures are environment-only and reproduce
without this release's changes. Optional tree-sitter packages are unavailable; installing the pinned
requirements was attempted but no package versions could be retrieved here. These failures are not
represented as passes.

## Existing environment failures

- test_rust_calls_follow_pub_use_and_typed_receivers (test_graph.GraphTests.test_rust_calls_follow_pub_use_and_typed_receivers)
- test_rust_calls_through_use_module_paths_and_self (test_graph.GraphTests.test_rust_calls_through_use_module_paths_and_self)
- test_rust_cfg_test_modules_are_tests (test_graph_features.FeatureTests.test_rust_cfg_test_modules_are_tests)
- test_type_only_imports_are_marked (test_graph_features.FeatureTests.test_type_only_imports_are_marked)
- test_typescript_calls_follow_imports_reexports_and_this (test_graph.GraphTests.test_typescript_calls_follow_imports_reexports_and_this)
- test_typescript_typed_receivers_and_constructors (test_graph.GraphTests.test_typescript_typed_receivers_and_constructors)
- test_typescript_unique_import_binding_resolves_through_barrel (test_graph.GraphTests.test_typescript_unique_import_binding_resolves_through_barrel)
- test_tiny_budget_keeps_views_and_one_delivery_ref (test_investigate.InvestigateTests.test_tiny_budget_keeps_views_and_one_delivery_ref)

## Intentional boundaries

- Recon collectors are read-only and bounded. They recognize Python, SQL, YAML and JSON; other languages
  are reported as unsupported scope. The comparison report measures contract mechanics, not the discovery
  quality of an independent agent; that evaluation is still open.
- Transcript recon receipts are recognized as non-authoritative evidence. Exact transcript replay requires
  explicit sources, expected revision and known head; an observed prefix cannot prove the latest receipt was
  retained. No automatic backend failover is performed.
- Recon freshness pins recorder-hashed evidence. Changed records and their dependents go stale; existing
  conclusions are not silently reused.
- Committed ADRs and generated audit/report snapshots remain files for sharing. Builder design/review
  bookkeeping is stored in the journal; draft, backup and application bytes remain recovery files.
- The journal retains stage-state snapshots per event. Domain checks remain in adapters; it does not infer
  decisions from ordinary assistant text or execute effects during replay.
- Project identity remains path-based for compatibility. Move state explicitly when relocating a checkout.
- Multi-file writes require reconciliation after interruption; they are not a filesystem transaction.
- build-skills cannot yet revise bundle skills (G5 D18), so foundation, untangle and remember changes were
  direct edits. Generator support is M4.
- This ZIP is a source distribution. It does not install skills into the current ChatGPT account.

See README.md for commands and docs/engine-plan.md for the original planning source.
