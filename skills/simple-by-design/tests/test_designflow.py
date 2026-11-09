import ast
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
LIB = SKILL_DIR / 'scripts' / 'designlib'
for _path in (str(SCRIPT.parent), str(SKILL_DIR.parent)):  # designlib; handtools' skills/_engine
    if _path not in sys.path:
        sys.path.insert(0, _path)

from _engine import storage  # noqa: E402
from designlib import config, flow  # noqa: E402


def printed_command(output, marker='Then run:'):
    line = next(row for row in output.splitlines() if marker in row)
    return shlex.split(line.split(marker, 1)[1].split(' <<', 1)[0])


class DesignflowTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._home = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {storage.ENV: self._home.name})
        env.start()
        self.addCleanup(env.stop)
        self.root = Path(self._tmp.name).resolve()
        self.design = self.root / '.agents' / 'design'
        self.record = self.design / 'decisions.json'
        self.view = self.design / 'decisions.md'
        self.base = Path(self._home.name).resolve() / config.AREA / storage.project_key(self.root)
        self.state = self.base / 'workflow.json'
        self.lock = self.base / 'workflow.lock'
        self.base.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()
        self._home.cleanup()

    def run_cmd(self, *args, payload=None, raw=None):
        stdin = raw if raw is not None else ('' if payload is None else json.dumps(payload))
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root), *args],
            capture_output=True, text=True, input=stdin,
        )

    def done(self, sid='s1', payload=None, ok=True):
        result = self.run_cmd('done', '--session', sid, payload=payload)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
        return result

    def workflow(self):
        return json.loads(self.state.read_text())

    def goals(self):
        return json.loads(self.record.read_text())['goals']

    def session(self, sid='s1'):
        return next(s for s in self.workflow()['sessions'] if s['id'] == sid)

    def phase(self, sid='s1'):
        session = self.session(sid)
        return session['phase'], session['cycle']

    def seed(self, goals):
        self.record.parent.mkdir(parents=True, exist_ok=True)
        self.record.write_text(json.dumps({'goals': goals}), encoding='utf-8')

    def to_challenge(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        self.done(payload={'decisions': [{'id': 'D1', 'question': 'Q?'}]})
        self.done(payload={'decisions': [{'id': 'D1', 'answer': 'A.'}]})
        self.assertEqual(self.phase(), ('challenge', 1))

    def test_start_creates_permanent_workflow(self):
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SESSION: s1', result.stdout)
        self.assertIn('PHASE: GROUND', result.stdout)
        self.assertIn('Keep it simple.', result.stdout)
        self.assertIn('Payload:', result.stdout)
        self.assertNotIn('decisions.json', result.stdout)
        self.assertNotIn('schema', result.stdout)
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
        self.assertEqual(rest, ['done', '--session', 's1'])

    def test_ground_creates_goal_set(self):
        self.run_cmd('start')
        out = self.done(payload={'goal': 'Ship.', 'constraints': ['Small.']}).stdout
        self.assertIn('PHASE: BRANCH', out)
        self.assertIn('GOAL G1 (next row id: D1)', out)
        self.assertEqual(self.goals(), [{'id': 'G1', 'goal': 'Ship.', 'constraints': ['Small.'], 'decisions': []}])
        self.assertEqual(self.session()['goal'], 'G1')

    def test_ground_reuses_goal_set_and_lists_earlier(self):
        self.seed([{'id': 'G1', 'goal': 'old', 'decisions': []},
                   {'id': 'G2', 'goal': 'new', 'decisions': []}])
        out = self.run_cmd('start').stdout
        self.assertIn('"id": "G2", "goal": "new", "held_by": null', out)
        self.done(payload={'id': 'G2'})
        self.assertEqual(self.session()['goal'], 'G2')
        self.assertEqual(len(self.goals()), 2)

    def test_ground_requires_payload(self):
        self.run_cmd('start')
        self.done(ok=False)
        self.done(payload={'constraints': ['x']}, ok=False)
        result = self.done(payload={'id': 'G9'}, ok=False)
        self.assertIn('G9', result.stderr)
        self.assertEqual(self.goals(), [])

    def test_start_adds_session_and_keeps_record(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        before = self.record.read_text()
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SESSION: s2', result.stdout)
        self.assertNotIn('SESSION: s1', result.stdout)
        self.assertIn('"held_by": "s1"', result.stdout)
        self.assertEqual(self.phase('s1'), ('branch', 1))
        self.assertEqual(self.phase('s2'), ('ground', 1))
        self.assertEqual(self.record.read_text(), before)

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
        self.assertIn('s2', every.stdout)
        self.assertIn('abandoned', every.stdout)
        one = self.run_cmd('status', '--session', 's2')
        self.assertIn('STATUS: abandoned', one.stdout)
        self.assertEqual(self.run_cmd('status', '--session', 's2', '--all').returncode, 1)

    def test_status_session_shows_goal(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        result = self.run_cmd('status', '--session', 's1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PHASE: BRANCH', result.stdout)
        self.assertIn('"goal": "Ship."', result.stdout)
        self.assertIn('--session s1', result.stdout)

    def test_done_uses_only_active_session(self):
        self.run_cmd('start')
        result = self.run_cmd('done', payload={'goal': 'Ship.'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.phase(), ('branch', 1))

    def test_done_requires_change(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        self.assertIn('requires a change', self.done(ok=False).stderr)
        self.done(payload={'goal': 'Ship.'}, ok=False)
        self.assertEqual(self.phase(), ('branch', 1))

    def test_blank_or_bom_stdin(self):
        self.run_cmd('start')
        self.assertEqual(self.run_cmd('done', raw='  \n').returncode, 1)
        self.assertEqual(self.run_cmd('done', raw='not json').returncode, 1)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), '--root', str(self.root), 'done'],
            capture_output=True, input='﻿{"goal": "Ship."}'.encode('utf-8'),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_id_only_in_ground(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        self.done(payload={'id': 'G1', 'goal': 'x'}, ok=False)

    def test_upsert_derives_status(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        self.done(payload={'decisions': [{'id': 'D1', 'question': 'Q?'},
                                         {'id': 'D2', 'question': 'R?', 'after': ['D1']}]})
        rows = self.goals()[0]['decisions']
        self.assertEqual([r['status'] for r in rows], ['open', 'open'])
        out = self.done(payload={'decisions': [{'id': 'D1', 'answer': 'A.', 'rationale': 'Why.'}]}).stdout
        self.assertIn('next row id: D3', out)
        self.assertNotIn('"status"', out)
        d1 = self.goals()[0]['decisions'][0]
        self.assertEqual((d1['question'], d1['status'], d1['answer']), ('Q?', 'resolved', 'A.'))
        self.done(payload={'decisions': [{'id': 'D1', 'answer': None, 'rationale': None}]})
        d1 = self.goals()[0]['decisions'][0]
        self.assertEqual(d1, {'id': 'D1', 'question': 'Q?', 'status': 'open'})

    def test_drop_rows(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        self.done(payload={'decisions': [{'id': 'D1', 'question': 'Q?'},
                                         {'id': 'D2', 'question': 'R?', 'after': ['D1']}]})
        self.done(payload={'decisions': [{'id': 'D1', 'drop': True}]}, ok=False)
        self.done(payload={'decisions': [{'id': 'D2', 'drop': True, 'question': 'x'}]}, ok=False)
        self.done(payload={'decisions': [{'id': 'D2', 'drop': True}, {'id': 'D1', 'drop': True}]})
        self.assertEqual(self.goals()[0]['decisions'], [])

    def test_payload_violations_rejected_and_nothing_written(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        before = (self.record.read_text(), self.state.read_text())
        bad = [
            [],
            {'extra': 1},
            {'goal': None},
            {'decisions': {}},
            {'decisions': [{'question': 'no id'}]},
            {'decisions': [{'id': 'D1'}]},
            {'decisions': [{'id': 'D1', 'question': 'Q?', 'status': 'open'}]},
            {'decisions': [{'id': 'D1', 'question': 'Q?', 'after': ['D9']}]},
            {'decisions': [{'id': 'D1', 'question': 'Q?', 'extra': 1}]},
            {'decisions': [{'id': 'X1', 'question': 'Q?'}]},
            {'decisions': [{'id': 'D1', 'question': 'Q?', 'answer': ''}]},
            {'decisions': [{'id': 'D9', 'drop': True}]},
        ]
        for payload in bad:
            with self.subTest(payload=payload):
                self.done(payload=payload, ok=False)
                self.assertEqual((self.record.read_text(), self.state.read_text()), before)

    def test_edit_touches_only_session_goal(self):
        other = {'id': 'G1', 'goal': 'old', 'decisions': [
            {'id': 'D1', 'question': 'Done?', 'status': 'resolved', 'answer': 'Yes.'}]}
        self.seed([other])
        self.run_cmd('start')
        self.done(payload={'goal': 'new'})
        self.done(payload={'decisions': [{'id': 'D1', 'question': 'Q?'}]})
        goals = self.goals()
        self.assertEqual(goals[0], other)
        self.assertEqual(goals[1]['id'], 'G2')
        self.assertEqual(goals[1]['decisions'][0]['question'], 'Q?')

    def test_decide_routes_references(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        out = self.done(payload={'decisions': [{'id': 'D1', 'question': 'Q?'}]}).stdout
        self.assertIn('PHASE: DECIDE', out)
        self.assertIn(str(SKILL_DIR / 'references' / 'contract.md'), out)
        self.assertIn(str(SKILL_DIR / 'references' / 'instructions.md'), out)
        self.assertIn('python', out)
        self.assertNotIn('instructions,', out)

    def test_challenge_open_rows_without_change_fails(self):
        self.to_challenge()
        self.done(payload={'decisions': [{'id': 'D1', 'answer': None}]})
        self.assertEqual(self.phase(), ('decide', 2))
        self.done(payload={'decisions': [{'id': 'D2', 'question': 'R?', 'answer': 'B.'}]})
        self.assertEqual(self.phase(), ('challenge', 2))
        result = self.done(ok=False)
        self.assertIn('D1', result.stderr)

    def test_challenge_open_gaps_go_to_decide(self):
        self.to_challenge()
        self.done(payload={'decisions': [{'id': 'D2', 'question': 'Gap?', 'after': ['D1']}]})
        self.assertEqual(self.phase(), ('decide', 2))
        self.done(payload={'decisions': [{'id': 'D2', 'answer': 'B.'}]})
        self.assertEqual(self.phase(), ('challenge', 2))

    def test_challenge_settled_gaps_rechallenge(self):
        self.to_challenge()
        self.done(payload={'decisions': [{'id': 'D2', 'question': 'Gap?', 'answer': 'B.'}]})
        self.assertEqual(self.phase(), ('challenge', 2))
        self.done()
        self.assertEqual(self.session()['status'], 'complete')

    def test_challenge_without_payload_closes(self):
        self.to_challenge()
        self.done()
        self.assertEqual(self.phase(), ('done', 1))
        self.assertEqual(self.session()['status'], 'complete')

    def test_header_shows_loop_and_limit(self):
        self.to_challenge()
        self.assertIn('LOOP: 1/3', self.run_cmd('status', '--session', 's1').stdout)

    def test_default_limit_closes_after_third_challenge(self):
        self.to_challenge()
        for n in (2, 3):
            self.done(payload={'decisions': [{'id': f'D{n}', 'question': f'Q{n}?', 'answer': 'A.'}]})
            self.assertEqual(self.phase(), ('challenge', n))
        out = self.done(payload={'decisions': [{'id': 'D4', 'question': 'Q4?', 'answer': 'A.'}]}).stdout
        self.assertIn('DONE', out)
        self.assertEqual(self.session()['status'], 'complete')

    def test_final_challenge_open_rows_get_one_decide(self):
        self.to_challenge()
        self.done(payload={'decisions': [{'id': 'D2', 'question': 'Q2?', 'answer': 'A.'}]})
        self.done(payload={'decisions': [{'id': 'D3', 'question': 'Q3?', 'answer': 'A.'}]})
        self.done(payload={'decisions': [{'id': 'D4', 'question': 'Late?'}]})
        self.assertEqual(self.phase(), ('decide', 4))
        self.assertIn('LOOP: 3/3', self.run_cmd('status', '--session', 's1').stdout)
        out = self.done().stdout
        self.assertIn('## Open questions', out)
        self.assertIn('- Late?', out)
        self.assertNotIn('### Late?', out)
        self.assertEqual(self.session()['status'], 'complete')

    def test_final_challenge_without_change_closes_with_open_rows(self):
        self.to_challenge()
        self.done(payload={'decisions': [{'id': 'D2', 'question': 'Q2?', 'answer': 'A.'}]})
        self.done(payload={'decisions': [{'id': 'D1', 'answer': None}]})
        self.assertEqual(self.phase(), ('decide', 3))
        self.done(payload={'decisions': [{'id': 'D3', 'question': 'Q3?', 'answer': 'A.'}]})
        self.assertEqual(self.phase(), ('challenge', 3))
        out = self.done().stdout
        self.assertIn('## Open questions', out)
        self.assertEqual(self.session()['status'], 'complete')

    def test_lowered_limit_applies_mid_session(self):
        self.to_challenge()
        self.done(payload={'decisions': [{'id': 'D2', 'question': 'Gap?'}]})
        self.assertEqual(self.phase(), ('decide', 2))
        with mock.patch('designlib.config.max_challenges', return_value=1):
            out = flow.done(self.root, 's1', None, 'L')
        self.assertIn('DONE', out)
        self.assertIn('- Gap?', out)
        self.assertEqual(self.session()['status'], 'complete')

    def test_bad_limit_blocks_done_but_not_abandon(self):
        self.run_cmd('start')
        bad = mock.patch('designlib.config.max_challenges', side_effect=ValueError('bad SKILL.md'))
        with bad:
            with self.assertRaises(ValueError):
                flow.done(self.root, 's1', {'goal': 'Ship.'}, 'L')
            self.assertIn('abandoned', flow.abandon(self.root, 's1'))
        self.assertEqual(self.goals(), [])

    def test_close_summary_and_permanent_state(self):
        self.seed([{'id': 'G1', 'goal': 'Earlier goal.', 'decisions': []}])
        self.view.write_text('keep me', encoding='utf-8')
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship the thing.', 'constraints': ['Stay simple.'],
                           'criteria': ['Users can ship.']})
        self.done(payload={'decisions': [{'id': 'D1', 'question': 'Which path?'}]})
        self.done(payload={'decisions': [{'id': 'D1', 'answer': 'The simple one.',
                                          'rationale': 'It is enough.'}]})
        out = self.done().stdout
        self.assertIn('# Ship the thing.', out)
        self.assertIn('Session s1.', out)
        self.assertIn('- Stay simple.', out)
        self.assertIn('- Users can ship.', out)
        self.assertIn('### Which path?', out)
        self.assertIn('The simple one.', out)
        self.assertIn('Reason: It is enough.', out)
        self.assertIn('## Earlier goals', out)
        self.assertIn('- Earlier goal.', out)
        self.assertIn('DONE', out)
        self.assertNotIn('G2', out)
        self.assertNotIn('D1', out)
        self.assertEqual(self.session()['status'], 'complete')
        self.assertIsNotNone(self.session()['completed'])
        self.assertEqual(self.view.read_text(), 'keep me')
        self.done(ok=False)
        reprint = self.run_cmd('status', '--session', 's1')
        self.assertEqual(reprint.returncode, 0, reprint.stderr)
        self.assertIn('The simple one.', reprint.stdout)
        self.assertNotIn('DONE', reprint.stdout)

    def test_abandon_releases_goal(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        result = self.run_cmd('abandon', '--session', 's1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.session()['status'], 'abandoned')
        self.assertEqual(self.run_cmd('abandon', '--session', 's1').returncode, 1)
        self.run_cmd('start')
        self.done('s2', payload={'id': 'G1'})

    def test_ground_refuses_goal_held_by_another_active_session(self):
        self.seed([{'id': 'G1', 'goal': 'one', 'decisions': []},
                   {'id': 'G2', 'goal': 'two', 'decisions': []}])
        self.run_cmd('start')
        self.run_cmd('start')
        self.done('s1', payload={'id': 'G1'})
        held = self.done('s2', payload={'id': 'G1'}, ok=False)
        self.assertIn('s1', held.stderr)
        self.done('s2', payload={'id': 'G2'})

    def test_done_requires_session_when_several_are_active(self):
        self.run_cmd('start')
        self.run_cmd('start')
        result = self.run_cmd('done', payload={'goal': 'Ship.'})
        self.assertEqual(result.returncode, 1)
        self.assertIn('Several active sessions', result.stderr)

    def test_sessions_advance_independently(self):
        self.run_cmd('start')
        self.run_cmd('start')
        self.done('s1', payload={'goal': 'one'})
        self.done('s2', payload={'goal': 'two'})
        self.done('s1', payload={'goal': 'one changed'})
        self.assertEqual(self.phase('s1'), ('decide', 1))
        self.assertEqual(self.phase('s2'), ('branch', 1))
        self.done('s2', ok=False)
        self.assertEqual([g['goal'] for g in self.goals()], ['one changed', 'two'])

    def test_migration_wraps_old_state(self):
        self.seed([{'id': 'G1', 'goal': 'old', 'decisions': []}])
        self.state.write_text(json.dumps({
            'phase': 'decide', 'cycle': 2, 'goal': 'G1', 'baseline': 'old',
        }))
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.workflow()
        self.assertEqual([s['id'] for s in state['sessions']], ['s1', 's2'])
        self.assertEqual(self.phase('s1'), ('decide', 2))
        self.assertEqual(self.session('s1')['goal'], 'G1')

    def test_status_migrates_old_state(self):
        self.seed([{'id': 'G1', 'goal': 'old', 'decisions': []}])
        self.state.write_text(json.dumps({
            'phase': 'decide', 'cycle': 2, 'goal': 'G1', 'baseline': 'old',
        }))
        result = self.run_cmd('status', '--session', 's1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.workflow()['version'], 1)
        self.assertEqual(self.phase('s1'), ('decide', 2))

    def test_migration_handoff_maps_complete(self):
        self.seed([{'id': 'G1', 'goal': 'old', 'decisions': []}])
        self.state.write_text(json.dumps({
            'phase': 'handoff', 'cycle': 2, 'goal': 'G1', 'baseline': 'old',
        }))
        self.assertEqual(self.run_cmd('start').returncode, 0)
        self.assertEqual(self.phase('s1'), ('done', 2))
        self.assertEqual(self.session('s1')['status'], 'complete')

    def test_stale_lock_is_recovered(self):
        self.run_cmd('start')
        self.lock.mkdir()
        old = time.time() - 31
        os.utime(self.lock, (old, old))
        result = self.run_cmd('start')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.lock.exists())

    def test_missing_session_fails(self):
        self.run_cmd('start')
        result = self.done('s9', payload={'goal': 'Ship.'}, ok=False)
        self.assertIn('s9', result.stderr)

    def test_resolution_stamps_date(self):
        self.to_challenge()
        d1 = self.goals()[0]['decisions'][0]
        self.assertRegex(d1['date'], r'^\d{4}-\d{2}-\d{2}$')

    def test_record_adds_goal_without_session(self):
        result = self.run_cmd('record', payload={
            'goal': 'Record decisions already in the code.',
            'decisions': [{'question': 'Which runtime?', 'answer': 'Python 3.11.'},
                          {'question': 'Which tests?'}]})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Recorded G1', result.stdout)
        self.assertFalse(self.state.exists())
        rows = self.goals()[0]['decisions']
        self.assertEqual([d['id'] for d in rows], ['D1', 'D2'])
        self.assertEqual([d['status'] for d in rows], ['resolved', 'open'])
        self.assertIn('date', rows[0])
        self.assertNotIn('date', rows[1])

    def test_record_updates_goal_and_supersedes(self):
        self.seed([{'id': 'G1', 'goal': 'Ship.', 'decisions': [
            {'id': 'D1', 'question': 'Which db?', 'status': 'resolved', 'answer': 'SQLite.'}]}])
        result = self.run_cmd('record', '--goal', 'G1', payload={'decisions': [
            {'question': 'Which db now?', 'answer': 'Postgres.'},
            {'id': 'D1', 'superseded_by': 'D2'}]})
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = {d['id']: d for d in self.goals()[0]['decisions']}
        self.assertEqual(rows['D1']['status'], 'superseded')
        self.assertEqual(rows['D2']['status'], 'resolved')
        shown = self.run_cmd('show').stdout
        self.assertIn('# G1. Ship.', shown)
        self.assertIn('### D1. Which db?', shown)
        self.assertIn('Superseded by: D2', shown)
        self.assertIn('### D2. Which db now?', shown)

    def test_record_refuses_held_goal_and_payload_id(self):
        self.run_cmd('start')
        self.done(payload={'goal': 'Ship.'})
        held = self.run_cmd('record', '--goal', 'G1', payload={'decisions': [{'question': 'Q?'}]})
        self.assertEqual(held.returncode, 1)
        self.assertIn('held by active session s1', held.stderr)
        with_id = self.run_cmd('record', payload={'id': 'G1'})
        self.assertEqual(with_id.returncode, 1)

    def test_cross_goal_references(self):
        self.seed([{'id': 'G1', 'goal': 'Old.', 'decisions': [
            {'id': 'D1', 'question': 'Q?', 'status': 'resolved', 'answer': 'A.'}]}])
        ok = self.run_cmd('record', payload={'goal': 'New.', 'decisions': [
            {'question': 'Q2?', 'answer': 'B.', 'after': ['G1/D1']}]})
        self.assertEqual(ok.returncode, 0, ok.stderr)
        bad = self.run_cmd('record', payload={'goal': 'Newer.', 'decisions': [
            {'question': 'Q3?', 'after': ['G7/D1']}]})
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(len(self.goals()), 2)

    def test_superseded_needs_superseded_by(self):
        self.seed([{'id': 'G1', 'goal': 'Ship.', 'decisions': [
            {'id': 'D1', 'question': 'Q?', 'status': 'superseded', 'answer': 'A.'}]}])
        self.assertEqual(self.run_cmd('show').returncode, 1)

    def test_warns_when_record_is_ignored_by_git(self):
        if subprocess.run(['git', '--version'], capture_output=True).returncode != 0:
            self.skipTest('git unavailable')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.agents/\n', encoding='utf-8')
        out = self.run_cmd('record', payload={'goal': 'Ship.'}).stdout
        self.assertIn('is ignored by git', out)
        self.assertIn('!.agents/design/decisions.json', out)
        (self.root / '.gitignore').write_text('.agents/*\n!.agents/design/\n.agents/design/*\n'
                                              '!.agents/design/decisions.json\n', encoding='utf-8')
        out = self.run_cmd('record', '--goal', 'G1', payload={'criteria': ['Done.']}).stdout
        self.assertIn('is not tracked by git yet', out)
        subprocess.run(['git', '-C', str(self.root), 'add', '.agents/design/decisions.json'], check=True)
        out = self.run_cmd('record', '--goal', 'G1', payload={'criteria': ['Done!']}).stdout
        self.assertNotIn('WARNING', out)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'SKILL.md'

    def tearDown(self):
        self._tmp.cleanup()

    def limit(self, text, encoding='utf-8'):
        self.path.write_text(text, encoding=encoding)
        return config.max_challenges(self.path)

    def test_defaults_to_three(self):
        self.assertEqual(config.max_challenges(self.path), 3)
        self.assertEqual(self.limit('# no frontmatter\n'), 3)
        self.assertEqual(self.limit('---\nname: x\n---\n'), 3)
        self.assertEqual(self.limit('---\nname: x\nmetadata:\n  max-challenges: 5\n'), 3)
        self.assertEqual(self.limit('---\nother:\n  max-challenges: 5\n---\n'), 3)

    def test_reads_metadata_value(self):
        self.assertEqual(self.limit('---\nname: x\nmetadata:\n  max-challenges: 5\n---\n'), 5)
        self.assertEqual(self.limit('---\nmetadata:\n  max-challenges: "2"  # few\n---\n'), 2)
        self.assertEqual(self.limit('---\nmetadata:\n  max-challenges: 4\n---\n', 'utf-8-sig'), 4)

    def test_invalid_value_errors(self):
        for value in ('0', 'three', '3.0', '-1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.limit(f'---\nmetadata:\n  max-challenges: {value}\n---\n')
        with self.assertRaises(ValueError):
            self.limit('---\nmetadata:\n  max-challenges: 2\n  max-challenges: 3\n---\n')

    def test_skill_md_limit_is_valid(self):
        self.assertGreaterEqual(config.max_challenges(), 1)


class ImportGraphTest(unittest.TestCase):
    ALLOWED = {
        'designflow': {'flow'},
        'flow': {'storage', 'sessions', 'record', 'config', 'steps', 'gitcheck'},
        'gitcheck': {'record'},
        'steps': {'sessions', 'record'},
        'sessions': {'config', 'record', 'storage'},
        'record': {'storage'},
        'config': set(),
        '__init__': set(),
    }

    def imports(self, path):
        found = set()
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom) and (node.module == 'designlib' or node.level):
                found |= {alias.name for alias in node.names}
        return found

    def test_imports_point_one_way(self):
        files = {p.stem: p for p in LIB.glob('*.py')}
        files['designflow'] = SCRIPT
        self.assertEqual(set(files), set(self.ALLOWED))
        for name, path in files.items():
            with self.subTest(module=name):
                self.assertLessEqual(self.imports(path), self.ALLOWED[name])


if __name__ == '__main__':
    unittest.main()
