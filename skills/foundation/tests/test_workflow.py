"""Tests for the stateless workflow CLI and stage checks."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = tempfile.TemporaryDirectory()  # never touch the real ~/.agents/state
os.environ['HANDTOOLS_STATE'] = STATE.name
WORKFLOW = ROOT / 'scripts' / 'workflow.py'

sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT.parent)]  # foundation's stages; handtools' skills/_engine
from workflowlib import steps  # noqa: E402

CAPABILITIES = {key: {'status': 'n/a', 'evidence': 'test fixture'} for key in steps.CAPABILITIES}


def run_workflow(root, *args, payload=None):
    return subprocess.run(
        [sys.executable, str(WORKFLOW), '--root', str(root), *args],
        cwd=root,
        input='' if payload is None else json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


class WorkflowTests(unittest.TestCase):
    def test_start_prints_the_first_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_workflow(Path(tmp), 'start')

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('STEP: DISCOVER', result.stdout)
            self.assertIn('done --stage discover', result.stdout)

    def test_done_requires_a_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_workflow(Path(tmp), 'done')

            self.assertEqual(result.returncode, 1)
            self.assertIn('pass `--stage S`', result.stderr)

    def test_status_is_unavailable_without_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_workflow(Path(tmp), 'status')

            self.assertEqual(result.returncode, 1)
            self.assertIn('Stateless', result.stderr)

    def test_discover_rejects_an_unknown_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_workflow(
                Path(tmp), 'done', '--stage', 'discover',
                payload={'kind': 'library', 'maturity': 'prototype', 'mode': 'plan'},
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn('`kind` must be one of', result.stderr)

    def test_interview_limits_questions_to_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_workflow(
                Path(tmp), 'done', '--stage', 'interview',
                payload={'questions_asked': 6, 'decisions': {}},
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn('`questions_asked` must be an integer from 0 to 5', result.stderr)

    def test_assess_requires_every_capability(self):
        with tempfile.TemporaryDirectory() as tmp:
            incomplete = dict(CAPABILITIES)
            incomplete.pop('adrs')
            result = run_workflow(
                Path(tmp), 'done', '--stage', 'assess',
                payload={'mode': 'plan', 'capabilities': incomplete, 'approved': [], 'run': []},
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn('missing: adrs', result.stderr)

    def test_full_run_ends_when_nothing_is_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            discover = {'kind': 'brownfield', 'maturity': 'prototype', 'mode': 'plan'}
            interview = {'questions_asked': 0, 'decisions': {}}
            assess = {'mode': 'plan', 'capabilities': CAPABILITIES, 'approved': [], 'run': []}

            first = run_workflow(root, 'done', '--stage', 'discover', payload=discover)
            second = run_workflow(root, 'done', '--stage', 'interview', payload=interview)
            third = run_workflow(root, 'done', '--stage', 'assess', payload=assess)

            self.assertIn('STEP: INTERVIEW', first.stdout)
            self.assertIn('STEP: ASSESS', second.stdout)
            self.assertIn('DONE:', third.stdout)

    def test_approved_item_advances_to_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            discover = {'kind': 'brownfield', 'maturity': 'prototype', 'mode': 'plan'}
            interview = {'questions_asked': 0, 'decisions': {}}
            assess = {
                'mode': 'plan',
                'capabilities': CAPABILITIES,
                'approved': ['decisions-record'],
                'run': [],
            }

            run_workflow(root, 'done', '--stage', 'discover', payload=discover)
            run_workflow(root, 'done', '--stage', 'interview', payload=interview)
            result = run_workflow(root, 'done', '--stage', 'assess', payload=assess)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('STEP: APPLY', result.stdout)


if __name__ == '__main__':
    unittest.main()
