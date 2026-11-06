# Greenfield defaults

Goal: a clone runs `mise install`, `mise run setup`, `mise run dev`, `mise run test`, and CI runs the same tasks.

Day one (propose when the gap is missing):

- `mise.toml`: pinned runtime versions (no `latest`), `[settings] lockfile = true`, tasks `setup`, `dev`, `test`, `lint`, `build`. Create an empty `mise.lock` so mise fills it, and commit it. Git-ignore `mise.local.toml`.
- `compose.yaml` only when the app needs local services (Postgres, Redis).
- CI workflow that installs via mise and runs the mise tasks on pull requests.
- Migrations from the chosen framework's tool, only once a database is chosen.
- `docs/architecture.md` with a Mermaid diagram; `docs/adr/0001-*.md` recording the stack choice.
- `.gitignore` covering `.env*` except `.env.example`; `.env.example` lists variables without values.
- `renovate.json` once there is a remote host and CI to validate update PRs.

Only when a deploy target is chosen: OpenTofu (default) or Pulumi (team prefers general-purpose languages), with remote state and reviewed plans.

Defer unless a stated need demands it: Kubernetes, Helm, service meshes, GitOps controllers, platform portals, Dev Containers, OpenTelemetry, policy-as-code. Start as a modular monolith with one deployment path.
