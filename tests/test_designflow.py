import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / 'scripts' / 'designflow.py'


class DesignflowTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.design = self.root / '.agents' / 'design'
        self.record = self.design / 'decisions.json'
        self.view = self.design / 'decisions.md'
        self.state = self.design / 'workflow.json'
        self.edits = 0

    def tearDown(self):
        self._tmp.cleanup()

    def run_cmd(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root), *args],
            capture_output=True, text=True,
        )

    def phase(self):
        state = json.loads(self.state.read_text())
        return state['phase'], state['cycle']

    def write(self, decisions=(), goals=None):
        self.edits += 1
        goals = goals or [{'id': 'G1', 'goal': f'edit {self.edits}', 'decisions': list(decisions)}]
        self.record.write_text(json.dumps({'goals': goals}), encoding='utf-8')

    def advance(self, *args, decisions=()):
        self.write(decisions)
        result = self.run_cmd('done', *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def to_challenge(self):
        self.run_cmd('start')
        self.advance('--goal', 'G1')
        self.advance()
        self.advance()
        self.assertEqual(self.phase(), ('challenge', 1))

    OPEN = {'id': 'D1', 'question': 'Open?', 'status': 'open'}
    RESOLVED = {'id': 'D1', 'question': 'Done?', 'status': 'resolved', 'answer': 'Yes.'}

    def test_start_creates_files(self):
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PHASE: GROUND', result.stdout)
        self.assertIn('Keep it simple.', result.stdout)
        self.assertIn(str(SKILL_DIR / 'references' / 'decisions.schema.json'), result.stdout)
        self.assertEqual(json.loads(self.record.read_text()), {'goals': []})
        self.assertEqual(self.phase(), ('ground', 1))

    def test_start_replaces_workflow_keeps_record(self):
        self.run_cmd('start')
        self.advance('--goal', 'G1')
        before = self.record.read_text()
        self.assertEqual(self.run_cmd('start').returncode, 0)
        self.assertEqual(self.phase(), ('ground', 1))
        self.assertIsNone(json.loads(self.state.read_text())['goal'])
        self.assertEqual(self.record.read_text(), before)

    def test_status_without_workflow_fails(self):
        result = self.run_cmd('status')
        self.assertEqual(result.returncode, 1)
        self.assertIn('start', result.stderr)

    def test_ground_requires_existing_goal(self):
        self.run_cmd('start')
        self.assertEqual(self.run_cmd('done').returncode, 1)
        self.write()
        result = self.run_cmd('done', '--goal', 'G2')
        self.assertEqual(result.returncode, 1)
        self.assertIn('G2', result.stderr)

    def test_done_requires_change(self):
        self.run_cmd('start')
        self.advance('--goal', 'G1')
        result = self.run_cmd('done')
        self.assertEqual(result.returncode, 1)
        self.assertIn('has not changed', result.stderr)
        self.assertEqual(self.phase(), ('branch', 1))

    def test_flags_only_in_their_phase(self):
        self.run_cmd('start')
        self.write()
        self.assertEqual(self.run_cmd('done', '--gaps', '0').returncode, 1)
        self.advance('--goal', 'G1')
        self.write()
        self.assertEqual(self.run_cmd('done', '--goal', 'G1').returncode, 1)

    def test_schema_violations_rejected(self):
        self.run_cmd('start')
        self.advance('--goal', 'G1')
        bad = [
            [{'id': 'D1', 'question': 'Q?', 'status': 'resolved'}],
            [{'id': 'D1', 'question': 'Q?', 'status': 'maybe'}],
            [{'id': 'D1', 'question': 'Q?', 'status': 'open', 'after': ['D9']}],
            [self.OPEN, self.OPEN],
            [{'id': 'D1', 'question': 'Q?', 'status': 'open', 'extra': 1}],
        ]
        for decisions in bad:
            with self.subTest(decisions=decisions):
                self.write(decisions)
                self.assertEqual(self.run_cmd('done').returncode, 1)

    def test_goal_sets_scope_ids(self):
        goals = [
            {'id': 'G1', 'goal': 'old', 'decisions': [self.RESOLVED]},
            {'id': 'G2', 'goal': 'new', 'decisions': [self.OPEN]},
        ]
        self.run_cmd('start')
        self.write(goals=goals)
        self.assertEqual(self.run_cmd('done', '--goal', 'G2').returncode, 0)

    def test_decide_routes_references(self):
        self.run_cmd('start')
        self.advance('--goal', 'G1')
        out = self.advance().stdout
        self.assertIn('PHASE: DECIDE', out)
        self.assertIn(str(SKILL_DIR / 'references' / 'contract.md'), out)
        self.assertIn(str(SKILL_DIR / 'languages' / 'skills.md'), out)
        self.assertIn('python', out)
        self.assertNotIn('skills,', out)

    def test_challenge_zero_gaps_with_open_rows_fails(self):
        self.to_challenge()
        self.write([self.OPEN])
        result = self.run_cmd('done', '--gaps', '0')
        self.assertEqual(result.returncode, 1)
        self.assertIn('D1', result.stderr)

    def test_challenge_gaps_without_open_rows_fails(self):
        self.to_challenge()
        self.write([self.RESOLVED])
        self.assertEqual(self.run_cmd('done', '--gaps', '1').returncode, 1)

    def test_challenge_gaps_loops_to_branch(self):
        self.to_challenge()
        self.advance('--gaps', '1', decisions=[self.OPEN])
        self.assertEqual(self.phase(), ('branch', 2))

    def test_handoff_rebuilds_view_and_removes_workflow(self):
        self.view.parent.mkdir(parents=True, exist_ok=True)
        self.view.write_text('old view', encoding='utf-8')
        self.to_challenge()
        self.advance('--gaps', '0', decisions=[self.RESOLVED])
        self.assertEqual(self.phase(), ('handoff', 1))
        self.assertFalse(self.view.exists())
        self.assertEqual(self.run_cmd('done').returncode, 1)
        self.view.write_text('# Goal\nNew view.\n', encoding='utf-8')
        result = self.run_cmd('done')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('DONE', result.stdout)
        self.assertFalse(self.state.exists())
        self.assertTrue(self.record.exists())


TEMPLATE = SKILL_DIR / 'references' / 'workflow.py'


class WorkflowTemplateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.state = self.root / '.agents' / 'workflow' / 'workflow.json'

    def tearDown(self):
        self._tmp.cleanup()

    def run_cmd(self, *args):
        return subprocess.run(
            [sys.executable, str(TEMPLATE), '--root', str(self.root), *args],
            capture_output=True, text=True,
        )

    def test_result_a_runs_z(self):
        self.assertIn('STEP: X', self.run_cmd('start').stdout)
        self.assertIn('STEP: Y', self.run_cmd('done').stdout)
        self.assertEqual(self.run_cmd('done').returncode, 1)
        self.assertIn('STEP: Z', self.run_cmd('done', '--result', 'A').stdout)
        self.assertIn('DONE', self.run_cmd('done').stdout)
        self.assertFalse(self.state.exists())

    def test_other_result_finishes(self):
        self.run_cmd('start')
        self.run_cmd('done')
        self.assertIn('DONE', self.run_cmd('done', '--result', 'B').stdout)
        self.assertFalse(self.state.exists())

    def test_result_outside_y_fails(self):
        self.run_cmd('start')
        self.assertEqual(self.run_cmd('done', '--result', 'A').returncode, 1)


if __name__ == '__main__':
    unittest.main()
