# Validation

Validated 2026-11-11 on Fedora Linux 44 (KDE), Python 3.14.10, mise 2026.11.2.
Executed results are below; the CI jobs encode the planned cross-platform matrix.

## Gate

```text
$ python3 scripts/validate.py
validate: ok (6 skills)
```

## Results

| Criterion | Result | Evidence |
| --- | --- | --- |
| C1 tree and frontmatter | PASS | `scripts/validate.py` checks all six `plugins/<name>/skills/<name>/SKILL.md` files, names, and descriptions. |
| C2 Pi paths | PASS | `package.json` `pi.skills` is `./plugins/*/skills/*`; the validator resolves exactly six skill dirs. |
| C3 Claude manifests | PASS | Marketplace lists six resolving sources; every plugin name and version matches `VERSION`; MIT license present. |
| C4 copy fidelity | PASS | Six intentional-diff summaries in `docs/import.md`; raw diffs in `.agents/artifacts/import/`. No unexplained differences. |
| C5 local tests | PASS | Commands and counts below; remember's full matrix is planned CI coverage. |
| C6 Pi smoke | PASS | Isolated local-path install discovers six skills; a shipped script runs from a scratch project; an isolated git-source install and update through a temporary dumb-HTTP remote also pass. |
| C7 Claude smoke | PASS | Isolated scratch copy installed `untangle@handtools` 0.0.3, then updated to 0.0.4 after a version bump. |
| C8 hygiene | PASS | Validator rejects `.git`, `.agents`, state, caches, bytecode, env/secret files, including force-committed ones; untracked gitignored paths are skipped so a dirty local tree does not fail, and a non-git checkout stays strict. `remember/settings.json` is allowed and documented. |
| C9 docs ownership | PASS | Root `README.md` owns install/update; per-skill install sections point to root. `workflows-as-skills` has no README. |
| C10 provenance | PASS | Source remotes/HEADs, remember's dirty patch SHA-256, and untracked hashes are in `docs/import.md`. |
| C11 design artifact | PASS | `.agents/artifacts/monorepo-design.md` records the tree, manifests, mapping, exclusions, versions, and validation plan; MIT decision recorded. |
| C12 install cutover | PASS | Pi package installed and six old symlinks removed; Claude marketplace re-pointed at the local checkout, all six plugins installed, and the old Claude skill symlink removed. |

## C5 executed tests

| Skill | Command | Result |
| --- | --- | --- |
| `untangle` | `mise run check` | ruff clean; 52 tests passed |
| `semantic-instructions` | `python3 -m unittest discover -s tests -v` | 10 tests passed |
| `workflows-as-skills` | `python3 -m unittest discover -s tests -v` | 62 tests passed |
| `simple-by-design` | `mise run check` | ruff clean; build compileall; 56 tests passed |
| `foundation` | `mise run lint`, `mise run test`, `mise run build` | ruff clean; 21 tests passed; compileall clean |
| `remember` | `python -m pip install -r requirements.txt`, then `python -m unittest discover -s tests -v` in a validation venv | requirements installed; 357 tests passed |

Raw logs are under `.agents/artifacts/validation/` (untracked).

## C6 Pi smoke

### Local-path install

Used a temporary `HOME` and `PI_CODING_AGENT_DIR` with an empty
`~/.agents/skills/`:

```text
pi install /home/joshsimon/Projects/handtools   # exit 0
pi list                                         # reports the package
```

Pi's package resolver returned exactly these six enabled skills under
`handtools/plugins/<name>/skills/<name>/`: `untangle`,
`semantic-instructions`, `workflows-as-skills`, `simple-by-design`,
`foundation`, `remember`.

A shipped script ran from a separate scratch project:

```text
$ python3 /home/joshsimon/Projects/handtools/plugins/simple-by-design/skills/simple-by-design/scripts/sbd.py
No current run. Start: python3 .../sbd.py --root /tmp/handtools-script... --request '<complete request>'
```

It created no files. The script resolves its own reference paths from the new
location.

### Git-source install and update

A temporary bare remote was served with the dumb HTTP protocol. In a separate
temporary `HOME` and `PI_CODING_AGENT_DIR`:

```text
pi install git:http://127.0.0.1:19418/sij0sh/handtools.git   # exit 0
pi list                                                       # reports the git source
```

Pi cloned to `~/.pi/agent/git/127.0.0.1/sij0sh/handtools`; its resolver returned
the same six enabled skills under that cache. `pi update --extensions` reported
up to date at the original commit. A temporary commit was pushed to the bare
remote, `git update-server-info` was refreshed, and the next
`pi update --extensions` fetched it (`5d46ce9 -> 2f2ff14`) and checked out the
new file.

## C7 Claude install and update smoke

Used a temporary `HOME`, `CLAUDE_CONFIG_DIR`, and a scratch copy of the monorepo:

```text
claude plugin marketplace add <scratch>/handtools --json   # ok
claude plugin install untangle@handtools --json            # untangle 0.0.3
# bump scratch VERSION and plugin.json.version to 0.0.4
claude plugin marketplace update handtools --json          # ok
claude plugin update untangle@handtools --json             # 0.0.3 -> 0.0.4
```

The installed cache contained `skills/untangle/SKILL.md`; `plugin list` reported
0.0.4 after the update.

## C12 user-level install cutover

Executed on the real user configuration after C1-C11 passed.

Pi:

```text
pi install /home/joshsimon/Projects/handtools   # exit 0
pi list                                         # ../../Projects/handtools -> /home/joshsimon/Projects/handtools
```

The package resolver returned the six package skills under
`/home/joshsimon/Projects/handtools/plugins/<name>/skills/<name>/` and no
top-level copies of those six names. The six symlinks in `~/.agents/skills/`
were removed; the unrelated `readme` symlink remains.

Claude:

```text
claude plugin marketplace remove handtools --json          # ok
claude plugin marketplace add /home/joshsimon/Projects/handtools --json  # ok
claude plugin install <name>@handtools --json              # ok, six times
```

`claude plugin list --json` reports exactly the six plugins at 0.0.3, 0.0.4,
0.0.8, 0.1.4, 0.0.1 and 0.5.20. Their cache contains the six
`skills/<name>/SKILL.md` files. The old `~/.claude/skills/simple-by-design`
symlink was removed; `readme` and `synced/` remain. The installed
simple-by-design script ran from a scratch directory and created no files.

The pre-existing marketplace named `handtools` pointed at
`github.com/sij0sh/handtools`, an older single-plugin repository. It was removed
from the user configuration and replaced by a `directory` source at the local
checkout. The old marketplace clone was backed up first, and the stale
`handtools/handtools` plugin cache was removed. Cutover evidence and the backup
are under `.agents/artifacts/cutover/` (untracked).

`claude plugin validate . --json` succeeds with warnings only (missing
marketplace/plugin descriptions, author and icon).

## Planned CI coverage

CI runs the local suites plus:

- untangle on Python 3.9;
- semantic-instructions and workflows-as-skills on Python 3.11 and 3.13;
- remember on Ubuntu, macOS, and Windows with Python 3.11 and 3.13;
- mise tasks for untangle, foundation, and simple-by-design;
- `scripts/validate.py`.

Remember's local run covers one platform and one Python version; the matrix above
is planned until CI results are appended.

## Pending

None. All C1-C12 criteria pass. The CI matrix remains planned coverage until CI
results are appended.
