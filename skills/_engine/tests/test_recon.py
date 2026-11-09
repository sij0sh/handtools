"""Shared reconnaissance (G5): records, journal recording, invalidation, queries, collectors.

Fixtures: tests/fixtures/recon/{orders,billing} and expected-map.json at the repo root.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS))
from _engine import events, recordings  # noqa: E402
from _engine.recon import collect, query, records, reduce, store  # noqa: E402

FIXTURES = SKILLS.parent / 'tests' / 'fixtures' / 'recon'
EXPECTED = json.loads((FIXTURES / 'expected-map.json').read_text())
CLI = SKILLS / '_engine' / 'recon' / 'cli.py'


def ev(path, statement, source='.', lines=None):
    out = {'source': source, 'path': path, 'statement': statement}
    return dict(out, lines=lines) if lines else out


def repo_records():
    """What an agent verifies in orders alone (repository-only mode)."""
    return [
        {'id': 'component:orders/api', 'classification': 'observed', 'responsibility': 'HTTP order intake',
         'sources': ['app/api.py'], 'entrypoints': ['POST /orders'],
         'evidence': [ev('app/api.py', 'Flask route POST /orders saves and publishes', lines='8-15')]},
        {'id': 'component:orders/events', 'classification': 'observed', 'responsibility': 'publishes order events',
         'sources': ['app/events.py'], 'evidence': [ev('app/events.py', 'KafkaProducer sends orders.created')]},
        {'id': 'contract:http:POST /orders', 'classification': 'observed', 'direction': 'inbound',
         'producers': [{'unresolved': 'producer of contract:http:POST /orders'}], 'consumers': ['component:orders/api'],
         'evidence': [ev('app/api.py', 'route accepts JSON with items; 400 without')]},
        {'id': 'contract:http:GET https://feeds.example-vendor.com/v2/prices.csv', 'classification': 'observed',
         'direction': 'outbound', 'producers': [{'external': 'example-vendor price feed'}],
         'evidence': [ev('app/ingest.py', 'urlopen(FEED) with 30s timeout, no retry')]},
        {'id': 'contract:schedule:ingest-prices', 'classification': 'configured', 'direction': 'inbound',
         'evidence': [ev('deploy/cron.yaml', 'CronJob schedule "0 * * * *" runs orders-ingest')]},
        {'id': 'contract:queue:orders.created', 'classification': 'observed', 'direction': 'outbound',
         'producers': ['component:orders/events'], 'consumers': [{'unresolved': 'consumer of contract:queue:orders.created'}],
         'schema': 'order_created.v1',
         'evidence': [ev('app/events.py', "producer.send('orders.created', ...)")]},
        {'id': 'contract:schema:order_created.v1', 'classification': 'declared', 'direction': 'both',
         'evidence': [ev('schemas/order_created.v1.json', 'requires order_id, total_cents, currency')]},
        {'id': 'contract:table:orders', 'classification': 'observed', 'direction': 'internal',
         'evidence': [ev('migrations/001_create_orders.sql', 'CREATE TABLE orders')]},
        {'id': 'contract:table:prices', 'classification': 'observed', 'direction': 'internal',
         'evidence': [ev('migrations/001_create_orders.sql', 'CREATE TABLE prices')]},
        {'id': 'rel:conforms-to:contract:queue:orders.created->contract:schema:order_created.v1',
         'classification': 'declared', 'relation': 'conforms-to', 'from': 'contract:queue:orders.created',
         'to': 'contract:schema:order_created.v1',
         'evidence': [ev('app/events.py', "SCHEMA = 'schemas/order_created.v1.json'")]},
        {'id': 'gap:orders-created-consumers', 'classification': 'unknown',
         'question': 'Who consumes orders.created?', 'searched': 'orders repository',
         'missing': 'subscriber repositories or broker ACLs', 'consequence': 'payload changes may break unknown consumers',
         'next_lookup': 'ask for the consumer repositories', 'affected': ['contract:queue:orders.created']},
        {'id': EXPECTED['inferred_pattern']['id'], 'classification': 'inferred',
         'claim': EXPECTED['inferred_pattern']['claim'], 'evidence': [ev('app/events.py', 'one publish_order_created')]},
    ]


def billing_records():
    return [
        {'id': 'component:billing/consumer', 'classification': 'observed', 'responsibility': 'invoices new orders',
         'evidence': [ev('billing/consumer.py', "subscribe(['orders.created'])", 'billing')]},
        {'id': 'contract:queue:orders.created', 'classification': 'observed', 'direction': 'outbound',
         'producers': ['component:orders/events'], 'consumers': ['component:billing/consumer'],
         'schema': 'order_created.v1',
         'evidence': [ev('app/events.py', "producer.send('orders.created', ...)"),
                      ev('billing/consumer.py', 'subscribes to orders.created', 'billing')]},
        {'id': 'gap:orders-created-consumers', 'drop': True, 'reason': 'billing supplied; other consumers out of scope'},
        {'id': 'obs:billing-requires-total-cents', 'classification': 'observed',
         'claim': 'billing reads order_id and total_cents and dedupes by order_id',
         'depends_on': ['contract:schema:order_created.v1'],
         'evidence': [ev('billing/consumer.py', "event['total_cents'], event['order_id']", 'billing')]},
    ]


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / 'orders'
        self.billing = self.tmp / 'billing'
        shutil.copytree(FIXTURES / 'orders', self.root)
        shutil.copytree(FIXTURES / 'billing', self.billing)
        env = patch.dict(os.environ, {'HANDTOOLS_STATE': str(self.tmp / 'state')})
        env.start()
        self.addCleanup(env.stop)

    def rid(self):
        return str(uuid.uuid4())

    def snapshot(self, batches, related=None, close=True, budgets=None):
        run = store.start(self.root, self.rid(), related, budgets=budgets)['run_id']
        rev = 1
        for recs in batches:
            rev = store.record(self.root, run, {'records': recs, 'cost': {'files': 3, 'bytes': 900}},
                               rev, self.rid())['revision']
        if close:
            store.close(self.root, run, rev, self.rid())
        return run


class RecordTests(Base):
    def test_repository_only_leaves_consumer_unknown_with_a_gap(self):
        run = self.snapshot([repo_records()])
        state = store.read(self.root, run)[0]
        result = query.consumers(state, 'contract:queue:orders.created')
        self.assertEqual(result['consumers'], ['unresolved: consumer of contract:queue:orders.created'])
        self.assertNotIn('none', json.dumps(result).lower())
        self.assertEqual([g['affected'] for g in query.gaps(state)], [EXPECTED['repo_only']['gap_affects']])
        self.assertIn('contract:queue:orders.created', query.summary(state)['contracts_with_unknown_endpoints'])
        for c in query.contracts(state):  # unknown details stay unknown
            self.assertEqual(c['owner'], 'unknown')
        ids = {c['id'] for c in query.contracts(state)}
        self.assertEqual(ids, {c['id'] for c in EXPECTED['contracts']})
        for ref in state['records']['contract:table:orders']['evidence']:
            self.assertEqual(len(ref['sha256']), 64)  # the recorder pinned the content

    def test_supplying_the_consumer_repository_resolves_it(self):
        run = self.snapshot([repo_records(), billing_records()], related={'billing': str(self.billing)})
        state = store.read(self.root, run)[0]
        self.assertEqual(query.consumers(state, 'contract:queue:orders.created')['consumers'],
                         [EXPECTED['with_billing']['resolved']['contract:queue:orders.created']])
        self.assertEqual(query.gaps(state), [])
        self.assertIn('gap:orders-created-consumers', state['dropped'])
        down = query.neighbors(state, 'component:orders/events', 'downstream', 2)
        self.assertIn('component:billing/consumer', {e['to'] for e in down['edges']})
        up = query.neighbors(state, 'component:billing/consumer', 'upstream', 2)
        self.assertIn('component:orders/events', {e['from'] for e in up['edges']})
        superseded = state['records']['contract:queue:orders.created']['supersedes']
        self.assertEqual(len(superseded), 1)  # history kept, never rewritten

    def test_related_evidence_needs_a_supplied_root(self):
        run = store.start(self.root, self.rid())['run_id']
        with self.assertRaisesRegex(ValueError, 'not a snapshot root'):
            store.record(self.root, run, {'records': billing_records()[:1]}, 1, self.rid())

    def test_inferred_pattern_never_becomes_a_decision(self):
        run = self.snapshot([repo_records()], close=False)
        claim = {'id': 'decision:G1/D1', 'classification': 'declared', 'summary': EXPECTED['inferred_pattern']['claim']}
        with self.assertRaisesRegex(ValueError, 'not an answered decision'):
            store.record(self.root, run, {'records': [claim]}, 2, self.rid())
        with self.assertRaisesRegex(ValueError, 'decision'):
            records.validate_record(dict(claim, id='decision:events-module-per-topic'), hashed=False)
        state = store.read(self.root, run)[0]
        self.assertEqual(query.decisions(state), [])
        self.assertIn(EXPECTED['inferred_pattern']['id'], {o['id'] for o in query.observations(state)})
        adr = self.root / '.agents' / 'design' / 'decisions.json'
        adr.parent.mkdir(parents=True)
        adr.write_text(json.dumps({'version': 1, 'goals': [{'id': 'G1', 'goal': 'g', 'decisions': [
            {'id': 'D1', 'question': 'q', 'answer': 'a'}]}]}))
        store.record(self.root, run, {'records': [claim]}, 2, self.rid())
        self.assertEqual([d['id'] for d in query.decisions(store.read(self.root, run)[0])], ['decision:G1/D1'])

    def test_unknown_fields_are_not_demanded_but_evidence_is(self):
        bare = {'id': 'contract:queue:x', 'classification': 'unknown', 'direction': 'outbound'}
        records.validate_record(bare, hashed=False)
        with self.assertRaisesRegex(ValueError, 'evidence'):
            records.validate_record(dict(bare, classification='observed'), hashed=False)
        with self.assertRaisesRegex(ValueError, 'id must be'):
            records.validate_record({'id': 'rel:calls:a->b', 'classification': 'unknown', 'relation': 'calls',
                                     'from': 'component:x/a', 'to': 'component:x/b'}, hashed=False)
        with self.assertRaisesRegex(ValueError, 'records per batch'):
            records.validate_envelope({'schema': records.SCHEMA, 'version': 1,
                                       'records': [bare] * (records.MAX_RECORDS + 1)}, hashed=False)

    def test_budgets_and_commands_are_enforced(self):
        run = store.start(self.root, self.rid(), budgets={'max_files': 4})['run_id']
        store.record(self.root, run, {'records': repo_records()[:1], 'cost': {'files': 4}}, 1, self.rid())
        with self.assertRaisesRegex(ValueError, 'exceeds the snapshot budget'):
            store.record(self.root, run, {'records': repo_records()[1:2], 'cost': {'files': 1}}, 2, self.rid())
        with self.assertRaisesRegex(ValueError, 'not allowed'):
            store.record(self.root, run, {'records': repo_records()[1:2], 'cost': {'commands': ['pytest']}}, 2,
                         self.rid())
        self.assertEqual(store.status(self.root, run)['cost']['files'], 4)

    def test_closed_snapshot_cannot_advance(self):
        run = self.snapshot([repo_records()])
        with self.assertRaisesRegex(ValueError, 'closed'):
            store.record(self.root, run, {'records': repo_records()[:1]}, 3, self.rid())

    def test_missing_or_moved_evidence_is_refused(self):
        run = store.start(self.root, self.rid())['run_id']
        bad = dict(repo_records()[0], evidence=[ev('app/missing.py', 'x')])
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            store.record(self.root, run, {'records': [bad]}, 1, self.rid())
        escape = dict(repo_records()[0], evidence=[ev('../billing/pyproject.toml', 'x')])
        with self.assertRaisesRegex(ValueError, 'relative'):
            store.record(self.root, run, {'records': [escape]}, 1, self.rid())


class JournalTests(Base):
    def test_retries_and_duplicate_receipts_add_nothing(self):
        run = store.start(self.root, 'start-1')['run_id']
        self.assertEqual(store.start(self.root, 'start-1')['run_id'], run)
        first = store.record(self.root, run, {'records': repo_records()}, 1, 'rec-1')
        self.assertEqual(store.record(self.root, run, {'records': repo_records()}, 1, 'rec-1'), first)
        chain = store.journal(self.root).history(run)
        self.assertEqual(len(chain), 2)
        state, _ = events.replay(chain + [chain[-1], chain[-1]], reduce.REDUCERS)
        self.assertEqual(state, store.read(self.root, run)[0])
        with self.assertRaises(ValueError):
            events.replay([chain[1]], reduce.REDUCERS)  # gap
        fork = dict(chain[1], event_id='fork', request_id='fork')
        with self.assertRaises(ValueError):
            events.replay(chain + [fork], reduce.REDUCERS)

    def test_unsupported_versions_and_missing_reducers_fail_visibly(self):
        run = self.snapshot([repo_records()[:1]], close=False)
        chain = store.journal(self.root).history(run)
        with self.assertRaisesRegex(ValueError, 'no reducer'):
            events.replay(chain)
        newer = dict(chain[1], payload=dict(chain[1]['payload'], version=2))
        with self.assertRaisesRegex(ValueError, 'unsupported handtools.recon version'):
            events.replay([chain[0], newer], reduce.REDUCERS)

    def test_version_1_journal_replays_identically(self):
        golden = json.loads((Path(__file__).parent / 'fixtures' / 'v1-journal.json').read_text())
        self.assertEqual(events.replay(golden['events'])[0], golden['state'])
        self.assertEqual(events.replay(golden['events'], reduce.REDUCERS)[0], golden['state'])

    def test_recon_receipts_are_recognized_in_transcripts(self):
        self.assertTrue(recordings.command_is_engine(
            f'python3 {CLI} --root . record --run snap-1 --expect-revision 1 --request-id x'))
        self.assertFalse(recordings.command_is_engine(f'python3 {CLI} query summary'))
        self.assertFalse(recordings.command_is_engine('python3 /x/other/cli.py record'))

    def test_cli_round_trip_prints_receipts(self):
        env = dict(os.environ)
        def run(*args, stdin=None):
            out = subprocess.run([sys.executable, str(CLI), '--root', str(self.root), *args], input=stdin,
                                 capture_output=True, text=True, env=env)
            self.assertEqual(out.returncode, 0, out.stderr)
            return json.loads(out.stdout)
        started = run('start', '--request-id', 'a', '--depth', 'map')
        self.assertEqual((started['protocol'], started['run_id']), (events.PROTOCOL, 'snap-1'))
        receipt = run('record', '--run', 'snap-1', '--expect-revision', '1', '--request-id', 'b',
                      stdin=json.dumps({'records': repo_records()}))
        self.assertEqual(receipt['kind'], 'record.accepted')
        run('close', '--run', 'snap-1', '--expect-revision', '2', '--request-id', 'c')
        self.assertEqual(run('query', 'consumers', '--id', 'contract:queue:orders.created')['consumers'],
                         ['unresolved: consumer of contract:queue:orders.created'])
        self.assertTrue(run('status')['fresh'])


class RefreshTests(Base):
    def test_schema_change_invalidates_dependents_and_reuses_the_rest(self):
        run = self.snapshot([repo_records(), billing_records()], related={'billing': str(self.billing)})
        schema = self.root / EXPECTED['schema_change']['edit']
        schema.write_text(schema.read_text().replace('"currency"]', '"currency", "customer_id"]'))
        self.assertFalse(store.status(self.root, run)['fresh'])
        result = store.refresh(self.root, run, self.rid())
        stale = {s['id'] for s in result['stale']}
        self.assertEqual(stale, set(EXPECTED['schema_change']['stale']))
        state = store.read(self.root, result['run'])[0]
        for rid in EXPECTED['schema_change']['reused']:
            self.assertEqual(state['records'][rid]['status'], 'current', rid)
            self.assertTrue(state['records'][rid]['reused_from'].startswith(run + '@'))
        self.assertEqual(state['snapshot']['predecessor'], f'{run}@{len(store.journal(self.root).history(run))}')
        self.assertIn('billing', state['snapshot']['roots'])
        self.assertEqual(set(store.stale_refs(self.root, run, ['contract:schema:order_created.v1',
                                                               'contract:table:orders'])),
                         {'contract:schema:order_created.v1'})
        # A re-recorded record becomes current again.
        new = dict(repo_records()[6], evidence=[ev('schemas/order_created.v1.json', 'adds customer_id')])
        rev = len(store.journal(self.root).history(result['run']))
        store.record(self.root, result['run'], {'records': [new]}, rev, self.rid())
        self.assertNotIn('contract:schema:order_created.v1',
                         {s['id'] for s in query.stale(store.read(self.root, result['run'])[0])})

    def test_records_without_evidence_go_stale_conservatively(self):
        lone = {'id': 'obs:no-evidence', 'classification': 'unknown', 'claim': 'not yet checked'}
        run = self.snapshot([repo_records() + [lone]])
        (self.root / 'NOTES.txt').write_text('unrelated change')
        stale = {s['id'] for s in store.refresh(self.root, run, self.rid())['stale']}
        self.assertEqual(stale, {'obs:no-evidence'})

    def test_refresh_needs_a_closed_snapshot_and_is_retry_safe(self):
        run = self.snapshot([repo_records()], close=False)
        with self.assertRaisesRegex(ValueError, 'still open'):
            store.refresh(self.root, run, self.rid())
        store.close(self.root, run, 2, self.rid())
        one = store.refresh(self.root, run, 'same')
        self.assertEqual(store.refresh(self.root, run, 'same'), one)
        self.assertEqual(store.runs(self.root), ['snap-1', 'snap-2'])


class CollectorTests(unittest.TestCase):
    def test_candidates_cover_the_expected_contract_channels(self):
        out = collect.candidates({'.': FIXTURES / 'orders', 'billing': FIXTURES / 'billing'})
        found = {(c['kind'], c['source']) for c in out['candidates']}
        for c in EXPECTED['contracts']:
            if c['kind'] == 'schedule':
                continue  # the CronJob gives a schedule, not its name; the agent names it
            with self.subTest(contract=c['id']):
                self.assertTrue(any(x['kind'] == c['kind'] and c['channel'] in x['channel']
                                    for x in out['candidates']), c)
        self.assertIn(('schedule', '.'), found)
        self.assertIn(('queue', 'billing'), found)
        self.assertNotIn('json-schema.org', json.dumps(out['candidates']))

    def test_limits_and_unsupported_languages_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'main.go').write_text('package main\n')
            (Path(tmp) / 'a.py').write_text("x = 1\n")
            out = collect.candidates({'.': tmp}, limits={'max_files': 1})
            self.assertTrue(any('max_files' in g['gap'] for g in out['gaps']))
            out = collect.candidates({'.': tmp})
            self.assertTrue(any('go' in g['gap'] for g in out['gaps']))
        orient = collect.orient({'.': FIXTURES / 'orders'})['roots']['.']['categories']
        self.assertEqual(orient['schemas'], ['schemas/order_created.v1.json'])
        self.assertIn('deploy/cron.yaml', orient['infrastructure'])


if __name__ == '__main__':
    unittest.main()
