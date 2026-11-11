#!/usr/bin/env python3
"""Validate the handtools monorepo manifests, layout, and hygiene."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "untangle",
    "semantic-instructions",
    "workflows-as-skills",
    "simple-by-design",
    "foundation",
    "remember",
)
FORBIDDEN_DIRS = {
    ".agents",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "state",
}
FORBIDDEN_FILES = {
    ".env",
    "credentials.json",
    "id_rsa",
    "mise.local.toml",
    "settings.local.json",
}
SECRET_SUFFIXES = {".key", ".pem", ".pyc", ".pyo"}

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        fail(f"missing {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
    return {}


def check_package() -> None:
    package = load_json(ROOT / "package.json")
    if package.get("name") != "handtools":
        fail("package.json name must be handtools")
    if package.get("license") != "MIT":
        fail("package.json license must be MIT")
    patterns = package.get("pi", {}).get("skills")
    if patterns != ["./plugins/*/skills/*"]:
        fail('package.json pi.skills must be ["./plugins/*/skills/*"]')
        return

    matched = set()
    for pattern in patterns:
        for path in ROOT.glob(pattern.removeprefix("./")):
            if path.is_dir() and (path / "SKILL.md").is_file():
                matched.add(path.resolve())
    expected = {(ROOT / "plugins" / name / "skills" / name).resolve() for name in SKILLS}
    if matched != expected:
        missing = sorted(str(p.relative_to(ROOT)) for p in expected - matched)
        extra = sorted(str(p.relative_to(ROOT)) for p in matched - expected)
        fail(f"pi.skills mismatch: missing={missing} extra={extra}")


def check_frontmatter(name: str, skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        fail(f"missing {skill_md.relative_to(ROOT)}")
        return
    text = skill_md.read_text()
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        fail(f"{skill_md.relative_to(ROOT)} has no frontmatter")
        return
    block = text[4 : text.index("\n---\n", 4)]
    values = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    if values.get("name") != name:
        fail(f"{skill_md.relative_to(ROOT)} name must be {name}")
    if not values.get("description"):
        fail(f"{skill_md.relative_to(ROOT)} description is empty")


def check_plugins() -> None:
    marketplace = load_json(ROOT / ".claude-plugin" / "marketplace.json")
    if marketplace.get("name") != "handtools":
        fail("marketplace name must be handtools")
    entries = marketplace.get("plugins", [])
    listed = [entry.get("name") for entry in entries]
    if sorted(listed) != sorted(SKILLS):
        fail(f"marketplace plugins must be exactly {list(SKILLS)}")
    for entry in entries:
        name = entry.get("name")
        source = entry.get("source")
        if name not in SKILLS:
            continue
        if not isinstance(source, str) or not source.startswith("./plugins/"):
            fail(f"{name}: marketplace source must be ./plugins/{name}")
            continue
        plugin_dir = (ROOT / source).resolve()
        plugin = load_json(plugin_dir / ".claude-plugin" / "plugin.json")
        version_file = ROOT / "plugins" / name / "skills" / name / "VERSION"
        if not version_file.is_file():
            fail(f"{name}: missing VERSION")
            continue
        version = version_file.read_text().strip()
        if plugin.get("name") != name:
            fail(f"{name}: plugin.json name mismatch")
        if plugin.get("version") != version:
            fail(f"{name}: plugin version {plugin.get('version')!r} != VERSION {version!r}")
        if plugin.get("license") != "MIT":
            fail(f"{name}: plugin.json license must be MIT")
        check_frontmatter(name, ROOT / "plugins" / name / "skills" / name)


def git_ignored(rels: list[str]) -> set[str]:
    """Ignore rules for untracked paths, so a dirty tree does not fail.

    `git check-ignore` reports -- and this skips -- only ignored paths that are
    not tracked, so a committed cache or secret is still an error.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "--stdin"],
            input="\n".join(rels),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if proc.returncode not in (0, 1):
        return set()
    return {line for line in proc.stdout.splitlines() if line}


def check_hygiene() -> None:
    entries = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in {".git", ".agents"}:
            continue
        entries.append((path, rel))
    ignored = git_ignored([str(rel) for _, rel in entries])
    for path, rel in entries:
        if str(rel) in ignored:
            continue
        if path.is_dir() and path.name in FORBIDDEN_DIRS:
            fail(f"forbidden directory: {rel}")
        if path.is_file():
            if path.name in FORBIDDEN_FILES or path.suffix in SECRET_SUFFIXES:
                fail(f"forbidden file: {rel}")
            if path.name.startswith(".env.") and path.name != ".env.example":
                fail(f"forbidden file: {rel}")
            if rel.parts[0] == "plugins" and path.name == "renovate.json":
                fail(f"nested Renovate config: {rel}")
            if rel.parts[0] == "plugins" and path.name == "dependabot.yml":
                fail(f"nested Dependabot config: {rel}")
    if not (ROOT / "LICENSE").is_file() or "MIT License" not in (ROOT / "LICENSE").read_text():
        fail("LICENSE must contain the MIT license")
    for doc in ("docs/import.md", "docs/validation.md"):
        path = ROOT / doc
        if not path.is_file() or not path.read_text().strip():
            fail(f"missing or empty {doc}")


def main() -> int:
    check_package()
    check_plugins()
    check_hygiene()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"validate: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"validate: ok ({len(SKILLS)} skills)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
