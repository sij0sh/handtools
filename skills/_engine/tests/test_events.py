import copy
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _engine import events, planning, recordings, storage, effects


class EventTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = events.Journal(self.root / 'events.sqlite3')

    def test_retry_revision_and_conflicting_request(self):
        first = self.store.append('r', 'run.started', {'goal': 'x'}, 0, 'request')
        self.assertEqual(self.store.append('r', 'run.started', {'goal': 'x'}, 0, 'request'), first)
        self.assertEqual(len(self.store.history('r')), 1)
        with self.assertRaisesRegex(ValueError, 'different payload'):
            self.store.append('r', 'run.started', {'goal': 'y'}, 0, 'request')
        with self.assertRaisesRegex(ValueError, 'stale revision'):
            self.store.append('r', 'stage.completed', {}, 0)

    def test_gaps_forks_and_identity_collisions(self):
        a = self.store.append('r', 'run.started', {}, 0)
        b = self.store.append('r', 'stage.completed', {'result': 'x'}, 1)
        self.assertEqual(events.replay([b, a, a])[0], {'result': 'x'})
        for chain in ([b], [a, {**b, 'parent_event_id': 'missing'}],
                      [a, b, {**b, 'event_id': 'fork', 'request_id': 'fork'}],
                      [a, {**a, 'payload': {'changed': True}}]):
            with self.assertRaises(ValueError): events.replay(chain)

    def test_closed_run_cannot_advance(self):
        self.store.append('r', 'run.started', {}, 0)
        self.store.append('r', 'run.closed', {'result': 'done'}, 1)
        with self.assertRaisesRegex(ValueError, 'closed'):
            self.store.append('r', 'stage.completed', {}, 2)

    def test_unknown_schema_and_policy_rejected(self):
        item = events.event('r', 1, None, 'run.started', {})
        for key in ('schema_version', 'workflow_version', 'policy_version'):
            with self.assertRaises(ValueError): events.replay([{**item, key: '999'}])

    def test_legacy_migration_keeps_backup_and_journal_authority(self):
        path = self.root / 'workflow.json'
        path.write_text('{"phase":"old"}')
        self.assertEqual(storage.read_state(path)['phase'], 'old')
        storage.write_state(path, {'phase': 'new'})
        self.assertFalse(path.exists())
        self.assertTrue(path.with_suffix('.json.migrated').exists())
        path.write_text('{"phase":"stale"}')
        self.assertEqual(storage.read_state(path)['phase'], 'new')
        self.assertEqual(len(self.store.history('workflow.json')), 2)

    def test_read_does_not_create_state_or_emit_events(self):
        absent = events.Journal(self.root / 'absent' / 'events.sqlite3')
        self.assertIsNone(absent.read('missing'))
        self.assertFalse(absent.path.exists())
        self.store.put('r', {'x': 1})
        for _ in range(3): self.store.read('r')
        self.assertEqual(len(self.store.history('r')), 1)

    def test_three_harnesses_exact_receipts(self):
        item = events.event('r', 1, None, 'run.started', {'goal': 'x'})
        command = {'command': 'python3 /bundle/skills/_engine/engine.py start --run r'}
        forms = [
            [{'type':'response_item','payload':{'type':'function_call','name':'exec_command','call_id':'c','arguments':json.dumps(command)}},
             {'type':'response_item','payload':{'type':'function_call_output','call_id':'c','output':json.dumps(item)}}],
            [{'type':'assistant','message':{'content':[{'type':'tool_use','id':'c','name':'Bash','input':command}]}},
             {'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':'c','content':json.dumps(item)}]}}],
            [{'type':'message','message':{'role':'assistant','content':[{'type':'toolCall','id':'c','name':'bash','arguments':command}]}},
             {'type':'message','message':{'role':'toolResult','toolCallId':'c','isError':False,'content':[{'type':'text','text':json.dumps(item)}]}}]]
        for i, rows in enumerate(forms):
            path = self.root / ('session%s.jsonl' % i)
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            result = recordings.receipts([path], 'r')
            self.assertEqual(result[0]['event_id'], item['event_id'])
            self.assertIn('source_ref', result[0])

    def test_examples_are_not_receipts_and_truncated_recording_is_unknown(self):
        path = self.root / 's.jsonl'
        item = events.event('r', 1, None, 'run.started', {})
        path.write_text(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':json.dumps(item)}]}})+'\n')
        self.assertEqual(recordings.receipts([path], 'r'), [])
        path.write_text('{"type":')
        with self.assertRaisesRegex(ValueError, 'incomplete recording'):
            recordings.receipts([path], 'r')
        self.assertFalse(recordings.command_is_engine('echo python3 engine.py start'))


class TranscriptCli(unittest.TestCase):
    def test_live_receipt_roundtrip_retry_and_missing_tail(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); script = Path(__file__).resolve().parents[1] / 'engine.py'
            prefix = [sys.executable, str(script), '--root', str(root), '--backend', 'transcript']
            def call(args, payload=None):
                return subprocess.run(prefix+args, input=json.dumps(payload) if payload is not None else '',
                                      capture_output=True, text=True)
            first = call(['start','--run','r','--expect-revision','0','--request-id','a'], {'goal':'x'})
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt = json.loads(first.stdout)
            path = root / 'session.jsonl'
            def capture(args, output, cid):
                rows = [{'type':'response_item','payload':{'type':'function_call','call_id':cid,
                         'arguments':json.dumps({'cmd': ' '.join(prefix+args)})}},
                        {'type':'response_item','payload':{'type':'function_call_output','call_id':cid,'output':output}}]
                with path.open('a') as out:
                    for row in rows: out.write(json.dumps(row)+'\n')
            capture(['start','--run','r'], first.stdout, 'c1')
            args = ['--recording',str(path),'append','--run','r','--expect-revision','1','--head',receipt['event_id'],'--request-id','b']
            second = call(args, {'answer':'y'})
            self.assertEqual(second.returncode, 0, second.stderr)
            next_item = json.loads(second.stdout)
            missing = call(['--recording',str(path),'append','--run','r','--expect-revision','2','--head',next_item['event_id'],'--request-id','c'], {})
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn('pending/unknown', missing.stderr)
            capture(args, second.stdout, 'c2')
            # Retrying an already captured request must return its original receipt.
            repeat = call(args, {'answer':'y'})
            self.assertEqual(repeat.returncode, 0, repeat.stderr)
            self.assertEqual(json.loads(repeat.stdout)['event_id'], next_item['event_id'])


class PlanningTests(unittest.TestCase):
    def plan(self):
        return {'goal':'x', 'constraints':[], 'criteria':['observable x'], 'decisions':[],
                'blocking':[], 'verification':'inspect x', 'challenged':True}

    def test_no_choices_ready_and_blocking_prevents_work(self):
        p = self.plan(); self.assertEqual(planning.validate(p), 'ready')
        p['blocking'] = ['unknown intent']
        self.assertEqual(planning.validate(p), 'needs_input')
        with self.assertRaisesRegex(ValueError, 'needs_input'): planning.require_ready(p)

    def test_dependency_cycles_and_unchallenged_plan(self):
        p = self.plan(); p['challenged'] = False
        with self.assertRaises(ValueError): planning.validate(p)
        p['challenged'] = True
        p['decisions'] = [{'id':'a','question':'q','answer':'a','after':['b']},
                          {'id':'b','question':'q','answer':'a','after':['a']}]
        with self.assertRaisesRegex(ValueError, 'cycle'): planning.validate(p)
