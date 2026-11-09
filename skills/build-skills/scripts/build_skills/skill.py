"""Inspect, copy, hash, overlay, and check one skill directory."""
import ast
import json
import hashlib
import os
import re
import shutil
from pathlib import Path

from .config import DESCRIPTION_MAX, ENGINE, EXCLUDE_DIRS, TEMPLATE

FRONTMATTER = re.compile(r'\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)', re.S)


def split_skill(skill):
    """Return (frontmatter dict, body text) of <skill>/SKILL.md."""
    path = skill / 'SKILL.md'
    if not path.is_file():
        raise ValueError(f'{path} does not exist.')
    text = path.read_text(encoding='utf-8')
    match = FRONTMATTER.match(text)
    if not match:
        raise ValueError(f'{path} needs YAML frontmatter between --- lines.')
    meta, last = {}, None
    for line in match.group(1).splitlines():
        if line[:1] in (' ', '\t') and last:
            meta[last] = (meta[last] + ' ' + line.strip()).strip()
            continue
        key, sep, value = line.partition(':')
        if sep:
            last = key.strip()
            value = value.strip()
            meta[last] = '' if value in ('>', '|', '>-', '|-') else value.strip('"\'')
    return meta, text[match.end():]


def tree_hash(skill):
    digest = hashlib.sha256()
    for path in skill_files(skill):
        digest.update(path.relative_to(skill).as_posix().encode('utf-8') + b'\0')
        digest.update(path.read_bytes() + b'\0')
    return digest.hexdigest()


def leaves(skill):
    ref = skill / 'references'
    return sorted(p for p in ref.rglob('*') if p.is_file()) if ref.is_dir() else []


def skill_files(skill):
    """Every file in the skill folder except state, caches, and VCS dirs; sorted."""
    found = []
    for top, dirs, files in os.walk(skill):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        found += [Path(top) / name for name in files if not name.endswith('.pyc')]
    return sorted(found)


def copy_skill(src, dest):
    """Copy src's skill files into a fresh dest."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in skill_files(src):
        target = dest / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def overlay(src, target):
    """Make target match src: mirror src's top-level dirs plus references/ and scripts/ exactly,
    and write top-level files except .gitignore (the target keeps its own). Top-level entries src lacks stay."""
    wanted = {p.relative_to(src) for p in skill_files(src)}
    mirrored = {rel.parts[0] for rel in wanted if len(rel.parts) > 1} | {'references', 'scripts'}
    if target.exists():
        for path in skill_files(target):
            rel = path.relative_to(target)
            if len(rel.parts) > 1 and rel.parts[0] in mirrored and rel not in wanted:
                path.unlink()
        for top in mirrored:
            for folder, _, _ in sorted(os.walk(target / top), reverse=True):
                if not os.listdir(folder):
                    os.rmdir(folder)
    for rel in wanted:
        if rel.as_posix() == '.gitignore':
            continue
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, target / rel)


def install_engine(skill, model):
    """Staged model: copy the template (launcher, example steps.py) unless steps.py exists; set MODE and AREA.

    Always replace scripts/_engine/ with a fresh copy of handtools' engine (never edited in place),
    so the skill runs without handtools and every revision picks up engine fixes.
    """
    if not (ENGINE / '__init__.py').is_file():
        raise ValueError(f'engine not found at {ENGINE}; install the handtools bundle.')
    scripts = skill / 'scripts'
    steps = scripts / 'steps.py'
    if not steps.is_file():
        shutil.copytree(TEMPLATE, scripts, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # Launcher is part of the versioned runtime, never leave an obsolete CLI behind.
    shutil.copy2(TEMPLATE / 'workflow.py', scripts / 'workflow.py')
    if (scripts / '_engine').exists():
        shutil.rmtree(scripts / '_engine')
    shutil.copytree(ENGINE, scripts / '_engine', ignore=shutil.ignore_patterns('tests', '__pycache__', '*.pyc'))
    text = steps.read_text(encoding='utf-8')
    text = re.sub(r"^MODE\s*=\s*['\"]\w+['\"]", f"MODE = '{model}'", text, count=1, flags=re.M)
    text = re.sub(r"^AREA\s*=\s*['\"][\w.-]+['\"]", f"AREA = '{skill.name}'", text, count=1, flags=re.M)
    steps.write_text(text, encoding='utf-8')
    # The engine's own distribution.json names what ships (engine_api, event_schema, policy, recon, audit); add the backend.
    meta = json.loads((ENGINE / 'distribution.json').read_text(encoding='utf-8'))
    meta['backend'] = 'journal' if model == 'stateful' else 'none'
    (scripts / '_engine' / 'distribution.json').write_text(json.dumps(meta) + '\n')


def check_files(skill):
    """Structural gates: frontmatter name, description, invocation; every leaf named in SKILL.md or scripts/."""
    if any(p.is_symlink() for p in skill.rglob('*')):
        raise ValueError('skill must not contain symlinks')
    meta, _ = split_skill(skill)
    if meta.get('name') != skill.name:
        raise ValueError(f'{skill}: frontmatter `name` must be `{skill.name}`.')
    description = meta.get('description', '')
    if not description or len(description) > DESCRIPTION_MAX:
        raise ValueError(f'{skill}: frontmatter `description` must be 1-{DESCRIPTION_MAX} characters (one line).')
    if meta.get('disable-model-invocation') not in ('true', 'false'):
        raise ValueError(f'{skill}: frontmatter `disable-model-invocation` must be true or false (default true).')
    texts = [(skill / 'SKILL.md').read_text(encoding='utf-8')]
    texts += [p.read_text(encoding='utf-8', errors='ignore') for p in skill_files(skill)
              if p.relative_to(skill).parts[0] == 'scripts']
    unreferenced = [p.relative_to(skill).as_posix() for p in leaves(skill)
                    if not any(p.relative_to(skill).as_posix() in t or p.name in t for t in texts)]
    if unreferenced:
        raise ValueError(f'{skill}: leaves not named in SKILL.md or scripts/: {", ".join(unreferenced)}.')


def write_codex_policy(skill):
    """Codex reads agents/openai.yaml, not `disable-model-invocation`; keep the two in step."""
    meta, _ = split_skill(skill)
    allow = 'false' if meta.get('disable-model-invocation') == 'true' else 'true'
    path = skill / 'agents' / 'openai.yaml'
    line = f'allow_implicit_invocation: {allow}'
    if not path.is_file():
        path.parent.mkdir(exist_ok=True)
        text = f'policy:\n  {line}\n'
    else:
        text = path.read_text(encoding='utf-8')
        if re.search(r'^\s+allow_implicit_invocation:', text, re.M):
            text = re.sub(r'^(\s+)allow_implicit_invocation:.*$', lambda m: m.group(1) + line, text, count=1, flags=re.M)
        elif re.search(r'^policy:[ \t]*$', text, re.M):
            text = re.sub(r'^policy:[ \t]*$', f'policy:\n  {line}', text, count=1, flags=re.M)
        else:
            text = text.rstrip('\n') + f'\npolicy:\n  {line}\n'
    path.write_text(text, encoding='utf-8')
    return path


def check_prompt(skill):
    """Saved prompt: SKILL.md only, user-invoked."""
    meta, _ = split_skill(skill)
    if meta.get('disable-model-invocation') != 'true':
        raise ValueError(f'{skill}: a saved prompt is user-invoked; set `disable-model-invocation: true`.')
    extra = [d for d in ('scripts', 'references') if (skill / d).exists()]
    if extra:
        raise ValueError(f'{skill}: a saved prompt is SKILL.md only; remove {", ".join(extra)}/.')


def engine_order(steps):
    """The ORDER list literal in steps.py, or None."""
    for node in ast.parse(steps.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == 'ORDER' for t in node.targets):
            try:
                return list(ast.literal_eval(node.value))
            except ValueError:
                return None
    return None


def check_model(skill, model, router, stages=()):
    """Shape matches the declared execution model, router, and design stage names."""
    steps = skill / 'scripts' / 'steps.py'
    found = re.search(r"^MODE\s*=\s*['\"](\w+)['\"]", steps.read_text(encoding='utf-8'), re.M) \
        if steps.is_file() else None
    if not found or found.group(1) != model:
        raise ValueError(f'{skill}: {model} model needs scripts/steps.py with MODE = \'{model}\'.')
    meta, _ = split_skill(skill)
    if meta.get('disable-model-invocation') != 'true':
        raise ValueError('workflow skills are user-invoked only')
    if not re.search(r'^PLANNING\s*=\s*True\b', steps.read_text(), re.M):
        raise ValueError('workflow needs PLANNING = True for shared readiness enforcement')
    order = engine_order(steps)
    if stages and order != list(stages):
        raise ValueError(f'{skill}: steps.py ORDER {order} must match design stages {list(stages)}.')
    if router and not leaves(skill):
        raise ValueError(f'{skill}: router needs at least one leaf under references/.')
