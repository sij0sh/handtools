import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / 'scripts' / 'designflow.py'


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def printed_command(output, marker='then run:'):
    line = next(row for row in output.splitlines() if marker in row)
    return shlex.split(line.split(marker, 1)[1])


class DesignflowTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.design = self.root / '.agents' / 'design'
        self.record = self.design / 'decisions.json'
        self.view = self.design / 'decisions.md'
        self.state = self.design / 'workflow.json'
        self.lock = self.design / 'workflow.lock'
        self.edits = 0

    def tearDown(self):
        self._tmp.cleanup()

    def run_cmd(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root), *args],
            capture_output=True, text=True,
        )

    def workflow(self):
        return json.loads(self.state.read_text())

    def session(self, sid='s1'):
        return next(s for s in self.workflow()['sessions'] if s['id'] == sid)

    def phase(self, sid='s1'):
        session = self.session(sid)
        return session['phase'], session['cycle']

    def write(self, decisions=(), goals=None):
        self.edits += 1
        goals = goals or [{'id': 'G1', 'goal': f'edit {self.edits}', 'decisions': list(decisions)}]
        self.record.parent.mkdir(parents=True, exist_ok=True)
        self.record.write_text(json.dumps({'goals': goals}), encoding='utf-8')

    def advance(self, *args, decisions=()):
        self.write(decisions)
        result = self.run_cmd('done', *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def to_challenge(self):
        self.run_cmd('start')
        self.advance('--session', 's1', '--goal', 'G1')
        self.advance('--session', 's1')
        self.advance('--session', 's1')
        self.assertEqual(self.phase(), ('challenge', 1))

    OPEN = {'id': 'D1', 'question': 'Open?', 'status': 'open'}
    RESOLVED = {'id': 'D1', 'question': 'Done?', 'status': 'resolved', 'answer': 'Yes.'}

    def test_start_creates_permanent_workflow(self):
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SESSION: s1', result.stdout)
        self.assertIn('PHASE: GROUND', result.stdout)
        self.assertIn('Keep it simple.', result.stdout)
        self.assertIn(str(SKILL_DIR / 'references' / 'decisions.schema.json'), result.stdout)
        self.assertEqual(json.loads(self.record.read_text()), {'goals': []})
        state = self.workflow()
        self.assertEqual(state['version'], 1)
        session = state['sessions'][0]
        self.assertEqual(session['id'], 's1')
        self.assertEqual(session['status'], 'active')
        self.assertEqual(session['phase'], 'ground')
        self.assertEqual(session['cycle'], 1)
        self.assertIsNone(session['goal'])
        self.assertIsNone(session['baseline'])
        self.assertIsNone(session['completed'])
        self.assertFalse(self.view.exists())

    def test_printed_done_command_uses_running_interpreter_and_session(self):
        command = printed_command(self.run_cmd('start').stdout)
        self.assertEqual(command[:2], [sys.executable, str(SCRIPT)])
        rest = command[2:]
        if rest[:2] == ['--root', str(self.root)]:
            rest = rest[2:]
        self.assertEqual(rest, ['done', '--session', 's1', '--goal', 'G#'])

    def test_start_adds_session_and_keeps_record(self):
        self.run_cmd('start')
        self.advance('--session', 's1', '--goal', 'G1')
        before = self.record.read_text()
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SESSION: s2', result.stdout)
        self.assertNotIn('SESSION: s1', result.stdout)
        self.assertEqual(self.phase('s1'), ('branch', 1))
        self.assertEqual(self.phase('s2'), ('ground', 1))
        self.assertEqual(self.session('s1')['goal'], 'G1')
        self.assertEqual(self.record.read_text(), before)
        self.assertEqual(
            [s['id'] for s in self.workflow()['sessions']], ['s1', 's2'],
        )

    def test_status_without_workflow_fails(self):
        result = self.run_cmd('status')
        self.assertEqual(result.returncode, 1)
        self.assertIn('start', result.stderr)

    def test_status_lists_active_and_all(self):
        self.run_cmd('start')
        self.run_cmd('start')
        self.assertEqual(self.run_cmd('abandon', '--session', 's2').returncode, 0)
        active = self.run_cmd('status')
        self.assertIn('s1', active.stdout)
        self.assertNotIn('s2', active.stdout)
        every = self.run_cmd('status', '--all')
        self.assertIn('s1', every.stdout)
        self.assertIn('s2', every.stdout)
        self.assertIn('abandoned', every.stdout)
        one = self.run_cmd('status', '--session', 's2')
        self.assertIn('STATUS: abandoned', one.stdout)
        self.assertEqual(self.run_cmd('status', '--session', 's2', '--all').returncode, 1)

    def test_status_session_shows_active_step(self):
        self.run_cmd('start')
        result = self.run_cmd('status', '--session', 's1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SESSION: s1', result.stdout)
        self.assertIn('PHASE: GROUND', result.stdout)
        self.assertIn('--session s1', result.stdout)

    def test_ground_requires_existing_goal(self):
        self.run_cmd('start')
        self.assertEqual(self.run_cmd('done', '--session', 's1').returncode, 1)
        self.write()
        result = self.run_cmd('done', '--session', 's1', '--goal', 'G2')
        self.assertEqual(result.returncode, 1)
        self.assertIn('G2', result.stderr)

    def test_done_uses_only_active_session(self):
        self.run_cmd('start')
        self.write()
        result = self.run_cmd('done', '--goal', 'G1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phase(), ('branch', 1))

    def test_done_requires_goal_edit(self):
        self.run_cmd('start')
        self.advance('--session', 's1', '--goal', 'G1')
        result = self.run_cmd('done', '--session', 's1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('has not changed', result.stderr)
        self.assertEqual(self.phase(), ('branch', 1))

    def test_flags_only_in_their_phase(self):
        self.run_cmd('start')
        self.write()
        self.assertEqual(self.run_cmd('done', '--session', 's1', '--gaps', '0').returncode, 1)
        self.advance('--session', 's1', '--goal', 'G1')
        self.write()
        self.assertEqual(self.run_cmd('done', '--session', 's1', '--goal', 'G1').returncode, 1)

    def test_schema_violations_rejected(self):
        self.run_cmd('start')
        self.advance('--session', 's1', '--goal', 'G1')
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
                self.assertEqual(self.run_cmd('done', '--session', 's1').returncode, 1)

    def test_goal_sets_scope_ids(self):
        goals = [
            {'id': 'G1', 'goal': 'old', 'decisions': [self.RESOLVED]},
            {'id': 'G2', 'goal': 'new', 'decisions': [self.OPEN]},
        ]
        self.run_cmd('start')
        self.write(goals=goals)
        self.assertEqual(self.run_cmd('done', '--session', 's1', '--goal', 'G2').returncode, 0)

    def test_decide_routes_references(self):
        self.run_cmd('start')
        self.advance('--session', 's1', '--goal', 'G1')
        out = self.advance('--session', 's1').stdout
        self.assertIn('PHASE: DECIDE', out)
        self.assertIn(str(SKILL_DIR / 'references' / 'contract.md'), out)
        self.assertIn(str(SKILL_DIR / 'languages' / 'skills.md'), out)
        self.assertIn('python', out)
        self.assertNotIn('skills,', out)

    def test_challenge_zero_gaps_with_open_rows_fails(self):
        self.to_challenge()
        self.write([self.OPEN])
        result = self.run_cmd('done', '--session', 's1', '--gaps', '0')
        self.assertEqual(result.returncode, 1)
        self.assertIn('D1', result.stderr)

    def test_challenge_gaps_without_open_rows_fails(self):
        self.to_challenge()
        self.write([self.RESOLVED])
        self.assertEqual(self.run_cmd('done', '--session', 's1', '--gaps', '1').returncode, 1)

    def test_challenge_gaps_loops_to_branch(self):
        self.to_challenge()
        self.advance('--session', 's1', '--gaps', '1', decisions=[self.OPEN])
        self.assertEqual(self.phase(), ('branch', 2))

    def test_challenge_zero_gaps_needs_no_edit(self):
        self.to_challenge()
        result = self.run_cmd('done', '--session', 's1', '--gaps', '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phase(), ('done', 1))
        self.assertEqual(self.session()['status'], 'complete')

    def test_close_summary_and_permanent_state(self):
        earlier = {'id': 'G0', 'goal': 'Earlier goal.', 'decisions': []}

        def target(decisions):
            return {
                'id': 'G1',
                'goal': 'Ship the thing.',
                'constraints': ['Stay simple.'],
                'criteria': ['Users can ship.'],
                'decisions': decisions,
            }

        self.view.parent.mkdir(parents=True, exist_ok=True)
        self.view.write_text('keep me', encoding='utf-8')
        self.run_cmd('start')
        self.write(goals=[earlier, target([])])
        self.assertEqual(self.run_cmd('done', '--session', 's1', '--goal', 'G1').returncode, 0)
        self.write(goals=[earlier, target([{
            'id': 'D1', 'question': 'Which path?', 'status': 'open',
        }])])
        self.assertEqual(self.run_cmd('done', '--session', 's1').returncode, 0)
        self.write(goals=[earlier, target([{
            'id': 'D1', 'question': 'Which path?', 'status': 'resolved',
            'answer': 'The simple one.', 'rationale': 'It is enough.',
        }])])
        self.assertEqual(self.run_cmd('done', '--session', 's1').returncode, 0)
        result = self.run_cmd('done', '--session', 's1', '--gaps', '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn('# Ship the thing.', out)
        self.assertIn('Session s1.', out)
        self.assertIn('## Constraints', out)
        self.assertIn('- Stay simple.', out)
        self.assertIn('## Success criteria', out)
        self.assertIn('- Users can ship.', out)
        self.assertIn('### Which path?', out)
        self.assertIn('The simple one.', out)
        self.assertIn('Reason: It is enough.', out)
        self.assertIn('## Earlier goals', out)
        self.assertIn('- Earlier goal.', out)
        self.assertIn('DONE', out)
        self.assertNotIn('G1', out)
        self.assertNotIn('D1', out)
        self.assertEqual(self.phase(), ('done', 1))
        self.assertEqual(self.session()['status'], 'complete')
        self.assertIsNotNone(self.session()['completed'])
        self.assertTrue(self.state.exists())
        self.assertEqual(self.view.read_text(), 'keep me')
        self.assertEqual(self.run_cmd('done', '--session', 's1').returncode, 1)
        reprint = self.run_cmd('status', '--session', 's1')
        self.assertEqual(reprint.returncode, 0, reprint.stderr)
        self.assertIn('# Ship the thing.', reprint.stdout)
        self.assertIn('The simple one.', reprint.stdout)
        self.assertNotIn('DONE', reprint.stdout)

    def test_abandon_releases_goal(self):
        self.run_cmd('start')
        self.write()
        self.advance('--session', 's1', '--goal', 'G1')
        result = self.run_cmd('abandon', '--session', 's1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phase(), ('done', 1))
        self.assertEqual(self.session()['status'], 'abandoned')
        self.assertIn('STATUS: abandoned', self.run_cmd('status', '--session', 's1').stdout)
        self.assertEqual(self.run_cmd('abandon', '--session', 's1').returncode, 1)
        self.run_cmd('start')
        self.write()
        self.assertEqual(self.run_cmd('done', '--session', 's2', '--goal', 'G1').returncode, 0)

    def test_ground_refuses_goal_held_by_another_active_session(self):
        self.run_cmd('start')
        self.run_cmd('start')
        self.write(goals=[
            {'id': 'G1', 'goal': 'one', 'decisions': []},
            {'id': 'G2', 'goal': 'two', 'decisions': []},
        ])
        self.assertEqual(self.run_cmd('done', '--session', 's1', '--goal', 'G1').returncode, 0)
        held = self.run_cmd('done', '--session', 's2', '--goal', 'G1')
        self.assertEqual(held.returncode, 1)
        self.assertIn('s1', held.stderr)
        self.assertEqual(self.run_cmd('done', '--session', 's2', '--goal', 'G2').returncode, 0)

    def test_done_requires_session_when_several_are_active(self):
        self.run_cmd('start')
        self.run_cmd('start')
        self.write()
        result = self.run_cmd('done')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Several active sessions', result.stderr)
        self.assertEqual(self.run_cmd('done', '--session', 's1', '--goal', 'G1').returncode, 0)

    def test_sessions_advance_independently(self):
        self.run_cmd('start')
        self.run_cmd('start')
        one = {'id': 'G1', 'goal': 'one', 'decisions': []}
        two = {'id': 'G2', 'goal': 'two', 'decisions': []}
        self.write(goals=[one, two])
        self.assertEqual(self.run_cmd('done', '--session', 's1', '--goal', 'G1').returncode, 0)
        self.assertEqual(self.run_cmd('done', '--session', 's2', '--goal', 'G2').returncode, 0)
        one['goal'] = 'one changed'
        self.write(goals=[one, two])
        self.assertEqual(self.run_cmd('done', '--session', 's1').returncode, 0)
        self.assertEqual(self.phase('s1'), ('decide', 1))
        self.assertEqual(self.phase('s2'), ('branch', 1))
        self.assertEqual(self.run_cmd('done', '--session', 's2').returncode, 1)

    def test_migration_wraps_old_state(self):
        self.write()
        self.state.write_text(json.dumps({
            'phase': 'decide', 'cycle': 2, 'goal': 'G1', 'baseline': 'old',
        }))
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.workflow()
        self.assertEqual(state['version'], 1)
        self.assertEqual([s['id'] for s in state['sessions']], ['s1', 's2'])
        self.assertEqual(self.phase('s1'), ('decide', 2))
        self.assertEqual(self.session('s1')['goal'], 'G1')
        self.assertEqual(self.session('s2')['phase'], 'ground')

    def test_status_migrates_old_state(self):
        self.write()
        self.state.write_text(json.dumps({
            'phase': 'decide', 'cycle': 2, 'goal': 'G1', 'baseline': 'old',
        }))
        result = self.run_cmd('status', '--session', 's1')
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.workflow()
        self.assertEqual(state['version'], 1)
        self.assertEqual([s['id'] for s in state['sessions']], ['s1'])
        self.assertEqual(self.phase('s1'), ('decide', 2))

    def test_migration_handoff_maps_complete(self):
        self.write([self.RESOLVED])
        self.state.write_text(json.dumps({
            'phase': 'handoff', 'cycle': 2, 'goal': 'G1', 'baseline': 'old',
        }))
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phase('s1'), ('done', 2))
        self.assertEqual(self.session('s1')['status'], 'complete')
        self.assertEqual(self.phase('s2'), ('ground', 1))

    def test_stale_lock_is_recovered(self):
        self.run_cmd('start')
        self.lock.mkdir()
        old = time.time() - 31
        os.utime(self.lock, (old, old))
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.lock.exists())
        self.assertEqual([s['id'] for s in self.workflow()['sessions']], ['s1', 's2'])

    def test_missing_session_fails(self):
        self.run_cmd('start')
        self.write()
        result = self.run_cmd('done', '--session', 's9', '--goal', 'G1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('s9', result.stderr)


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

    def test_printed_done_command_uses_running_interpreter(self):
        command = printed_command(self.run_cmd('start').stdout, 'Then run:')
        self.assertEqual(command[:2], [sys.executable, str(TEMPLATE)])
        rest = command[2:]
        if rest[:2] == ['--root', str(self.root)]:
            rest = rest[2:]
        self.assertEqual(rest, ['done'])

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


class QuoteTest(unittest.TestCase):
    def setUp(self):
        self.designflow = load_module(SCRIPT, 'designflow_quote_test')

    def test_posix_quoting(self):
        self.assertEqual(self.designflow.quote('a b'), "'a b'")

    def test_windows_quoting_uses_double_quotes(self):
        with mock.patch('os.name', 'nt'):
            self.assertEqual(
                self.designflow.quote(r'C:\Program Files\Python\python.exe'),
                r'"C:\Program Files\Python\python.exe"',
            )


if __name__ == '__main__':
    unittest.main()
