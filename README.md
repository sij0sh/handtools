# handtools

Six agent skills, one source each, packaged for Pi and Claude Code.

| Skill | Purpose |
| --- | --- |
| `untangle` | Bounded, resumable complexity audit; recommends only. |
| `semantic-instructions` | Frame, compose, and challenge instructions for agents. |
| `workflows-as-skills` | Design workflows that are usable as skills. |
| `simple-by-design` | Settle consequential design choices before implementation. |
| `foundation` | Audit, plan, and bootstrap a project foundation. |
| `remember` | Evidence-backed memory from source, Git, and session recordings. |

## Install

### Pi

```sh
pi install git:github.com/sij0sh/handtools
```

For local development:

```sh
pi install ./handtools
# or run once without installing
pi -e ./handtools
```

The package exposes `./plugins/*/skills/*`; all six skills install together.
Update with `pi update --extensions`.

### Claude Code

```sh
/plugin marketplace add sij0sh/handtools
/plugin install untangle@handtools
```

Install any or all of `untangle`, `semantic-instructions`, `workflows-as-skills`,
`simple-by-design`, `foundation`, and `remember` from the `handtools`
marketplace. Each plugin is independently versioned.

## Layout

```text
plugins/<name>/.claude-plugin/plugin.json   thin Claude wrapper
plugins/<name>/skills/<name>/               full skill source and tests
scripts/validate.py                         manifest and hygiene checks
docs/import.md                              source provenance
docs/validation.md                          executed validation results
```

Root `package.json` owns Pi discovery. Root `.claude-plugin/marketplace.json`
owns Claude discovery. There is no custom installer or update engine.

## Development

```sh
python3 scripts/validate.py
cd plugins/untangle/skills/untangle && mise run check
cd plugins/semantic-instructions/skills/semantic-instructions && python3 -m unittest discover -s tests -v
```

See `docs/validation.md` for the full validation plan and results.

## License

MIT. See `LICENSE`.
