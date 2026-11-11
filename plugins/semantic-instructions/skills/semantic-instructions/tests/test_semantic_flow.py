import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / 'scripts' / 'semantic_flow.py'
STATE = Path('.agents') / 'semantic-instructions.json'


def run(root, *args, payload=None):
    command = [sys.executable, '-B', str(SCRIPT), '--root', str(root), *args]
    return subprocess.run(command, input=json.dumps(payload) if payload is not None else '',
                          text=True, capture_output=True, cwd=root)


def read_state(root):
    return json.loads((root / STATE).read_text(encoding='utf-8'))


def frame(**overrides):
    value = {'status': 'frame', 'operation': 'create', 'target': 'out.txt',
             'format': 'plain text', 'outcome': 'Agent does the thing.',
             'constraints': [], 'unknowns': []}
    value.update(overrides)
    return value


def compose(candidate='Do the thing.'):
    return {'status': 'compose', 'candidate': candidate}


def pass_result(**overrides):
    value = {'status': 'pass',
             'case': 'An agent could write before reading the target.',
             'evidence': 'The frame handoff requires reading the target first.',
             'necessity': 'Each retained rule changes behavior: frame gates writing.',
             'removed': [], 'unresolved': []}
    value.update(overrides)
    return value


def revise(**overrides):
    value = {'status': 'revise',
             'case': 'An agent could skip the frame handoff.',
             'evidence': 'Nothing prevents drafting from the request alone.',
             'fix': 'Require the frame result before compose.'}
    value.update(overrides)
    return value


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def start(self, request='Refine a prompt.'):
        result = run(self.root, '--request', request)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_state(self.root)['phase'], 'frame')

    def done(self, payload):
        result = run(self.root, 'done', read_state(self.root)['ticket'], payload=payload)
        return result

    def test_pass_completes_without_writing_target(self):
        self.start()
        self.assertEqual(self.done(frame()).returncode, 0)
        self.assertEqual(self.done(compose()).returncode, 0)
        result = self.done(pass_result(removed=['Delete the redundant rule.']))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('DONE', result.stdout)
        self.assertIn('Write only out.txt', result.stdout)
        self.assertIn('Delete the redundant rule.', result.stdout)
        self.assertFalse((self.root / 'out.txt').exists())
        self.assertEqual(read_state(self.root)['phase'], 'complete')

    def test_review_output_never_writes(self):
        self.start()
        self.assertEqual(self.done(frame(operation='review', target='SKILL.md')).returncode, 0)
        self.assertEqual(self.done(compose('Finding.')).returncode, 0)
        result = self.done(pass_result())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Review never writes', result.stdout)
        self.assertFalse((self.root / 'SKILL.md').exists())

    def test_pathless_output_is_inline(self):
        self.start()
        self.assertEqual(self.done(frame(target='')).returncode, 0)
        self.assertEqual(self.done(compose()).returncode, 0)
        result = self.done(pass_result())
        self.assertIn('Return the instruction inline', result.stdout)

    def test_two_revisions_then_stop_with_unresolved_risk(self):
        self.start()
        self.assertEqual(self.done(frame()).returncode, 0)
        self.assertEqual(self.done(compose('v1')).returncode, 0)
        result = self.done(revise())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_state(self.root)['phase'], 'compose')
        self.assertEqual(read_state(self.root)['passes'], 1)
        self.assertEqual(self.done(compose('v2')).returncode, 0)
        self.assertEqual(self.done(revise()).returncode, 0)
        self.assertEqual(read_state(self.root)['passes'], 2)
        self.assertEqual(self.done(compose('v3')).returncode, 0)
        result = self.done(revise(case='A third defect remains.', evidence='No further revision is allowed.',
                                  fix='Resolve later.'))
        self.assertEqual(result.returncode, 0, result.stderr)
        state = read_state(self.root)
        self.assertEqual(state['phase'], 'complete')
        self.assertEqual(state['passes'], 2)
        self.assertIn('STOP: two revision passes exhausted', result.stdout)
        self.assertIn('A third defect remains.', result.stdout)

    def test_early_target_write_is_rejected(self):
        self.start()
        self.assertEqual(self.done(frame()).returncode, 0)
        (self.root / 'out.txt').write_text('written too early', encoding='utf-8')
        self.assertEqual(self.done(compose()).returncode, 0)
        result = self.done(pass_result())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('target changed before challenge pass', result.stderr)
        self.assertEqual(read_state(self.root)['phase'], 'challenge')

    def test_placeholder_pass_is_rejected(self):
        self.start()
        self.assertEqual(self.done(frame()).returncode, 0)
        self.assertEqual(self.done(compose()).returncode, 0)
        result = self.done(pass_result(case='none', evidence='none', necessity='none'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_state(self.root)['phase'], 'challenge')

    def test_stale_ticket_is_rejected(self):
        self.start()
        result = run(self.root, 'done', '0' * 32, payload=frame())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Resume:', result.stderr)
        self.assertNotIn('--request', result.stderr)
        self.assertEqual(read_state(self.root)['phase'], 'frame')

    def test_out_of_phase_result_is_rejected(self):
        self.start()
        result = self.done(compose())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_state(self.root)['phase'], 'frame')

    def test_active_request_is_refused_but_completed_run_can_restart(self):
        self.start()
        result = run(self.root, '--request', 'Different request.')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.done(frame()).returncode, 0)
        self.assertEqual(self.done(compose()).returncode, 0)
        self.assertEqual(self.done(pass_result()).returncode, 0)
        result = run(self.root, '--request', 'Different request.')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_state(self.root)['phase'], 'frame')
        self.assertEqual(read_state(self.root)['request'], 'Different request.')

    def test_corrupt_state_fails_closed(self):
        (self.root / '.agents').mkdir()
        (self.root / STATE).write_text('{}', encoding='utf-8')
        result = run(self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ERROR:', result.stderr)


if __name__ == '__main__':
    unittest.main()
