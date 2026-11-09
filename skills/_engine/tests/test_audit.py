"""G6/D2, D5, D15, D16: shared audit bookkeeping is domain-free, bounded and verifiable."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _engine.audit import budgets, candidates, evidence, obligations, packs  # noqa: E402


def item(oid, target='a.py', check='general/logic', boundary='library'):
    return {'id': oid, 'target': target, 'boundary': boundary, 'check': check, 'risk': 'r', 'rationale': 'why'}


class AuditTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'a.py').write_text('x = 1\n')
        (self.root / 'b.go').write_text('package b\n')
        self.catalog = packs.load(packs.available())

    def test_packs_are_valid_and_report_unsupported_languages(self):
        self.assertEqual(packs.available(), ['general', 'python', 'tests'])
        self.assertTrue(all(c['version'] == 1 for c in self.catalog.values()))
        self.assertEqual(packs.unsupported(['a.py', 'b.go', 'README.md'], self.catalog), ['go'])
        with self.assertRaises(ValueError):
            packs.validate({'pack': 'x', 'version': 1, 'checks': [{'id': 'y/z'}]}, 'x')

    def test_obligations_need_applicable_checks_unique_ids_and_a_cap(self):
        obls, used = {}, set()
        obligations.add(obls, [item('O1'), item('O2', 'a.py', 'python/numeric')], self.catalog, 'diff', 3, used, 'T')
        with self.assertRaisesRegex(ValueError, 'does not apply'):
            obligations.add(obls, [item('O3', 'b.go', 'python/numeric')], self.catalog, 'diff', 3, used, 'T')
        with self.assertRaisesRegex(ValueError, 'already has'):
            obligations.add(obls, [item('O4')], self.catalog, 'diff', 3, used, 'T')
        with self.assertRaisesRegex(ValueError, 'never reused'):
            obligations.add(obls, [item('O1', 'b.go')], self.catalog, 'diff', 3, used, 'T')
        with self.assertRaisesRegex(ValueError, 'exceed'):
            obligations.add(obls, [item('O5', 'b.go'), item('O6', 'c.py')], self.catalog, 'diff', 3, used, 'T')
        self.assertEqual(obligations.queue(obls), ['O1', 'O2'])

    def test_examined_needs_check_outcome_and_matching_refs(self):
        obls = {}
        obligations.add(obls, [item('O1')], self.catalog, 'subsystem', 5, set(), 'T')
        o = obls['O1']
        with self.assertRaisesRegex(ValueError, 'examined needs `outcome`'):
            obligations.resolve(o, {'status': 'examined'}, self.root, [], 'T')
        report = {'status': 'examined', 'outcome': {'performed': 'read', 'result': 'no-issue', 'refs': []},
                  'evidence': [{'path': 'a.py', 'statement': 'x'}]}
        with self.assertRaisesRegex(ValueError, 'exactly the candidates'):
            obligations.resolve(o, report, self.root, ['C1'], 'T')
        obligations.resolve(o, report, self.root, [], 'T')
        self.assertEqual(o['status'], 'examined')
        self.assertEqual(len(o['evidence'][0]['sha256']), 64)
        obligations.reopen(o, 'drift')
        self.assertEqual((o['status'], 'outcome' in o), ('planned', False))

    def test_candidates_settle_only_through_the_workflow_judge(self):
        cands, used = {}, set()
        c = {'id': 'C1', 'expected': 'e', 'actual': 'a', 'trigger': 't',
             'sources': [{'path': 'a.py', 'statement': 'x'}]}
        candidates.propose(cands, c, 'O1', self.root, used, 'T')
        with self.assertRaisesRegex(ValueError, 'never reused'):
            candidates.propose(cands, c, 'O1', self.root, used, 'T')
        cand = cands['C1']
        candidates.attempt(cand, {'method': 'run', 'outcome': 'tool-failed', 'note': 'n'}, [], 1, 'T')
        self.assertEqual(cand['state'], 'validating')
        with self.assertRaisesRegex(ValueError, 'attempts_per_candidate'):
            candidates.attempt(cand, {'method': 'run', 'outcome': 'supports', 'note': 'n'}, [], 1, 'T')
        seen = []
        candidates.settle(cand, {'state': 'unresolved'}, lambda c, v, w: seen.append(v) or {'state': 'unresolved', 'refs': []}, 'T')
        self.assertEqual((cand['state'], len(seen)), ('unresolved', 1))
        with self.assertRaisesRegex(ValueError, 'already'):
            candidates.settle(cand, {'state': 'confirmed'}, lambda c, v, w: {}, 'T')

    def test_evidence_hashes_working_tree_and_commits(self):
        def git(*a):
            return subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=t', '-c', 'user.email=t@e', *a],
                                  check=True, capture_output=True, text=True).stdout.strip()
        git('init', '-q')
        git('add', '-A')
        git('commit', '-qm', 'one')
        sha = git('rev-parse', 'HEAD')
        (self.root / 'a.py').write_text('x = 2\n')
        refs = evidence.hash_refs(self.root, [{'path': 'a.py', 'statement': 'now'},
                                              {'path': 'a.py', 'statement': 'then', 'revision': sha}], 'T')
        self.assertNotEqual(refs[0]['sha256'], refs[1]['sha256'])
        (self.root / 'a.py').write_text('x = 3\n')
        self.assertEqual(evidence.changed(self.root, refs), ['a.py'])  # commit refs never drift
        with self.assertRaisesRegex(ValueError, 'without `..`'):
            evidence.hash_refs(self.root, [{'path': '../etc/passwd', 'statement': 's'}], 'T')
        with self.assertRaisesRegex(ValueError, 'cannot read'):
            evidence.hash_refs(self.root, [{'path': 'gone.py', 'statement': 's'}], 'T')
        self.assertEqual(evidence.expand(self.root, ['.'], 'T', 10), ['a.py', 'b.go'])

    def test_command_runs_must_be_approved_and_isolated(self):
        run = {'command': 'make test', 'cwd': 'worktree', 'revision': 'worktree', 'exit': 1,
               'output_sha256': 'a' * 64, 'excerpt': 'fail'}
        self.assertEqual(evidence.command_run(run, ['make test'], 'T')['exit'], 1)
        with self.assertRaisesRegex(ValueError, 'not approved'):
            evidence.command_run(run, [], 'T')
        with self.assertRaisesRegex(ValueError, 'isolated'):
            evidence.command_run(dict(run, cwd='project'), ['make test'], 'T')

    def test_budgets(self):
        state = {'budgets': budgets.approve({'a': 1, 'b': 2}, ('a', 'b'), 'T')}
        with self.assertRaisesRegex(ValueError, 'positive'):
            budgets.approve({'a': 0, 'b': 1}, ('a', 'b'), 'T')
        with self.assertRaisesRegex(ValueError, 'need b'):
            budgets.approve({'a': 1}, ('a', 'b'), 'T')
        self.assertFalse(budgets.exhausted(state, 'a'))
        budgets.spend(state, 'a')
        self.assertTrue(budgets.exhausted(state, 'a'))
        self.assertEqual(budgets.checkpoint_to(state, 'work', 'a used'), 'checkpoint')


if __name__ == '__main__':
    unittest.main()
