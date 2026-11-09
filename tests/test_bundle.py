"""Bundle-level guards: one source of truth for shared rules, resolvable sibling paths,
one version, schema and validator in step, and Codex/Claude invocation flags in agreement.

Run from the repo root: python3 -m unittest discover -s tests
"""
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'skills'
OWNER = SKILLS / 'simple-by-design'
SHARED = sorted([OWNER / 'references' / n for n in ('defaults.md', 'contract.md', 'instructions.md',
                                                     'decisions.schema.json')]
                + list((OWNER / 'languages').glob('*.md')))
TEXT = {'.md', '.json', '.py', '.txt', '.yaml', '.yml', '.toml'}
SKIP_DIRS = {'.git', '__pycache__', '.venv', 'node_modules', '.pytest_cache', '.ruff_cache'}
SIMILAR = 0.8  # a copied-then-edited rule file still shares most of its text


def tracked_files():
    for top, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (Path(top) == ROOT and d == '.agents')]
        for name in files:
            path = Path(top) / name
            if path.suffix in TEXT:
                yield path


def normalize(text):
    return '\n'.join(line.rstrip() for line in text.strip().splitlines() if line.strip())


def frontmatter(skill):
    text = (skill / 'SKILL.md').read_text(encoding='utf-8')
    match = re.match(r'---\n(.*?)\n---', text, re.S)
    return dict(line.split(':', 1) for line in match.group(1).splitlines() if ':' in line and line[0] != ' ')


def skills():
    return sorted(p for p in SKILLS.iterdir() if (p / 'SKILL.md').is_file())


class SharedRulesTest(unittest.TestCase):
    def test_shared_files_exist(self):
        self.assertGreaterEqual(len(SHARED), 5)
        for path in SHARED:
            self.assertTrue(path.is_file(), path)

    def test_no_copy_of_a_shared_rule_outside_its_owner(self):
        shared = {p: normalize(p.read_text(encoding='utf-8')) for p in SHARED}
        hashes = {hashlib.sha256(t.encode()).hexdigest(): p for p, t in shared.items()}
        for path in tracked_files():
            if OWNER in path.parents or path.name == 'CHANGELOG.md':
                continue
            text = normalize(path.read_text(encoding='utf-8', errors='ignore'))
            rel = path.relative_to(ROOT)
            with self.subTest(file=str(rel)):
                self.assertNotIn(hashlib.sha256(text.encode()).hexdigest(), hashes,
                                 f'{rel} is a copy of a shared rule file; cite it from simple-by-design instead.')
                for owner_path, owner_text in shared.items():
                    if len(text) < 200:
                        continue
                    matcher = difflib.SequenceMatcher(None, text, owner_text, autojunk=False)
                    if matcher.real_quick_ratio() >= SIMILAR and matcher.quick_ratio() >= SIMILAR:
                        self.assertLess(matcher.ratio(), SIMILAR,
                                        f'{rel} looks like an edited copy of {owner_path.relative_to(ROOT)}.')


class SiblingPathsTest(unittest.TestCase):
    SIBLING = re.compile(r'(?:\bS/)?\.\./(build-skills|untangle|foundation|simple-by-design|remember)'
                         r'((?:/[\w.*<>-]+)*)/?')
    OWN = re.compile(r'\bS/((?:scripts|references|languages|assets|templates)(?:/[\w.-]+)*)')

    def test_cited_sibling_and_own_paths_exist(self):
        for skill in skills():
            for path in [skill / 'SKILL.md', *skill.rglob('*.md'), *skill.rglob('*.py')]:
                if any(part in SKIP_DIRS for part in path.parts) or not path.is_file():
                    continue
                text = path.read_text(encoding='utf-8', errors='ignore')
                for match in self.SIBLING.finditer(text):
                    sub = match.group(2).strip('/')
                    if '<' in sub or '*' in sub:
                        sub = sub.split('/')[0] if not ('<' in sub.split('/')[0]) else ''
                    target = SKILLS / match.group(1) / sub
                    with self.subTest(file=str(path.relative_to(ROOT)), cites=match.group(0)):
                        self.assertTrue(target.exists(), f'{target} does not exist')
                if path.name == 'SKILL.md':
                    for match in self.OWN.finditer(text):
                        with self.subTest(file=str(path.relative_to(ROOT)), cites=match.group(0)):
                            self.assertTrue((skill / match.group(1)).exists())

    def test_runtime_lookups_resolve(self):
        sys.path.insert(0, str(SKILLS / 'untangle' / 'scripts'))
        try:
            from workflowlib import ledger
            self.assertEqual(ledger.SIBLING, OWNER)
            self.assertEqual(set(ledger.load_policy()['files']),
                             {p.relative_to(OWNER).as_posix() for p in SHARED if p.suffix == '.md'})
        finally:
            sys.path.pop(0)
            for name in [m for m in sys.modules if m == 'workflowlib' or m.startswith('workflowlib.')]:
                del sys.modules[name]
        self.assertTrue((SKILLS / 'foundation' / 'scripts').is_dir())
        validate = (SKILLS / 'foundation' / 'scripts' / 'validate.py').read_text(encoding='utf-8')
        self.assertIn("parents[2] / 'simple-by-design' / 'scripts'", validate)
        self.assertTrue((OWNER / 'scripts' / 'designlib' / 'record.py').is_file())


class VersionTest(unittest.TestCase):
    def manifests(self):
        def load(rel):
            return json.loads((ROOT / rel).read_text(encoding='utf-8'))
        market = load('.claude-plugin/marketplace.json')
        return {
            '.claude-plugin/plugin.json': load('.claude-plugin/plugin.json')['version'],
            '.claude-plugin/marketplace.json': next(p['version'] for p in market['plugins'] if p['name'] == 'handtools'),
            '.codex-plugin/plugin.json': load('.codex-plugin/plugin.json')['version'],
            'package.json': load('package.json')['version'],
        }

    def test_manifests_match_version(self):
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self.assertRegex(version, r'^\d+\.\d+\.\d+$')
        for rel, found in self.manifests().items():
            with self.subTest(manifest=rel):
                self.assertEqual(found, version)
        self.assertIn(f'## [{version}]', (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'))

    def test_no_per_skill_versions(self):
        for skill in skills():
            self.assertFalse((skill / 'VERSION').exists(), skill)
            self.assertFalse((skill / 'CHANGELOG.md').exists(), skill)

    def test_skill_changes_since_last_release_bump_version(self):
        def git(*args):
            out = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True)
            return out.stdout.strip() if out.returncode == 0 else None
        tag = git('describe', '--tags', '--abbrev=0', '--match', 'v*')
        if not tag:
            self.skipTest('no release tag yet')
        changed = git('diff', '--name-only', tag, '--', 'skills')
        if changed:
            self.assertNotEqual(git('show', f'{tag}:VERSION'), (ROOT / 'VERSION').read_text().strip(),
                                f'skills/ changed since {tag}; bump VERSION and add a CHANGELOG entry.')


class SchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(OWNER / 'scripts'))
        from designlib import record
        cls.record = record
        cls.schema = json.loads((OWNER / 'references' / 'decisions.schema.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(OWNER / 'scripts'))

    def test_schema_matches_validator(self):
        goal, decision = self.schema['$defs']['goal'], self.schema['$defs']['decision']
        r = self.record
        self.assertEqual(goal['required'], r.GOAL_REQUIRED)
        self.assertEqual(set(goal['properties']), set(r.GOAL_REQUIRED + r.GOAL_OPTIONAL))
        self.assertEqual(decision['required'], r.DECISION_REQUIRED)
        self.assertEqual(set(decision['properties']), set(r.DECISION_REQUIRED + r.DECISION_OPTIONAL))
        self.assertEqual(tuple(decision['properties']['status']['enum']), r.STATUSES)
        self.assertEqual(goal['properties']['id']['pattern'], r.GOAL_ID)
        self.assertEqual(decision['properties']['id']['pattern'], r.DECISION_ID)
        self.assertEqual(decision['properties']['after']['items']['pattern'], r.DECISION_REF)
        self.assertEqual(decision['properties']['superseded_by']['pattern'], r.DECISION_REF)
        self.assertEqual(decision['properties']['date']['pattern'], r.DATE)

    def test_committed_records_are_valid(self):
        listed = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '*decisions.json'],
                                capture_output=True, text=True).stdout.split()
        paths = [ROOT / p for p in listed] or [ROOT / '.agents' / 'design' / 'decisions.json']
        for path in paths:
            with self.subTest(record=str(path.relative_to(ROOT))):
                self.record.validate(json.loads(path.read_text(encoding='utf-8')))


class InvocationPolicyTest(unittest.TestCase):
    def test_codex_policy_matches_frontmatter(self):
        for skill in skills():
            disabled = frontmatter(skill).get('disable-model-invocation', '').strip() == 'true'
            yaml = skill / 'agents' / 'openai.yaml'
            with self.subTest(skill=skill.name):
                if not yaml.is_file():
                    self.assertFalse(disabled, 'explicit-only skill needs agents/openai.yaml for Codex')
                    continue
                match = re.search(r'^\s+allow_implicit_invocation:\s*(true|false)\s*$', yaml.read_text(), re.M)
                self.assertIsNotNone(match, 'agents/openai.yaml needs policy.allow_implicit_invocation')
                self.assertEqual(match.group(1) == 'false', disabled)


class CheckScriptTest(unittest.TestCase):
    def git(self, *args, cwd):
        subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, stdin=subprocess.DEVNULL)

    def test_reports_pi_clone_behind_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            origin, work = tmp / 'origin' / 'handtools.git', tmp / 'work'
            env = dict(os.environ, HOME=str(tmp / 'home'), GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@e', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@e')
            run = lambda *a, cwd: subprocess.run(['git', *a], cwd=cwd, check=True, capture_output=True,
                                                 env=env, stdin=subprocess.DEVNULL)
            origin.parent.mkdir(parents=True)
            run('init', '-q', '--bare', '-b', 'main', str(origin), cwd=tmp)
            run('clone', '-q', str(origin), str(work), cwd=tmp)
            (work / 'VERSION').write_text('0.1.0\n')
            run('add', '.', cwd=work)
            run('commit', '-qm', 'one', cwd=work)
            run('push', '-q', 'origin', 'HEAD:main', cwd=work)
            pi = tmp / 'home' / '.pi' / 'agent' / 'git' / 'github.com' / 'sij0sh' / 'handtools'
            run('clone', '-q', str(origin), str(pi), cwd=tmp)
            script = [sys.executable, str(ROOT / 'scripts' / 'check.py')]
            current = subprocess.run(script, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
            self.assertIn('pi:', current.stdout)
            self.assertIn('up to date', current.stdout)
            run('commit', '-q', '--allow-empty', '-m', 'two', cwd=work)
            run('push', '-q', 'origin', 'HEAD:main', cwd=work)
            behind = subprocess.run(script, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
            self.assertEqual(behind.returncode, 1, behind.stdout + behind.stderr)
            self.assertIn('update available, 1 commit(s) behind; run: pi update git:github.com/sij0sh/handtools',
                          behind.stdout)


TEMPLATE = SKILLS / 'build-skills' / 'templates' / 'workflow' / 'scripts' / 'workflowlib'
# Engine files copied verbatim until phase 2 gives them one home (G3/D7); every copy must equal the template's.
COPIES = {
    'storage.py': [SKILLS / 'build-skills' / 'scripts' / 'build_skills', SKILLS / 'foundation' / 'scripts' / 'workflowlib',
                   SKILLS / 'untangle' / 'scripts' / 'workflowlib', OWNER / 'scripts' / 'designlib'],
    'cli.py': [SKILLS / 'build-skills' / 'scripts' / 'build_skills', SKILLS / 'foundation' / 'scripts' / 'workflowlib',
               SKILLS / 'untangle' / 'scripts' / 'workflowlib'],
    'flow.py': [SKILLS / 'foundation' / 'scripts' / 'workflowlib', SKILLS / 'untangle' / 'scripts' / 'workflowlib'],
}


def load_storage():
    import importlib.util
    spec = importlib.util.spec_from_file_location('handtools_storage', TEMPLATE / 'storage.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StateTest(unittest.TestCase):
    """G3: per-user state under one root, one layout, no state inside an installed skill."""

    @classmethod
    def setUpClass(cls):
        cls.storage = load_storage()

    def test_engine_copies_are_identical(self):
        for name, dirs in COPIES.items():
            for folder in dirs:
                with self.subTest(file=str((folder / name).relative_to(ROOT))):
                    self.assertEqual((folder / name).read_bytes(), (TEMPLATE / name).read_bytes(),
                                     f'edit every copy of {name} together (see its docstring)')

    def test_no_state_inside_skills(self):
        for skill in skills():
            self.assertFalse((skill / 'state').exists(), f'{skill.name}/state: state belongs in the state root')

    def test_default_root_is_home_agents_state(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, clear=False) as env:
            env.pop(self.storage.ENV, None)
            with mock.patch.object(Path, 'home', return_value=Path(home)):
                self.assertEqual(self.storage.state_root(), Path(home) / '.agents' / 'state')

    def test_env_overrides_root(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {self.storage.ENV: tmp}):
            self.assertEqual(self.storage.state_root(), Path(tmp).resolve())

    def test_project_key_is_stable_and_per_path(self):
        key = self.storage.project_key
        a, b = Path('/work/my repo').resolve(), Path('/other/my repo').resolve()
        self.assertEqual(key(a), key(a))
        self.assertNotEqual(key(a), key(b))
        self.assertRegex(key(a), r'^my-repo-[0-9a-f]{8}$')

    def test_state_dir_layout_and_project_file(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {self.storage.ENV: tmp}):
            root = Path(tmp).resolve() / 'proj'
            path = self.storage.state_dir('untangle', root)
            self.assertEqual(path, Path(tmp).resolve() / 'untangle' / self.storage.project_key(root))
            self.assertEqual(json.loads((path / 'project.json').read_text()), {'root': str(root)})


if __name__ == '__main__':
    unittest.main()
