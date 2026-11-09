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


class ReconTests(unittest.TestCase):
    """G5/D8: foundation reads a closed recon snapshot and reports external contract gaps."""

    def setUp(self):
        import shutil
        from _engine.recon import store
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'orders'
        shutil.copytree(ROOT.parents[1] / 'tests' / 'fixtures' / 'recon' / 'orders', self.root)
        self.store = store
        self.run_id = store.start(self.root, 'f-start')['run_id']
        ev = lambda path, s: [{'source': '.', 'path': path, 'statement': s}]
        store.record(self.root, self.run_id, {'records': [
            {'id': 'contract:queue:orders.created', 'classification': 'observed', 'direction': 'outbound',
             'consumers': [{'unresolved': 'consumer of contract:queue:orders.created'}],
             'evidence': ev('app/events.py', 'publishes orders.created')},
            {'id': 'contract:schema:order_created.v1', 'classification': 'declared', 'direction': 'both',
             'owner': 'orders team', 'evidence': ev('schemas/order_created.v1.json', 'payload schema')},
            {'id': 'contract:table:orders', 'classification': 'observed', 'direction': 'internal',
             'evidence': ev('migrations/001_create_orders.sql', 'CREATE TABLE orders')}]}, 1, 'f-rec')

    def close(self):
        self.store.close(self.root, self.run_id, 2, 'f-close')

    def assess(self, **extra):
        return dict({'mode': 'audit', 'capabilities': CAPABILITIES, 'approved': [], 'run': [],
                     'recon_snapshot': self.run_id}, **extra)

    def test_discover_prints_the_recon_guide_and_needs_a_closed_snapshot(self):
        start = run_workflow(self.root, 'start')
        self.assertIn('recon/cli.py', start.stdout)
        self.assertIn('unresolved', start.stdout)
        self.assertIn('external-contracts', steps.CAPABILITIES)
        discover = {'kind': 'brownfield', 'maturity': 'mvp', 'mode': 'audit', 'recon_snapshot': self.run_id}
        result = run_workflow(self.root, 'done', '--stage', 'discover', payload=discover)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('still open', result.stderr)
        self.close()
        result = run_workflow(self.root, 'done', '--stage', 'discover', payload=discover)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('query gaps', result.stdout)

    def test_assess_requires_a_gap_for_each_unknown_owner_or_compatibility(self):
        self.close()
        result = run_workflow(self.root, 'done', '--stage', 'assess', payload=self.assess())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('contract:queue:orders.created (compatibility, owner)', result.stderr)
        self.assertIn('contract:schema:order_created.v1 (compatibility)', result.stderr)
        self.assertNotIn('contract:table:orders', result.stderr)  # internal
        gaps = [{'contract': 'contract:queue:orders.created', 'missing': ['owner', 'compatibility'],
                 'recommendation': 'name the owning team and a versioning rule for orders.created'},
                {'contract': 'contract:schema:order_created.v1', 'missing': ['compatibility'],
                 'recommendation': 'state additive-only changes with a version bump'}]
        result = run_workflow(self.root, 'done', '--stage', 'assess', payload=self.assess(contract_gaps=gaps))
        self.assertEqual(result.returncode, 0, result.stderr)
        bogus = gaps + [{'contract': 'contract:queue:missing', 'missing': ['owner'], 'recommendation': 'x'}]
        result = run_workflow(self.root, 'done', '--stage', 'assess', payload=self.assess(contract_gaps=bogus))
        self.assertIn('not contracts in the snapshot', result.stderr)

    def test_foundation_writes_no_recon_state(self):
        self.close()
        before = len(self.store.journal(self.root).history(self.run_id))
        run_workflow(self.root, 'done', '--stage', 'assess', payload=self.assess(contract_gaps=[]))
        self.assertEqual(len(self.store.journal(self.root).history(self.run_id)), before)
        self.assertEqual(self.store.runs(self.root), [self.run_id])


if __name__ == '__main__':
    unittest.main()
