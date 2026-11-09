"""Architecture checks: import edges, standard library only, and syntax."""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
PACKAGE = SCRIPTS / 'workflowlib'
LOCAL = {'workflowlib', '_engine'}  # foundation's stages, handtools' engine

FALLBACK_STDLIB = {
    'argparse', 'contextlib', 'fnmatch', 'hashlib', 'json', 'os', 'pathlib',
    're', 'shlex', 'subprocess', 'sys', 'time',
}
STDLIB = set(getattr(sys, 'stdlib_module_names', ())) or FALLBACK_STDLIB


def source_files():
    return [SCRIPTS / 'audit.py', SCRIPTS / 'validate.py', SCRIPTS / 'workflow.py', *PACKAGE.glob('*.py')]


def parse(path):
    return ast.parse(path.read_text(encoding='utf-8'), filename=str(path))


def local_imports(path):
    """Names imported from this package (relative or absolute `workflowlib`)."""
    found = set()
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.ImportFrom) and (node.level or (node.module or '').startswith('workflowlib')):
            found.update(alias.name for alias in node.names)
    return found


def top_level_imports(path):
    names = set()
    for node in parse(path).body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add((node.module or '').split('.')[0])
    return names


class ImportTests(unittest.TestCase):
    def test_package_holds_only_steps(self):
        self.assertEqual({p.stem for p in PACKAGE.glob('*.py')}, {'__init__', 'steps'})

    def test_steps_import_only_the_engine_storage(self):
        self.assertEqual(local_imports(PACKAGE / 'steps.py'), set())
        self.assertIn('_engine', top_level_imports(PACKAGE / 'steps.py'))

    def test_scripts_import_only_the_standard_library(self):
        local = LOCAL
        for path in source_files():
            self.assertLessEqual(top_level_imports(path) - local, STDLIB, path.name)

    def test_every_script_compiles(self):
        for path in source_files():
            with self.subTest(path=path.name):
                compile(path.read_text(encoding='utf-8'), str(path), 'exec')


if __name__ == '__main__':
    unittest.main()
