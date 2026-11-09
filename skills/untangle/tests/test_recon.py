"""G5/D9/D16: untangle pins a shared recon snapshot, cites its records, reads state from the journal,
blocks a complete report on stale recon citations, and continues a closed audit as a successor."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
SKILLS = HERE.parent
FIXTURES = SKILLS.parent / 'tests' / 'fixtures' / 'recon'
SCRIPT = HERE / 'scripts' / 'workflow.py'
sys.path.insert(0, str(SKILLS))
from _engine.recon import store  # noqa: E402

BUDGETS = {'dissect_transitions': 30, 'max_units': 10, 'passes_per_unit': 3, 'split_depth': 2,
           'synth_reopens': 2, 'challenge_rounds': 2}


def ev(path, statement, source='.'):
    return [{'source': source, 'path': path, 'statement': statement}]


RECORDS = [
    {'id': 'component:orders/events', 'classification': 'observed', 'responsibility': 'publishes order events',
     'evidence': ev('app/events.py', 'KafkaProducer')},
    {'id': 'component:billing/consumer', 'classification': 'observed', 'responsibility': 'invoices orders',
     'evidence': ev('billing/consumer.py', 'subscribes', 'billing')},
    {'id': 'contract:queue:orders.created', 'classification': 'observed', 'direction': 'outbound',
     'producers': ['component:orders/events'], 'consumers': ['component:billing/consumer'],
     'evidence': ev('app/events.py', "send('orders.created')") + ev('billing/consumer.py', 'subscribe', 'billing')},
    {'id': 'contract:schema:order_created.v1', 'classification': 'declared', 'direction': 'both',
     'evidence': ev('schemas/order_created.v1.json', 'required fields')},
    {'id': 'obs:billing-requires-total-cents', 'classification': 'observed',
     'claim': 'billing reads order_id and total_cents and dedupes by order_id',
     'depends_on': ['contract:schema:order_created.v1'],
     'evidence': ev('billing/consumer.py', "event['total_cents']", 'billing')},
    {'id': 'gap:other-consumers', 'classification': 'unknown', 'question': 'Other orders.created consumers?',
     'searched': 'orders, billing', 'missing': 'broker ACLs', 'consequence': 'unknown breakage',
     'next_lookup': 'ask platform team', 'affected': ['contract:queue:orders.created']},
]
UNITS = [{'id': 'U1', 'responsibility': 'order intake, pricing and events',
          'paths': ['app/api.py', 'app/events.py', 'app/store.py', 'app/__init__.py']},
         {'id': 'U2', 'responsibility': 'price import, schema, migrations and deploy',
          'paths': ['app/ingest.py', 'schemas', 'migrations', 'deploy']},
         {'id': 'U3', 'responsibility': 'project metadata', 'paths': ['pyproject.toml', 'README.md']}]
CONSTRAINT = {'what': 'orders.created keeps order_id and total_cents; billing dedupes on order_id',
              'status': 'contractual',
              'recon_refs': ['contract:queue:orders.created', 'obs:billing-requires-total-cents']}


def finding(fid, where, refs):
    return {'id': fid, 'where': where, 'summary': 'publish after commit has no failure handling',
            'mechanism': 'send() result is ignored', 'evidence': 'observed',
            'policy': {'tier': 'default', 'source': 'defaults.md'}, 'track': 'gap',
            'option': 'decide delivery guarantee with the billing owner', 'recon_refs': refs}


class UntangleRecon(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root, self.billing = self.tmp / 'orders', self.tmp / 'billing'
        shutil.copytree(FIXTURES / 'orders', self.root)
        shutil.copytree(FIXTURES / 'billing', self.billing)
        self.env = dict(os.environ, HANDTOOLS_STATE=str(self.tmp / 'state'))
        patcher = patch.dict(os.environ, {'HANDTOOLS_STATE': str(self.tmp / 'state')})
        patcher.start()
        self.addCleanup(patcher.stop)
        run = store.start(self.root, 'u-start', {'billing': str(self.billing)})['run_id']
        store.record(self.root, run, {'records': RECORDS}, 1, 'u-rec')
        store.close(self.root, run, 2, 'u-close')
        self.snap = run

    def run_cmd(self, *args, payload=None, ok=True):
        out = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args],
                             input=json.dumps(payload) if payload is not None else '',
                             capture_output=True, text=True, env=self.env)
        if ok:
            self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout if ok else out.stderr

    def done(self, payload, ok=True):
        return self.run_cmd('done', payload=payload, ok=ok)

    def map_payload(self, **extra):
        return dict({'conventions': [], 'units': UNITS, 'observables': [CONSTRAINT],
                     'entry_points': [{'id': 'E1', 'where': 'app/api.py:8', 'flow': 'POST /orders -> store -> publish',
                                       'recon_refs': ['contract:queue:orders.created']}],
                     'exclusions': [], 'recon_snapshot': self.snap}, **extra)

    def to_scope(self, pin_payload=None):
        out = self.done(pin_payload or self.map_payload())
        self.assertIn('STEP: SCOPE', out)
        rev = json.loads(self.run_cmd('show'))['map_rev']
        return out, rev

    def dissect_all(self, refs_for_u1):
        while True:
            state = json.loads(self.run_cmd('show'))
            if state['phase'] != 'dissect':
                return state['phase']
            head = state['queue'][0]
            item = {**state['units'], **state['flows']}[head]
            body = {'item': head, 'rev': state['rev'], 'findings': []}
            if item['kind'] == 'flow':
                body['trace'] = ['app/api.py:8-15', 'app/events.py:10-12']
            else:
                body['reviewed'] = item['paths']
                if head == 'U1':
                    body['findings'] = [finding('F1', 'app/events.py:10-12', refs_for_u1)]
            self.done(body)

    def publish(self):
        self.assertEqual(self.done({'recommendations': [{'id': 'R1', 'track': 'gap', 'title': 'delivery',
                                                          'findings': ['F1'], 'change': 'agree guarantee',
                                                          'verification': 'owner sign-off',
                                                          'missing_evidence': 'billing tolerance'}],
                                    'dismissed': [], 'waves': [], 'reopen': []}).split('\n')[0], 'STEP: CHALLENGE')
        return self.done({'reviewer': 'self', 'objections': []})

    def test_pin_constraint_staleness_and_successor(self):
        self.run_cmd('start')
        out = self.done({'approved_by_user': True, 'limits': {'max_files': 100, 'max_bytes': 1_000_000}})
        self.assertIn('recon/cli.py', out)
        self.assertIn('Current state (from the journal', out)
        self.assertNotIn('read current.md', out)
        # Map must choose recon explicitly and cite only pinned records.
        bare = self.map_payload()
        del bare['recon_snapshot']
        self.assertIn('recon_none', self.done(bare, ok=False))
        bad = self.map_payload(observables=[dict(CONSTRAINT, recon_refs=['contract:queue:nope'])])
        self.assertIn('not in the pinned snapshot', self.done(bad, ok=False))
        out, rev = self.to_scope()
        self.assertIn(f'## Recon: {self.snap}', out)
        self.assertIn('contract:queue:orders.created [outbound', out)
        self.assertIn('consumers component:billing/consumer', out)
        self.assertIn('gap:other-consumers', out)
        state = json.loads(self.run_cmd('show'))
        self.assertEqual(state['recon'], {'run': self.snap, 'revision': 3})
        self.assertEqual(state['map']['observables'][0]['status'], 'contractual')  # downstream constraint
        self.done({'approved_by_user': True, 'map_rev': rev, 'budgets': BUDGETS, 'allowed_commands': []})
        self.assertEqual(self.dissect_all(['obs:billing-requires-total-cents']), 'synthesize')
        # The consumer changes outside the audit tree: only recon sees it.
        consumer = self.billing / 'billing' / 'consumer.py'
        consumer.write_text(consumer.read_text().replace("event['total_cents']", "event['total_cents'] or 0"))
        refreshed = store.refresh(self.root, self.snap, 'u-refresh')
        self.assertIn('obs:billing-requires-total-cents', {s['id'] for s in refreshed['stale']})
        self.done({'recommendations': [{'id': 'R1', 'track': 'gap', 'title': 'delivery', 'findings': ['F1'],
                                        'change': 'agree guarantee', 'verification': 'owner sign-off',
                                        'missing_evidence': 'billing tolerance'}],
                   'dismissed': [], 'waves': [], 'reopen': []})
        err = self.done({'reviewer': 'self', 'objections': []}, ok=False)
        self.assertIn('cited recon records changed', err)
        self.assertIn('obs:billing-requires-total-cents', err)
        self.assertIn('STEP: CHECKPOINT', self.done({'checkpoint': 'recon stale'}))
        self.assertIn('STEP: INVENTORY', self.done({'approved_by_user': True, 'decision': 'reinventory'}))
        self.done({'approved_by_user': True, 'limits': {'max_files': 100, 'max_bytes': 1_000_000}})
        # Re-record the changed observation in the successor snapshot, close it, pin it.
        new = refreshed['run']
        obs = dict(RECORDS[4], evidence=ev('billing/consumer.py', "total_cents defaults to 0", 'billing'))
        self.assertIn('contract:queue:orders.created', {s['id'] for s in refreshed['stale']})  # cites billing too
        store.record(self.root, new, {'records': [obs, RECORDS[2]]}, refreshed['revision'], 'u-rerec')
        self.assertEqual(store.stale_refs(self.root, new, ['obs:billing-requires-total-cents']), {})
        self.assertIn('different content',  # the old pin's conclusion rests on the previous version
                      store.stale_refs(self.root, self.snap, ['obs:billing-requires-total-cents'])
                      ['obs:billing-requires-total-cents'])
        self.assertEqual(store.stale_refs(self.root, self.snap, ['component:orders/events']), {})
        store.close(self.root, new, refreshed['revision'] + 1, 'u-close2')
        _, rev = self.to_scope(self.map_payload(recon_snapshot=new))
        units = json.loads(self.run_cmd('show', 'units'))
        self.assertEqual(units['U1']['status'], 'pending')  # its finding cited a changed record
        self.assertEqual(units['U2']['status'], 'reviewed')  # unchanged files, no stale citations
        self.done({'approved_by_user': True, 'map_rev': rev, 'budgets': BUDGETS, 'allowed_commands': []})
        self.assertEqual(self.dissect_all(['obs:billing-requires-total-cents']), 'synthesize')
        self.assertIn('DONE', self.publish())
        audit = next(p for p in (self.tmp / 'state' / 'untangle').glob('*/audit-*'))
        report = (audit / 'report.md').read_text()
        self.assertIn('Status: **COMPLETE', report)
        self.assertIn(f'## Recon: {new}', report)
        self.assertIn('Recon completeness does not imply review coverage.', report)
        self.assertTrue((audit / 'audit.json').is_file() and (audit / 'current.md').is_file())  # exports kept
        # A successor audit reuses unchanged reviews.
        self.assertIn('No closed audit', self.run_cmd('start', '--continue', 'audit-nope', ok=False))
        out = self.run_cmd('start', '--continue', audit.name)
        self.assertIn(f'Successor of {audit.name}: 3 reviewed unit(s)', out)
        self.done({'approved_by_user': True, 'limits': {'max_files': 100, 'max_bytes': 1_000_000}})
        self.to_scope(self.map_payload(recon_snapshot=new))
        state = json.loads(self.run_cmd('show'))
        self.assertEqual({k: u['status'] for k, u in state['units'].items()},
                         {'U1': 'reviewed', 'U2': 'reviewed', 'U3': 'reviewed'})
        self.assertEqual(state['predecessor']['audit_id'], audit.name)
        self.assertNotEqual(state['audit_id'], audit.name)
        self.assertIn('F1', state['findings'])

    def test_recon_none_needs_a_reason_and_open_snapshots_are_refused(self):
        self.run_cmd('start')
        self.done({'approved_by_user': True, 'limits': {'max_files': 100, 'max_bytes': 1_000_000}})
        open_run = store.start(self.root, 'u-open')['run_id']
        self.assertIn('is open', self.done(self.map_payload(recon_snapshot=open_run), ok=False))
        none = self.map_payload(observables=[dict(CONSTRAINT, recon_refs=[])],
                                entry_points=[{'id': 'E1', 'where': 'app/api.py:8', 'flow': 'POST'}])
        del none['recon_snapshot']
        self.assertIn('recon_none', self.done(dict(none, recon_none=''), ok=False))
        out = self.done(dict(none, recon_none='library audit; no external contracts in question'))
        self.assertIn('## Recon: none', out)


if __name__ == '__main__':
    unittest.main()
