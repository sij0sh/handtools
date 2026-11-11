# Import provenance

Imported 2026-11-11 from `git@github.com:sij0sh/<name>.git`.

Each source working tree was read-only during the copy. The source repositories
were not modified, committed, or pushed by the import. The copy is a snapshot:
monorepo history starts fresh, while each source repository keeps its history.

## Sources

| Skill | Source HEAD | Source VERSION | Imported VERSION |
| --- | --- | --- | --- |
| `untangle` | `676a74a3e64db9166337f239ee741f22ce09f11a` | 0.0.2 | 0.0.3 |
| `semantic-instructions` | `b8a756425c6ddd5aae2bdf29de1bb5ace5948e56` | 0.0.3 | 0.0.4 |
| `workflows-as-skills` | `0f31253c4f7ecde72be7f3a44184e879ad60473c` | 0.0.7 | 0.0.8 |
| `simple-by-design` | `071d2003b218fd7d93f4eeecf760f16bcd013dfd` | 0.1.3 | 0.1.4 |
| `foundation` | `6c9522eac2778223f390b79a6aed1b6eb5580c9a` | none | 0.0.1 |
| `remember` | `f382c38914c49c04d9f330d1fb55ca5bf65f18f9` | 0.5.19 | 0.5.20 |

`simple-by-design` was at 0.1.3 when the design was recorded. Its source gained
one commit (`071d200`, stop after DONE) before the copy, so the import carries
0.1.3 and the patch bump produces 0.1.4. The other source versions matched the
design.

## remember dirty snapshot

`remember` had 14 modified tracked files and 4 untracked non-ignored files at
import time. The full tracked diff is `.agents/artifacts/import/remember-dirty.patch`
(untracked, not committed), SHA-256:

```text
5faac491f3d5221a480437d7933be73b4fdbf76b32875f28ff769d5652f96166
```

Modified files: `.gitignore`, `README.md`, `references/history.md`,
`references/reader.md`, `scripts/helper/cite.py`, `scripts/helper/discovery.py`,
`scripts/helper/edit_hunks.py`, `scripts/helper/file_observations.py`,
`scripts/helper/profiles.py`, `scripts/helper/providers.py`,
`scripts/helper/reader.py`, `scripts/helper/recording_scan.py`,
`scripts/helper/records.py`, `settings.json`.

Untracked files and SHA-256:

| File | SHA-256 |
| --- | --- |
| `scripts/helper/zstd.py` | `21ab14f05c8de97acf62b7a85089f938829abaea5268754c391ace39c1ce1b6a` |
| `scripts/profiles/dsh-v1.json` | `a1b3dc0a51458ccd961ce09f3cc5e5e1145e3236115f5a8eab279897d9a2b21b` |
| `tests/fixtures/recordings/dsh-slice1.jsonl` | `3876c73af1a4cbeee4208eb057e6fa5f76d88611fa3dad302cb3bd935912a249` |
| `tests/test_dsh.py` | `32090e25ad294acb1af97648054866129ae1fb11965446748fce02168b726d7d` |

The import includes all 18 files and the current `settings.json` recording
paths. `settings.json` is functional configuration, not a secret.

## Exclusions

- `.git/`
- `.agents/` (tracked design/run history and local ledgers)
- `state/`, `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `*.pyc`, `mise.local.toml`
- per-skill `.github/` and per-skill `renovate.json`; root CI and Renovate own these now

## Fidelity diffs

Raw diffs are under `.agents/artifacts/import/<name>.diff` (untracked). They
compare each source tree against its imported tree with the exclusions above.

| Skill | Intentional differences | Diff files |
| --- | --- | --- |
| `untangle` | `VERSION` bump; install section points at root README | 2 |
| `semantic-instructions` | `VERSION` bump; install section points at root README | 2 |
| `workflows-as-skills` | `VERSION` bump | 1 |
| `simple-by-design` | `VERSION` bump; install section points at root README | 2 |
| `foundation` | `VERSION` added; monorepo note and status refreshed | 2 |
| `remember` | `VERSION` bump; install section points at root README | 2 |

No other content differences were observed. Each plugin wrapper adds
`.claude-plugin/plugin.json` outside the skill directory; that file is not part
of the source diff.

## Version policy

Each skill's `VERSION` is canonical. `plugins/<name>/.claude-plugin/plugin.json`
mirrors it and `scripts/validate.py` fails on drift. The import applies the
required `0.0.1` patch bump.
