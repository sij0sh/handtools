# ADR 0001: one canonical skill copy, two distribution wrappers

## Status

Accepted.

## Context

The six skills were separate repositories. Pi discovers skills from package
paths; Claude Code discovers plugins from a marketplace and skills under a
plugin root. Duplicating instruction sources would let the harnesses drift.

## Decision

- Keep one canonical copy per skill at `plugins/<name>/skills/<name>/`.
- Add a thin `plugins/<name>/.claude-plugin/plugin.json` wrapper for Claude.
- Expose all six to Pi with root `package.json` `pi.skills`.
- Expose all six to Claude with root `.claude-plugin/marketplace.json`.
- Keep per-skill `VERSION`; mirror it in `plugin.json`; validate the mirror.
- Use root CI and Renovate; do not run nested per-skill automation.

## Consequences

Pi installs and updates the suite together. Claude plugins keep independent
versions and can be installed separately. Paths are deeper, and a sync is a
snapshot rather than a history merge. There is no custom installer or update
engine.
