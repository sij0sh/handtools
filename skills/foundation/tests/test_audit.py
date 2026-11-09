"""Tests for the read-only audit script."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'scripts' / 'audit.py'


def run_audit(root):
    return subprocess.run(
        [sys.executable, str(AUDIT), '--root', str(root)],
        capture_output=True, text=True, check=False,
    )


class AuditTests(unittest.TestCase):
    def test_reports_evidence_and_stacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'mise.toml').write_text('[tools]\npython = "3.14"\n', encoding='utf-8')
            (root / 'tests').mkdir()
            (root / 'package.json').write_text('{}', encoding='utf-8')
            (root / '.gitignore').write_text('state/\n', encoding='utf-8')

            result = run_audit(root)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['stacks'], ['node'])
            self.assertEqual(report['files'], 3)
            self.assertIn('mise.toml', report['evidence']['runtime-versions'])
            self.assertIn('tests', report['evidence']['tests-lint'])
            self.assertIn('.gitignore', report['evidence']['secrets-excluded'])
            self.assertEqual(report['warnings'], [])

    @unittest.skipUnless(shutil.which('git'), 'git is required')
    def test_warns_on_tracked_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            (root / '.env').write_text('SECRET=1\n', encoding='utf-8')
            subprocess.run(['git', 'add', '.env'], cwd=root, check=True)

            report = json.loads(run_audit(root).stdout)

            self.assertEqual(report['warnings'], ['tracked env file: .env'])

    def test_missing_root_is_an_error(self):
        missing = Path(tempfile.gettempdir()) / 'foundation-test-does-not-exist'

        result = run_audit(missing)

        self.assertEqual(result.returncode, 1)
        self.assertIn('not a directory', json.loads(result.stdout)['error'])


if __name__ == '__main__':
    unittest.main()
