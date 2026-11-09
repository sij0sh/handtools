"""Bundle-level guards: one source of truth for shared rules, resolvable sibling paths,
one version, schema and validator in step, and Codex/Claude invocation flags in agreement.

Run from the repo root: python3 -m unittest discover -s tests
"""
import ast
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
ENGINE = SKILLS / '_engine'


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


def assert_no_copies(test, owned, owner, fix):
    """No file outside `owner` equals, or is an edited copy of, any file in `owned`."""
    shared = {p: normalize(p.read_text(encoding='utf-8')) for p in owned}
    hashes = {hashlib.sha256(t.encode()).hexdigest(): p for p, t in shared.items()}
    for path in tracked_files():
        if owner in path.parents or path.name == 'CHANGELOG.md':
            continue
        text = normalize(path.read_text(encoding='utf-8', errors='ignore'))
        rel = path.relative_to(ROOT)
        with test.subTest(file=str(rel)):
            test.assertNotIn(hashlib.sha256(text.encode()).hexdigest(), hashes, f'{rel} is a copy; {fix}.')
            for owner_path, owner_text in shared.items():
                if len(text) < 200:
                    continue
                matcher = difflib.SequenceMatcher(None, text, owner_text, autojunk=False)
                if matcher.real_quick_ratio() >= SIMILAR and matcher.quick_ratio() >= SIMILAR:
                    test.assertLess(matcher.ratio(), SIMILAR,
                                    f'{rel} looks like an edited copy of {owner_path.relative_to(ROOT)}; {fix}.')


class SharedRulesTest(unittest.TestCase):
    def test_shared_files_exist(self):
        self.assertGreaterEqual(len(SHARED), 5)
        for path in SHARED:
            self.assertTrue(path.is_file(), path)

    def test_no_copy_of_a_shared_rule_outside_its_owner(self):
        assert_no_copies(self, SHARED, OWNER, 'cite it from simple-by-design instead')


class SiblingPathsTest(unittest.TestCase):
    SIBLING = re.compile(r'(?:\bS/)?\.\./(build-skills|untangle|foundation|simple-by-design|remember|_engine)'
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
        sys.path[:0] = [str(SKILLS / 'untangle' / 'scripts'), str(SKILLS)]
        try:
            from workflowlib import ledger
            self.assertEqual(ledger.SIBLING, OWNER)
            self.assertEqual(set(ledger.load_policy()['files']),
                             {p.relative_to(OWNER).as_posix() for p in SHARED if p.suffix == '.md'})
        finally:
            del sys.path[:2]
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
        sys.path[:0] = [str(OWNER / 'scripts'), str(SKILLS)]  # designlib; _engine
        from designlib import record
        cls.record = record
        cls.schema = json.loads((OWNER / 'references' / 'decisions.schema.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(OWNER / 'scripts'))
        sys.path.remove(str(SKILLS))

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



# Launchers that find the engine by walking up to the first folder holding _engine/ (G4/D2).
LAUNCHERS = [SKILLS / 'simple-by-design' / 'scripts' / 'designflow.py',
             SKILLS / 'foundation' / 'scripts' / 'workflow.py',
             SKILLS / 'untangle' / 'scripts' / 'workflow.py',
             SKILLS / 'build-skills' / 'scripts' / 'build-skills.py',
             SKILLS / 'build-skills' / 'templates' / 'workflow' / 'scripts' / 'workflow.py']
# Packages whose docstring declares their allowed local imports as `mod -> a, b` lines.
GRAPHS = [ENGINE, SKILLS / 'untangle' / 'scripts' / 'workflowlib', SKILLS / 'build-skills' / 'scripts' / 'build_skills']


def declared_graph(package):
    rules = {}
    for line in ast.get_docstring(ast.parse((package / '__init__.py').read_text(encoding='utf-8'))).splitlines():
        if '->' in line:
            left, right = (part.strip() for part in line.split('->'))
            right = right.split('  ')[0].strip()
            for mod in left.split(','):
                rules[mod.strip()] = set() if right == 'none' else {r.strip() for r in right.split(',')}
    return rules


class EngineTest(unittest.TestCase):
    """G4: one workflow engine in skills/_engine/, imported, never copied inside the repo."""

    def test_engine_is_not_a_skill(self):
        self.assertTrue((ENGINE / '__init__.py').is_file())
        self.assertFalse((ENGINE / 'SKILL.md').exists())
        self.assertNotIn(ENGINE, skills())

    def test_no_engine_copy_inside_the_repo(self):
        stray = [p for p in SKILLS.rglob('_engine') if p != ENGINE and '__pycache__' not in p.parts]
        self.assertEqual(stray, [], 'vendored engines belong only in skills generated outside handtools')
        assert_no_copies(self, sorted(p for p in ENGINE.glob('*.py') if p.name != '__init__.py'), ENGINE,
                         'import it from skills/_engine instead')

    def test_every_launcher_resolves_the_engine(self):
        for launcher in LAUNCHERS:
            with self.subTest(launcher=str(launcher.relative_to(ROOT))):
                text = launcher.read_text(encoding='utf-8')
                self.assertIn("(p / '_engine' / '__init__.py').is_file()", text)
                self.assertIn('from _engine import', text)
                here = launcher.parent
                found = next(p for p in (here, *here.parents) if (p / '_engine' / '__init__.py').is_file())
                self.assertEqual(found, SKILLS)

    def test_imports_follow_declared_graphs(self):
        for package in GRAPHS:
            rules = declared_graph(package)
            modules = {p.stem for p in package.glob('*.py') if p.stem != '__init__'}
            self.assertEqual(set(rules), modules, package)
            for mod in modules:
                used = set()
                for node in ast.walk(ast.parse((package / f'{mod}.py').read_text(encoding='utf-8'))):
                    if isinstance(node, ast.ImportFrom) and node.level == 1:
                        used |= {node.module} if node.module else {a.name for a in node.names}
                self.assertLessEqual(used, rules[mod], f'{package.name}.{mod}')

    def test_no_state_inside_skills(self):
        for skill in skills():
            self.assertFalse((skill / 'state').exists(), f'{skill.name}/state: state belongs in the state root')

if __name__ == '__main__':
    unittest.main()
