"""End-to-end contracts for the common interface; standard-library fixtures only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from helper import continuations
from helper.engine import SQLiteQuery
from helper.runtime import Runtime, Request, parser, normalize


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root/'repo'
        self.repo.mkdir()
        self.cache = self.root/'cache'
        (self.repo/'core.py').write_text('def save(value):\n    return value\n')
        (self.repo/'app.py').write_text('from core import save\n\ndef run():\n    return save(3)\n')
        self.recording = self.root/'fixture.jsonl'
        self.records = [
            {'type': 'session', 'id': 'fixture', 'cwd': str(self.repo)},
            {'type': 'message', 'id': 'u1', 'message': {'role': 'user', 'content': 'Please fix core.py save.'}},
            {'type': 'message', 'id': 'a1', 'parentId': 'u1', 'message': {'role': 'assistant', 'content': 'Inspect callers before changing core.py.'}},
        ]
        self.write_records()

    def tearDown(self):
        self.temp.cleanup()

    def write_records(self):
        self.recording.write_text(''.join(json.dumps(r)+'\n' for r in self.records))

    def cli(self, *args, ok=True, stdin=None, cwd=None):
        p = subprocess.run([sys.executable, str(ROOT/'scripts/remember.py'), *map(str,args),
                            '--repo', str(self.repo), '--cache', str(self.cache)],
                           input=stdin, capture_output=True, text=True, cwd=cwd, timeout=30)
        self.assertEqual(p.returncode, 0 if ok else 2, p.stderr+p.stdout)
        self.assertFalse(p.stderr, p.stderr)
        return json.loads(p.stdout)

    def test_constant_and_cte_need_no_providers(self):
        out = self.cli('query', "WITH events(x) AS (VALUES ('files')) SELECT x FROM events")
        self.assertEqual(out['results'], [{'x':'files'}])
        self.assertEqual(out['scope']['providers'], [])
        self.assertFalse(self.cache.exists())

    def test_plan_compiles_nested_aliases_quoted_names_and_parameters(self):
        out = self.cli('query', 'WITH chosen AS (SELECT path FROM "files" WHERE size > $n) SELECT * FROM chosen', '--param', 'n=0', '--plan')
        self.assertEqual(out['plan']['providers'], ['graph'])
        self.assertEqual(set(out['plan']['tables']['files']), {'path','size'})
        self.assertFalse(self.cache.exists())

    def test_unknown_table_fails_before_scanning(self):
        out = self.cli('query', 'SELECT * FROM evnts', ok=False)
        self.assertIn('describe TABLE', out['error'])
        self.assertFalse(self.cache.exists())

    def test_unknown_column_fails_before_scanning(self):
        self.cli('query', 'SELECT not_a_column FROM files', ok=False)
        self.assertFalse(self.cache.exists())

    def test_readonly_and_single_statement(self):
        for sql in ['DELETE FROM files', 'DROP TABLE files', "ATTACH ':memory:' AS x", 'PRAGMA user_version',
                    "SELECT load_extension('x')", 'SELECT 1; SELECT 2']:
            with self.subTest(sql=sql): self.cli('query', sql, ok=False)

    def test_source_ordinary_directory_without_optional_packages(self):
        out = self.cli('query', 'SELECT path, content FROM files ORDER BY path')
        self.assertEqual([r['path'] for r in out['results']], ['app.py','core.py'])
        self.assertEqual(out['scope']['providers'], ['graph'])
        self.assertEqual(out['status'], 'ok')

    def test_symbol_graph_reused_for_code_items(self):
        out = self.cli('query', "SELECT f.path, s.qualname FROM files f JOIN code_items s USING(path) WHERE s.qualname='save'")
        self.assertEqual(out['results'], [{'path':'core.py','qualname':'save'}])
        self.assertEqual(out['scope']['providers'], ['graph'])

    def test_custom_join_without_clipping(self):
        data = self.root/'owners.json'
        data.write_text(json.dumps([{'path':'core.py','owner':'A'}, {'path':'app.py','owner':'B'}]))
        out = self.cli('query', 'SELECT count(*) AS n FROM files JOIN owners USING(path)', '--input', f'owners={data}', '--limit','1')
        self.assertEqual(out['results'], [{'n':2}])
        self.assertEqual(out['status'],'partial')  # external completeness unknown

    def test_empty_custom_table_has_schema(self):
        data = self.root/'empty.json';data.write_text('[]')
        out = self.cli('query', 'SELECT count(*) AS n FROM custom', '--input', f'custom={data}', '--type','custom.path=TEXT')
        self.assertEqual(out['results'], [{'n':0}])
        self.cli('query', 'SELECT * FROM custom', '--input', f'custom={data}', ok=False)

    def test_custom_name_collision(self):
        self.cli('query', 'SELECT 1', '--input', 'FILES=unused.json', ok=False)

    def test_external_page_coverage_survives_join(self):
        data = self.root/'page.json';data.write_text(json.dumps({'schema_version':1,'results':[{'x':1}], 'omissions':{'selection':5}}))
        out=self.cli('query','SELECT count(*) AS n FROM supplied','--input',f'supplied={data}')
        self.assertEqual(out['results'],[{'n':1}]);self.assertEqual(out['status'],'partial')
        self.assertTrue(out['delivery']['complete'])

    def test_events_auto_load_without_include(self):
        out=self.cli('query',"SELECT text, ref FROM events WHERE role='user'",'--recordings',self.recording)
        self.assertEqual(out['scope']['providers'],['recordings'])
        self.assertIn('Please fix',out['results'][0]['text'])
        self.assertIsInstance(out['results'][0]['ref'],dict)
        self.assertFalse(self.cache.exists())

    def test_mixed_query_transient(self):
        out=self.cli('query',"SELECT e.text, f.path FROM events e JOIN files f ON instr(e.text, f.path)>0",'--recordings',self.recording)
        self.assertEqual(len(out['results']),2)
        for p in self.cache.rglob('*.json'):
            self.assertNotIn('Please fix core.py save.',p.read_text())
        self.assertFalse(list(self.cache.rglob('report-*')))

    def test_query_output_pages_stable_source_snapshot(self):
        first=self.cli('query','SELECT path FROM files ORDER BY path','--limit','1')
        (self.repo/'new.py').write_text('x=1')
        token=first['next'][0]['ref']
        last=self.cli('show',token)
        self.assertEqual(last['results'],[{'path':'core.py'}])
        self.assertTrue(last['delivery']['complete'])

    def test_changed_custom_input_rejects_continuation(self):
        data=self.root/'rows.json';data.write_text('[{"x":1},{"x":2}]')
        out=self.cli('query','SELECT * FROM custom ORDER BY x','--input',f'custom={data}','--limit','1')
        data.write_text('[{"x":1},{"x":3}]')
        err=self.cli('show',out['next'][0]['ref'],ok=False)
        self.assertIn('source changed',err['error'])

    def test_changed_recording_rejects_continuation(self):
        out=self.cli('query','SELECT text FROM events','--recordings',self.recording,'--limit','1')
        self.records.append({'type':'message','id':'u2','message':{'role':'user','content':'Another request'}})
        self.write_records()
        self.assertIn('source changed',self.cli('show',out['next'][0]['ref'],ok=False)['error'])

    def test_continuation_presentation_override(self):
        first=self.cli('query','SELECT path FROM files ORDER BY path','--limit','1')
        last=self.cli('show',first['next'][0]['ref'],'--limit','10')
        self.assertEqual(len(last['results']),1)
        self.assertTrue(last['delivery']['complete'])

    def test_continuation_schema_rejects_unknown_version_or_operation(self):
        bad=continuations.encode(['query','SELECT 1'])['ref']
        self.assertEqual(continuations.decode(bad)['version'],1)
        bad=continuations.encode(['raw','oops'])['ref']
        self.cli('show',bad,ok=False)

    def test_inspect_plan_reads_nothing(self):
        out=self.cli('inspect','core.py','--plan')
        self.assertEqual(len(out['results']),5)
        self.assertFalse(self.cache.exists())

    def test_inspect_collects_source_consumers_history_and_evidence(self):
        out=self.cli('inspect','core.py','--recordings',self.recording,'--max-bytes','50000')
        sections={r['section'] for r in out['results']}
        self.assertTrue({'source','relationships','history','evidence'}<=sections, out)
        self.assertTrue(any(r.get('path')=='app.py' for r in out['results']))
        self.assertFalse(list(self.cache.rglob('report-*')))
        for p in self.cache.rglob('*.json'):self.assertNotIn('Please fix core.py save.',p.read_text())

    def test_inspect_ambiguous_does_not_retrieve_history(self):
        (self.repo/'other.py').write_text('def save(x):\n    return x\n')
        out=self.cli('inspect','save','--recordings',self.recording)
        self.assertEqual(out['coverage']['target']['reason'],'ambiguous')
        self.assertEqual(len(out['results']),2)

    def test_show_session_json_ref(self):
        out=self.cli('query',"SELECT ref FROM events WHERE role='user'",'--recordings',self.recording)
        expanded=self.cli('show',json.dumps(out['results'][0]['ref']))
        self.assertTrue(expanded['results'][0]['selected'])
        self.assertEqual(expanded['results'][0]['text'],'Please fix core.py save.')

    def test_global_options_before_session_verb(self):
        p=subprocess.run([sys.executable,str(ROOT/'scripts/remember.py'),'--repo',str(self.repo),
                          'search',str(self.recording),'--text','core.py'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        self.assertTrue(json.loads(p.stdout)['results'])

    def test_focused_schema_needs_no_source(self):
        out=self.cli('describe','events')
        self.assertIn('recording_id',out['results'][0]['columns'])
        self.assertFalse(self.cache.exists())

    def test_provider_registry_loads_once(self):
        argv=['query','SELECT n.name FROM nodes n JOIN files f USING(path)','--repo',str(self.repo),'--cache',str(self.cache)]
        args=normalize(parser().parse_args(argv),argv)
        from helper import providers
        original=providers.Providers.load_graph
        calls=[]
        def counted(p): calls.append(1);return original(p)
        with patch.object(providers.Providers,'load_graph',counted):Runtime(Request(args,tuple(argv))).execute()
        self.assertEqual(calls,[1])

    def test_sql_timeout(self):
        with SQLiteQuery({},.01) as q:
            q.plan('WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n')
            with self.assertRaisesRegex(ValueError,'interrupted'):q.evaluate()

    def test_unknown_column_types_rejected(self):
        with self.assertRaises(ValueError):SQLiteQuery({'x':{'column':'NOT_A_TYPE'}})

    def test_duplicate_output_names_rejected(self):
        self.cli('query','SELECT 1 AS x, 2 AS x',ok=False)

    def test_stdin_result_does_not_offer_unreplayable_token(self):
        out=self.cli('query','SELECT * FROM supplied','--input','supplied=-','--limit','1',stdin='[{"x":1},{"x":2}]')
        self.assertFalse(out['delivery']['complete'])
        self.assertFalse(out['next'])

    def test_byte_budget_keeps_executable_next(self):
        data=self.root/'large.json';data.write_text(json.dumps([{'x':'a'*5000}]))
        out=self.cli('query','SELECT * FROM supplied','--input',f'supplied={data}','--max-bytes','2048')
        self.assertFalse(out['results'])
        self.assertFalse(out['delivery']['complete'])
        token=out['next'][0]['ref']
        expanded=self.cli('show',token,'--max-bytes','12000')
        self.assertEqual(len(expanded['results'][0]['x']),5000)

    def decoded(self, item):
        return continuations.decode(item['ref'])['argv']

    def test_limited_query_ranks_coverage_recovery_before_paging(self):
        self.records += [{'type':'message','id':f'u{i}','message':{'role':'user','content':f'note {i}'}} for i in range(2,6)]
        self.write_records()
        out=self.cli('query','SELECT text FROM events','--recordings',self.recording,'--max-events','2','--limit','1')
        self.assertEqual(out['status'],'partial')
        self.assertEqual([n['effect'] for n in out['next']],['coverage','delivery'])
        argv=self.decoded(out['next'][0])
        self.assertIn('deep',argv)
        self.assertNotIn('--max-events',argv)
        self.assertNotIn('--offset',argv)
        wide=self.cli('show',out['next'][0]['ref'],'--limit','50')
        self.assertEqual(wide['status'],'ok')
        self.assertGreater(len(wide['results']),2)
        self.assertTrue(wide['coverage']['recordings']['complete'])
        self.assertFalse(any(n['effect']=='coverage' for n in wide['next']))

    def test_inspect_history_follow_up_keeps_recording_scope(self):
        folder=self.root/'many';folder.mkdir()
        for i in range(10):
            (folder/f's{i}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in [
                {'type':'session','id':f's{i}','cwd':str(self.repo)},
                {'type':'message','id':'u1','message':{'role':'user','content':f'Change core.py save, take {i}.'}}]))
        out=self.cli('inspect','core.py','--recordings',folder,'--max-commits','7','--max-bytes','50000')
        follow=next(n for n in out['next'] if n['effect']=='expansion')
        argv=self.decoded(follow)
        self.assertEqual(argv[0],'history')
        self.assertEqual(argv[argv.index('--recordings')+1],str(folder.resolve()))
        self.assertEqual(argv[argv.index('--max-commits')+1],'7')
        self.assertEqual(argv[argv.index('--snapshot')+1],out['scope']['snapshot'])
        history=self.cli('show',follow['ref'],'--max-bytes','50000')
        self.assertGreater(len(history['results']),8)


class RegistryTests(unittest.TestCase):
    def test_every_parser_command_has_one_registered_route(self):
        from helper.operations import OPERATIONS, graph_parser, session_parser
        from helper.runtime import ROUTES
        import argparse
        def commands(p):
            return {n for a in p._actions if isinstance(a, argparse._SubParsersAction) for n in a.choices}
        common, legacy, sessions = commands(graph_parser('common')), commands(graph_parser('legacy')), commands(session_parser())
        self.assertLessEqual(common | legacy, set(OPERATIONS))
        self.assertIn('inspect', common)
        for name in common | legacy:
            self.assertIn(OPERATIONS[name].route, ROUTES)
        self.assertTrue(sessions)

    def test_retained_delivery_refuses_transient_results(self):
        from helper import delivery
        args = parser().parse_args(['map'])
        for doc in ({'operation': 'history', 'scope': {}}, {'operation': 'inspect', 'scope': {}},
                    {'operation': 'query', 'scope': {'retention': 'transient'}}):
            with self.assertRaises(ValueError):
                delivery.retained(None, doc, args)


if __name__ == '__main__':
    unittest.main()
