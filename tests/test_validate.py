"""Tests for read-only validation of changed and untracked files."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / 'scripts' / 'validate.py'


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, check=True)


def init_repo(root):
    git(root, 'init', '-q')
    git(root, 'config', 'user.email', 'test@example.com')
    git(root, 'config', 'user.name', 'Test')
    (root / 'seed.txt').write_text('seed\n', encoding='utf-8')
    git(root, 'add', 'seed.txt')
    git(root, 'commit', '-qm', 'seed')


def run_validate(root):
    return subprocess.run(
        [sys.executable, str(VALIDATE), '--root', str(root)],
        capture_output=True, text=True, check=False,
    )


class ValidateTests(unittest.TestCase):
    def test_clean_repo_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)

            result = run_validate(root)

            self.assertEqual(result.returncode, 0, result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report['changed'], [])
            self.assertEqual(report['failed'], [])

    def test_invalid_json_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            (root / 'bad.json').write_text('{', encoding='utf-8')

            result = run_validate(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn('bad.json', json.loads(result.stdout)['failed'])

    def test_valid_json_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            (root / 'ok.json').write_text('{"ok": true}\n', encoding='utf-8')

            result = run_validate(root)

            self.assertEqual(result.returncode, 0, result.stdout)
            report = json.loads(result.stdout)
            self.assertIn('ok.json', report['changed'])
            self.assertIn('ok.json', [check['name'] for check in report['checks']])

    def test_committed_env_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            (root / '.env').write_text('SECRET=1\n', encoding='utf-8')
            git(root, 'add', '.env')

            result = run_validate(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn('no committed .env files', json.loads(result.stdout)['failed'])

    def test_adr_needs_a_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            adr = root / 'docs' / 'adr'
            adr.mkdir(parents=True)
            (adr / '0001-test.md').write_text('No title\n', encoding='utf-8')

            result = run_validate(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn('docs/adr/0001-test.md has a title', json.loads(result.stdout)['failed'])

    @unittest.skipUnless(sys.version_info >= (3, 11), 'tomllib requires Python 3.11+')
    def test_invalid_toml_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            (root / 'bad.toml').write_text('[tools\n', encoding='utf-8')

            result = run_validate(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn('bad.toml', json.loads(result.stdout)['failed'])


if __name__ == '__main__':
    unittest.main()
