"""Exact workflow views are independent of transcript ranking and current session exclusions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS))
from _engine import storage


class WorkflowViews(unittest.TestCase):
    def test_query_loads_exact_project_heads_and_history(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / 'project'; root.mkdir()
            with patch.dict(os.environ, {'HANDTOOLS_STATE': str(Path(name) / 'state')}):
                base = storage.state_dir('build-skills', root)
                storage.write_state(base / 'workflow.json', {'phase':'draft'})
                storage.write_state(base / 'workflow.json', {'phase':'review', 'sessions':[{'id':'s1', 'plan':{'decisions':[{'id':'D1','question':'Which owner?','answer':'engine'}]}}]})
                script = SKILLS / 'remember' / 'scripts' / 'remember.py'
                result = subprocess.run([sys.executable, str(script), '--repo', str(root), 'query',
                    'SELECT run_id, revision, state FROM workflow_runs', '--format', 'json'],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('review', result.stdout)
                self.assertIn('workflow.json', result.stdout)
                result = subprocess.run([sys.executable, str(script), '--repo', str(root), 'query',
                    'SELECT COUNT(*) AS total FROM workflow_events', '--format', 'json'],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('2', result.stdout)
                result = subprocess.run([sys.executable, str(script), '--repo', str(root), 'query',
                    'SELECT question, answer FROM workflow_decisions', '--format', 'json'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Which owner?', result.stdout)
                self.assertIn('engine', result.stdout)
                other = Path(name) / 'other'; other.mkdir()
                result = subprocess.run([sys.executable, str(script), '--repo', str(other), 'query',
                    'SELECT * FROM workflow_runs', '--format', 'json'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('review', result.stdout)
