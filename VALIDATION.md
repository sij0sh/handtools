# Implementation and validation

Release 0.1.0 · 9 November 2026

Implemented shared non-skill planning/policy ownership, journal-backed workflow state with legacy
imports, exact transcript receipt replay pilot, searchable workflow SQL views, and aligned authoring
and standalone workflow generation. Builder review now accepts a hashed draft before separate apply
and verify stages. Application intent is durable; drift, changed backups/drafts, symlink targets,
partial writes, stale revisions and conflicting retries are checked. Design revisions retain history.

## Validation

| Suite | Tests | Result |
|---|---:|---|
| Bundle guards | 16 | OK (skipped=1) |
| Engine, planning, event replay | 24 | OK |
| Build-skills and recovery | 33 | OK |
| Simple-by-design | 50 | OK |
| Foundation | 23 | OK |
| Untangle resume | 1 | OK |
| Remember (including workflow SQL views) | 342 | FAILED (failures=9) |

All new tests and changed workflow suites pass. Bundle checks skip one release-tag comparison because
the uploaded archive contains no Git release history. Source compilation also passes.

Independent forward testing created a staged skill through the builder and ran it with only its
vendored runtime, empty PYTHONPATH, and no bundle access. Resume, blocked planning and failed-verification
gates behaved as expected. Dedicated tests cover interrupted application and command retry identity.

## Existing environment failures

The nine Remember failures below reproduce on the unmodified supplied bundle in this same environment.
Optional tree-sitter packages are unavailable; installing the pinned requirements was attempted but
no package versions could be retrieved here. The remaining baseline failure includes truncated Zstandard
capture handling with the installed decoder. These failures have not been represented as passes.

- test_rust_calls_follow_pub_use_and_typed_receivers (test_graph.GraphTests.test_rust_calls_follow_pub_use_and_typed_receivers)
- test_rust_calls_through_use_module_paths_and_self (test_graph.GraphTests.test_rust_calls_through_use_module_paths_and_self)
- test_rust_cfg_test_modules_are_tests (test_graph_features.FeatureTests.test_rust_cfg_test_modules_are_tests)
- test_tiny_budget_keeps_views_and_one_delivery_ref (test_investigate.InvestigateTests.test_tiny_budget_keeps_views_and_one_delivery_ref)
- test_truncated_artifact_reports_a_decompression_gap (test_dsh.DshTests.test_truncated_artifact_reports_a_decompression_gap)
- test_type_only_imports_are_marked (test_graph_features.FeatureTests.test_type_only_imports_are_marked)
- test_typescript_calls_follow_imports_reexports_and_this (test_graph.GraphTests.test_typescript_calls_follow_imports_reexports_and_this)
- test_typescript_typed_receivers_and_constructors (test_graph.GraphTests.test_typescript_typed_receivers_and_constructors)
- test_typescript_unique_import_binding_resolves_through_barrel (test_graph.GraphTests.test_typescript_unique_import_binding_resolves_through_barrel)

## Intentional boundaries

- Production workflows use the transactional journal. Transcript-only operation is an explicit plan-only
  experiment with synthetic Codex/Claude Code/pi capture fixtures, not verified live retention guarantees.
- Exact transcript replay requires explicit sources, expected revision and known head. An observed prefix
  cannot prove the latest receipt was retained. No automatic backend failover is performed.
- Committed ADRs and generated audit/report snapshots remain files for sharing. Builder design/review
  bookkeeping is stored in the journal; draft, backup and application bytes remain recovery files.
- The journal currently retains stage-state snapshots per event. Domain checks remain in adapters;
  it does not infer decisions from ordinary assistant text or execute effects during replay.
- Project identity remains path-based for compatibility. Move state explicitly when relocating a checkout.
- Legacy build runs missing a ready plan stop before mutation; preserve drafts/backups and restart.
- Multi-file writes require reconciliation after interruption; they are not a filesystem transaction.
- This ZIP is a source distribution. It does not install skills into the current ChatGPT account.

See README.md for commands and docs/engine-plan.md for the original planning source.
