"""Unit tests for the shared engine: storage, cli, flow (single run), sessions (registry).

Run from the repo root: python3 -m unittest discover -s skills/_engine/tests
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

SKILLS = Path(__file__).resolve().parents[2]
if str(SKILLS) not in sys.path:
    sys.path.insert(0, str(SKILLS))

from _engine import cli, flow, sessions, storage  # noqa: E402


class TempState(unittest.TestCase):
    """Each test gets its own HANDTOOLS_STATE; never the real ~/.agents/state."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        env = mock.patch.dict(os.environ, {storage.ENV: str(self.tmp / 'state')})
        env.start()
        self.addCleanup(env.stop)
        self.root = self.tmp / 'proj'
        self.root.mkdir()


class StorageTest(TempState):
    def test_default_root_is_home_agents_state(self):
        with mock.patch.dict(os.environ) as env, mock.patch.object(Path, 'home', return_value=self.tmp):
            env.pop(storage.ENV, None)
            self.assertEqual(storage.state_root(), self.tmp / '.agents' / 'state')

    def test_env_overrides_root(self):
        self.assertEqual(storage.state_root(), self.tmp / 'state')

    def test_project_key_is_stable_and_per_path(self):
        a, b = Path('/work/my repo').resolve(), Path('/other/my repo').resolve()
        self.assertEqual(storage.project_key(a), storage.project_key(a))
        self.assertNotEqual(storage.project_key(a), storage.project_key(b))
        self.assertRegex(storage.project_key(a), r'^my-repo-[0-9a-f]{8}$')

    def test_state_dir_layout_and_project_file(self):
        path = storage.state_dir('untangle', self.root)
        self.assertEqual(path, self.tmp / 'state' / 'untangle' / storage.project_key(self.root))
        self.assertTrue(path.is_dir())
        self.assertFalse((path / 'project.json').exists())

    def test_lock_is_exclusive_and_released(self):
        base = self.tmp / 'lockdir'
        with storage.lock(base):
            with mock.patch.object(storage, 'LOCK_TIMEOUT', 0.1), self.assertRaises(ValueError):
                with storage.lock(base):
                    pass
        self.assertFalse((base / 'workflow.lock').exists())


class CliTest(unittest.TestCase):
    def test_posix_quoting(self):
        with mock.patch('os.name', 'posix'):
            self.assertEqual(cli.quote('a b'), "'a b'")

    def test_windows_quoting_uses_double_quotes(self):
        with mock.patch('os.name', 'nt'):
            self.assertEqual(cli.quote(r'C:\Program Files\Python\python.exe'), r'"C:\Program Files\Python\python.exe"')

    def test_run_prints_errors_and_returns_one(self):
        def fail():
            raise ValueError('nope')
        with mock.patch('sys.stderr') as err:
            self.assertEqual(cli.run(fail), 1)
        self.assertIn('ERROR: nope', ''.join(c.args[0] for c in err.write.call_args_list))


def make_steps(mode):
    """A two-step workflow: A, then B (whose check needs {"ok": true}) and done."""
    seen = []

    def check_b(state, payload):
        if not payload.get('ok'):
            raise ValueError('need ok')

    def advance(state, payload):
        seen.append(dict(state))
        return {'a': 'b', 'b': None}[state['phase']]

    return types.SimpleNamespace(
        MODE=mode, AREA='demo', ORDER=['a', 'b'], DONE_MSG='DONE',
        PROMPTS={'a': 'Do A.', 'b': lambda root: f'Do B in {root}.'},
        CHECKS={'b': check_b}, advance=advance, seen=seen)


class FlowTest(TempState):
    def test_stateful_run(self):
        steps = make_steps('stateful')
        self.assertIn('STEP: A', flow.start(steps, self.root, 'go'))
        with self.assertRaises(ValueError):
            flow.start(steps, self.root, 'go')
        out = flow.done(steps, self.root, None, 'go')
        self.assertIn(f'Do B in {self.root}.', out)
        self.assertEqual(steps.seen[-1], {'phase': 'a', 'root': str(self.root)})
        with self.assertRaises(ValueError):
            flow.done(steps, self.root, {}, 'go')
        self.assertEqual(flow.done(steps, self.root, {'ok': True}, 'go'), 'DONE')
        self.assertFalse((storage.state_dir('demo', self.root) / 'workflow.json').exists())

    def test_stateless_saves_nothing(self):
        steps = make_steps('stateless')
        self.assertIn('done --stage a', flow.start(steps, self.root, 'go'))
        self.assertIn('STEP: B', flow.done(steps, self.root, None, 'go', stage='a'))
        self.assertEqual(steps.seen[-1], {'phase': 'a', 'root': str(self.root)})
        with self.assertRaises(ValueError):
            flow.status(steps, self.root, 'go')
        self.assertFalse((self.tmp / 'state').exists())

    def test_abandon(self):
        steps = make_steps('stateful')
        flow.start(steps, self.root, 'go')
        self.assertEqual(flow.abandon(steps, self.root), 'Run abandoned.')
        self.assertIn('STEP: A', flow.start(steps, self.root, 'go'))


class SessionsTest(TempState):
    def test_add_find_select_close(self):
        state = sessions.load('demo', self.root, allow_missing=True)
        s1 = sessions.add(state, phase='one')
        s2 = sessions.add(state, phase='one')
        self.assertEqual((s1['id'], s2['id'], s1['status']), ('s1', 's2', 'active'))
        with self.assertRaisesRegex(ValueError, 'pass --session sN'):
            sessions.select_active(state, None)
        sessions.close(s1, 'complete', 'closed')
        self.assertIs(sessions.select_active(state, None), s2)
        with self.assertRaises(ValueError):
            sessions.select_active(state, 's1')
        self.assertEqual((s1['phase'], s1['completed'] is not None), ('closed', True))
        sessions.save('demo', self.root, state)
        self.assertEqual(sessions.load('demo', self.root), state)

    def test_missing_registry(self):
        with self.assertRaises(ValueError):
            sessions.load('demo', self.root)


if __name__ == '__main__':
    unittest.main()
