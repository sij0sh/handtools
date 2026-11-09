"""G6: review classifies the seeded shop fixture, refuses unsupported verdicts, stops within budgets,
reopens exactly what cites changed sources, and renders the same report from the journal."""
import hashlib
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
FIXTURE = SKILLS.parent / 'tests' / 'fixtures' / 'review' / 'shop'
SCRIPT = HERE / 'scripts' / 'workflow.py'
sys.path[:0] = [str(SKILLS), str(HERE / 'scripts')]
from _engine import events, storage  # noqa: E402
from _engine.recon import store  # noqa: E402
from reviewlib import report  # noqa: E402

PLAN = {'goal': 'review the rounding change', 'verification': 'report against expected-classification.json',
        'constraints': [], 'criteria': ['every seed classified'], 'decisions': [], 'blocking': [], 'challenged': True}
TESTS = 'python3 -m unittest discover -s tests'
TAX = 'python3 -c "from shop.checkout import tax_cents; print(tax_cents(1000, 0.0825))"'
BUDGETS = {'hunt_transitions': 10, 'validate_transitions': 10, 'attempts_per_candidate': 3,
           'variant_obligations': 2, 'challenge_rounds': 2, 'max_obligations': 20}
OBLIGATIONS = [
    {'id': 'O1', 'target': 'shop/pricing.py', 'boundary': 'library', 'check': 'general/compatibility',
     'risk': 'callers rely on half-up rounding', 'rationale': 'the diff changes round_cents'},
    {'id': 'O2', 'target': 'shop/checkout.py:17-19', 'boundary': 'library', 'check': 'python/numeric',
     'risk': 'tax rounding', 'rationale': 'tax_cents calls round_cents'},
    {'id': 'O3', 'target': 'shop/cart.py:13-16', 'boundary': 'library', 'check': 'general/logic',
     'risk': 'pagination', 'rationale': 'checkout pages carts'},
    {'id': 'O4', 'target': 'shop/pricing.py:9-11', 'boundary': 'library', 'check': 'general/error-propagation',
     'risk': 'None discount', 'rationale': 'apply_discount indexes its argument'},
    {'id': 'O5', 'target': 'shop/checkout.py:26-31', 'boundary': 'library', 'check': 'tests/contract-tested',
     'risk': 'refund limits', 'rationale': 'refunds move money'},
    {'id': 'O6', 'target': 'tests/test_checkout.py', 'boundary': 'test', 'check': 'tests/assertion',
     'risk': 'discount total unasserted', 'rationale': 'the only discount test'}]


def ev(path, statement, lines=None, revision=None):
    ref = {'path': path, 'statement': statement}
    if lines:
        ref['lines'] = lines
    if revision:
        ref['revision'] = revision
    return [ref]


def git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@example.com', GIT_COMMITTER_NAME='t',
               GIT_COMMITTER_EMAIL='t@example.com')
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True,
                          env=env).stdout.strip()


def run_record(command, revision, output, exit_code=0):
    return {'command': command, 'cwd': 'worktree', 'revision': revision, 'exit': exit_code,
            'output_sha256': hashlib.sha256(output.encode()).hexdigest(), 'excerpt': output}


class ReviewTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / 'shop'
        shutil.copytree(FIXTURE / 'base', self.root)
        git(self.root, 'init', '-q', '-b', 'main')
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-qm', 'Shop')
        self.base = git(self.root, 'rev-parse', 'HEAD')
        shutil.copytree(FIXTURE / 'head', self.root, dirs_exist_ok=True)
        git(self.root, 'commit', '-qam', 'Simplify cent rounding')
        self.head = git(self.root, 'rev-parse', 'HEAD')
        self.env = dict(os.environ, HANDTOOLS_STATE=str(self.tmp / 'state'))
        patcher = patch.dict(os.environ, {'HANDTOOLS_STATE': str(self.tmp / 'state')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cmd(self, *args, payload=None, ok=True):
        out = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args],
                             input=json.dumps(payload) if payload is not None else '',
                             capture_output=True, text=True, env=self.env)
        if ok:
            self.assertEqual(out.returncode, 0, out.stderr + out.stdout)
        else:
            self.assertNotEqual(out.returncode, 0, out.stdout)
        return out.stdout if ok else out.stderr

    def done(self, payload, ok=True):
        return self.run_cmd('done', payload=payload, ok=ok)

    def state(self):
        return json.loads(self.run_cmd('show'))

    def frame(self, **extra):
        body = {'plan': PLAN, 'approved_by_user': True, 'mode': 'diff', 'expected': 'totals and tax round half up',
                'diff': {'base': 'main~1', 'head': 'HEAD'},
                'scope': ['shop/checkout.py', 'shop/cart.py', 'tests/test_checkout.py'],
                'allowed_commands': [{'command': c, 'purpose': 'reproduce', 'side_effects': 'none (worktree)'}
                                     for c in (TESTS, TAX)],
                'budgets': BUDGETS}
        body.update(extra)
        return body

    def to_hunt(self, obligations=OBLIGATIONS, **frame):
        self.run_cmd('start')
        self.assertIn('STEP: RECON', self.done(self.frame(**frame)))
        self.assertIn('STEP: OBLIGATIONS', self.done({'recon_none': 'library with no external interfaces'}))
        return self.done({'obligations': obligations})

    def first_hunt(self):
        return {'results': [
            {'id': 'O1', 'status': 'examined', 'evidence': ev('shop/pricing.py', 'int() truncates', '4-6'),
             'outcome': {'performed': 'compared round_cents at base and head', 'result': 'candidates', 'refs': ['C1']}},
            {'id': 'O2', 'status': 'examined', 'evidence': ev('shop/checkout.py', 'tax delegates to round_cents', '17-19'),
             'outcome': {'performed': 'traced tax rounding', 'result': 'no-issue', 'refs': []}},
            {'id': 'O3', 'status': 'examined', 'evidence': ev('shop/cart.py', 'start = number * size', '13-16'),
             'outcome': {'performed': 'evaluated page(1, 2)', 'result': 'candidates', 'refs': ['C2']}},
            {'id': 'O4', 'status': 'examined', 'evidence': ev('shop/pricing.py', "discount['percent']", '9-11'),
             'outcome': {'performed': 'checked None discount', 'result': 'candidates', 'refs': ['C3']}},
            {'id': 'O5', 'status': 'examined', 'evidence': ev('tests/test_checkout.py', 'no refund test'),
             'outcome': {'performed': 'searched tests for refund', 'result': 'test-gaps', 'refs': ['T1']}}],
            'candidates': [
                {'id': 'C1', 'obligation': 'O1', 'expected': 'tax and totals round half up (pricing docstring)',
                 'actual': 'round_cents truncates', 'trigger': 'tax_cents(1000, 0.0825)',
                 'sources': ev('shop/pricing.py', 'return int(amount)', '4-6')},
                {'id': 'C2', 'obligation': 'O3', 'expected': '1-based pages (docstring)',
                 'actual': 'page 1 skips the first page', 'trigger': 'page(1, 2) with 3 items',
                 'sources': ev('shop/cart.py', 'start = number * size', '13-16')},
                {'id': 'C3', 'obligation': 'O4', 'expected': 'no TypeError on a missing discount',
                 'actual': "discount['percent'] fails for None", 'trigger': 'apply_discount(100, None)',
                 'sources': ev('shop/pricing.py', "discount['percent']", '9-11')}],
            'test_gaps': [{'id': 'T1', 'obligation': 'O5', 'contract': 'refund rejects zero, negative and excess',
                           'chain_break': 'no-test', 'consequence': 'a refund limit regression goes unnoticed',
                           'evidence': ev('shop/checkout.py', 'refund limits', '26-31')}]}

    def verdicts(self):
        merge_base = self.base
        return {'candidates': [
            {'id': 'C1', 'attempt': {'method': 'run tax at head', 'outcome': 'supports', 'note': '82, expected 83',
                                     'command_run': run_record(TAX, self.head, '82\n')},
             'verdict': {'state': 'confirmed', 'severity': 'medium', 'confidence': 'high', 'origin': 'introduced',
                         'proof': {'kind': 'counterexample', 'repeatable': True, 'observed': 'tax is 82, not 83',
                                   'command_run': run_record(TAX, self.head, '82\n')},
                         'baseline': {'statement': 'the same command prints 83 at the merge base',
                                      'command_run': run_record(TAX, merge_base, '83\n')}}},
            {'id': 'C2', 'verdict': {
                'state': 'confirmed', 'severity': 'low', 'confidence': 'high', 'origin': 'pre-existing',
                'proof': {'kind': 'source_argument', 'steps': [
                    {'role': 'trigger', 'claim': 'page(1, 2) on 3 items', 'evidence': ev('shop/cart.py', 'page(number, size)', '13')},
                    {'role': 'fault', 'claim': 'start = 1 * 2 = 2', 'evidence': ev('shop/cart.py', 'start = number * size', '15')},
                    {'role': 'effect', 'claim': 'returns only item 3', 'evidence': ev('shop/cart.py', 'slice', '16')}],
                    'mitigations_checked': [{'what': 'no caller converts to 0-based',
                                             'evidence': ev('shop/checkout.py', 'no page() call')}]},
                'baseline': {'statement': 'same line at the merge base',
                             'evidence': ev('shop/cart.py', 'start = number * size', '15', merge_base)}}},
            {'id': 'C3', 'verdict': {'state': 'rejected', 'reason': 'the only caller validates first',
                                     'counterevidence': ev('shop/checkout.py', 'returns early on None; validates otherwise', '11-15')}}]}

    def second_hunt(self):
        return {'results': [{'id': 'O6', 'status': 'examined', 'evidence': ev('tests/test_checkout.py', "assertIn('$')", '8-12'),
                             'outcome': {'performed': 'read assertions', 'result': 'test-gaps', 'refs': ['T2']}}],
                'test_gaps': [{'id': 'T2', 'obligation': 'O6', 'contract': 'discounted total is 1800',
                               'chain_break': 'wrong-assertion', 'consequence': 'a wrong discount passes',
                               'evidence': ev('tests/test_checkout.py', "assertIn('$', format_total(total))", '12')}]}

    def test_diff_review_classifies_every_seed(self):
        expected = json.loads((FIXTURE / 'expected-classification.json').read_text())
        out = self.to_hunt()
        self.assertIn('STEP: HUNT', out)
        self.assertIn('Next obligations:', out)
        self.assertIn('STEP: VALIDATE', self.done(self.first_hunt()))
        self.assertIn('STEP: HUNT', self.done(self.verdicts()))
        self.assertIn('STEP: CHALLENGE', self.done(self.second_hunt()))
        out = self.done({'reviewer': 'fresh', 'objections': [
            {'claim': 'C3 could be reached directly', 'verdict': 'rejected', 'reason': 'no other caller', 'reopen': []}]})
        self.assertIn('STEP: REPORT', out)
        self.assertIn('# Review review-', out)
        state = self.state()
        self.assertEqual(state['outcome'], {'result': 'complete', 'reasons': []})
        got = {c['id']: (c['state'], c['verdict'].get('origin')) for c in state['candidates'].values()}
        self.assertEqual(got, {'C1': ('confirmed', 'introduced'), 'C2': ('confirmed', 'pre-existing'),
                               'C3': ('rejected', None)})
        seeds = {s['id']: s for s in expected['seeds']}
        self.assertEqual({t['chain_break'] for t in state['test_gaps'].values()},
                         {seeds['refund-untested']['chain_break'], seeds['discount-test-asserts-format']['chain_break']})
        run_id = state['run_id']
        self.assertIn('DONE', self.done({}))
        path = report.report_path(self.root, run_id)
        text = path.read_text()
        self.assertIn('COMPLETE', text)
        self.assertIn('## Findings (confirmed): 2', text)
        self.assertIn('## Test gaps: 2 (not bug findings)', text)
        self.assertIn('Report-only', text)
        ran = text.split('## Commands run')[1].split('##')[0]
        self.assertEqual(ran.count(TAX), 2)  # head (attempt and proof cite one run) and merge base
        self.assertIn('- Attempt 1:', text)
        # The report renders from the journal alone: replaying the final state gives the same bytes.
        history = storage.journal(storage.state_dir('review', self.root)).history('workflow.json')
        final = events.replay(history[:-1])[0]
        self.assertEqual(report.render(final), text)
        self.assertEqual(report.render(final), report.render(json.loads(json.dumps(final))))

    def test_gates_refuse_unsupported_claims(self):
        self.to_hunt()
        hunt = self.first_hunt()
        bad = json.loads(json.dumps(hunt))
        del bad['results'][1]['outcome']
        self.assertIn('examined needs `outcome`', self.done(bad, ok=False))
        bad = json.loads(json.dumps(hunt))
        bad['results'][0]['outcome']['refs'] = []
        self.assertIn('exactly the candidates', self.done(bad, ok=False))
        bad = dict(hunt, commands_run=[run_record('rm -rf /', self.head, 'x')])
        self.assertIn('was not approved', self.done(bad, ok=False))
        bad = dict(hunt, commands_run=[dict(run_record(TESTS, self.head, 'ok'), cwd='project')])
        self.assertIn('isolated `cwd`', self.done(bad, ok=False))
        self.done(hunt)
        v = self.verdicts()['candidates']

        def refused(item, needle):
            self.assertIn(needle, self.done({'candidates': [item]}, ok=False))
        refused({'id': 'C1', 'verdict': {'state': 'confirmed', 'severity': 'high', 'confidence': 'high'}},
                'proof')
        no_effect = json.loads(json.dumps(v[1]))
        no_effect['verdict']['proof']['steps'].pop()
        refused(no_effect, 'missing effect')
        no_origin = json.loads(json.dumps(v[0]))
        del no_origin['verdict']['origin']
        refused(no_origin, 'origin')
        wrong_base = json.loads(json.dumps(v[1]))
        wrong_base['verdict']['baseline']['evidence'][0]['revision'] = self.head
        refused(wrong_base, 'baseline refs need')
        refused({'id': 'C3', 'verdict': {'state': 'rejected', 'reason': 'trust me'}}, 'cite at least one')
        refused({'id': 'C3', 'attempt': {'method': 'run', 'outcome': 'tool-failed', 'note': 'import error'},
                 'verdict': {'state': 'rejected', 'reason': 'it failed', 'attempts': [1],
                             'counterevidence': ev('shop/checkout.py', 'x')}}, 'failed as tools')
        refused({'id': 'C3', 'verdict': {'state': 'duplicate'}}, 'duplicate_of')
        refused({'id': 'C3', 'verdict': {'state': 'unresolved', 'reason': 'unsure'}}, 'at least one recorded attempt')
        # A tool failure leaves the candidate open, never rejected.
        out = self.done({'candidates': [{'id': 'C3', 'attempt': {'method': 'run', 'outcome': 'tool-failed',
                                                                 'note': 'missing dependency'}}]})
        self.assertIn('STEP: VALIDATE', out)
        self.assertEqual(self.state()['candidates']['C3']['state'], 'validating')

    def test_budgets_stop_at_checkpoint_and_publish_incomplete(self):
        self.to_hunt(budgets=dict(BUDGETS, hunt_transitions=1, validate_transitions=1))
        self.assertIn('STEP: VALIDATE', self.done(self.first_hunt()))
        out = self.done(self.verdicts())
        self.assertIn('STEP: CHECKPOINT', out)
        self.assertIn('hunt_transitions budget used', out)
        out = self.done({'approved_by_user': True, 'decision': 'publish_incomplete'})
        self.assertIn('STEP: REPORT', out)
        outcome = self.state()['outcome']
        self.assertEqual(outcome['result'], 'incomplete')
        self.assertIn('obligations not examined: O6', outcome['reasons'])
        self.assertIn('INCOMPLETE', out)

    def test_drift_reopens_exactly_what_cites_the_changed_file(self):
        self.to_hunt()
        self.done(self.first_hunt())
        cart = self.root / 'shop' / 'cart.py'
        cart.write_text(cart.read_text().replace('number * size', '(number - 1) * size'))
        self.assertIn('SOURCE CHANGED since FRAME: shop/cart.py', self.run_cmd('status'))
        out = self.done(self.verdicts())
        self.assertIn('STEP: CHECKPOINT', out)
        state = self.state()
        self.assertIn('reopened C2, O3.', state['checkpoint']['reason'])
        self.assertEqual(state['obligations']['O3']['status'], 'planned')
        self.assertEqual(state['obligations']['O1']['status'], 'examined')
        self.assertTrue(all(c['state'] == 'proposed' for c in state['candidates'].values()))  # verdicts not applied
        self.assertIn('STEP: RECON', self.done({'approved_by_user': True, 'decision': 'reframe'}) and
                      self.done(self.frame()))
        self.done({'recon_none': 'library'})
        out = self.done({'obligations': []})
        self.assertIn('STEP: VALIDATE', out)
        self.assertNotIn('SOURCE CHANGED', out)

    def test_abandon_writes_a_cancelled_report(self):
        self.to_hunt()
        run_id = self.state()['run_id']
        out = self.run_cmd('abandon')
        self.assertIn('Cancelled report:', out)
        self.assertIn('CANCELLED', report.report_path(self.root, run_id).read_text())

    def test_bug_mode_needs_the_symptom_explained(self):
        self.run_cmd('start')
        body = self.frame(mode='bug', diff=None, scope=['shop/cart.py'],
                          bug={'symptom': 'page 1 is missing items', 'expected': 'items 1-2',
                               'reproduction': 'page(1, 2) on 3 items', 'version': 'main'})
        del body['diff']
        self.assertIn('bug mode needs `bug`', self.done(dict(body, bug=None), ok=False))
        self.done(body)
        self.done({'recon_none': 'library'})
        self.done({'obligations': [OBLIGATIONS[2]]})
        hunt = self.first_hunt()
        self.done({'results': [hunt['results'][2]], 'candidates': [hunt['candidates'][1]]})
        c2 = self.verdicts()['candidates'][1]
        del c2['verdict']['origin'], c2['verdict']['baseline']
        self.done({'candidates': [c2]})
        out = self.done({'reviewer': 'self', 'objections': []})
        self.assertIn('symptom is not explained', out)
        self.assertIn('self-review', out)

    def test_recon_pin_and_stale_citation_blocks_complete_report(self):
        self.run_cmd('start')
        self.done(self.frame())
        snap = store.start(self.root, 'r-start')['run_id']
        store.record(self.root, snap, {'records': [
            {'id': 'obs:docs-say-cents', 'classification': 'declared', 'claim': 'amounts are integer cents',
             'evidence': [{'source': '.', 'path': 'README.md', 'statement': 'integer cents'}]}]}, 1, 'r-rec')
        self.assertIn('is open', self.done({'recon_snapshot': snap}, ok=False))
        store.close(self.root, snap, 2, 'r-close')
        self.assertIn('STEP: OBLIGATIONS', self.done({'recon_snapshot': snap}))
        bad = [dict(OBLIGATIONS[0], recon_refs=['obs:nope'])]
        self.assertIn('not in the pinned snapshot', self.done({'obligations': bad}, ok=False))
        self.done({'obligations': [dict(OBLIGATIONS[1], recon_refs=['obs:docs-say-cents'])]})
        self.done({'results': [self.first_hunt()['results'][1]]})
        readme = self.root / 'README.md'
        readme.write_text(readme.read_text() + 'Amounts may be floats.\n')
        store.refresh(self.root, snap, 'r-refresh')
        out = self.done({'reviewer': 'self', 'objections': []})
        self.assertIn('STEP: CHECKPOINT', out)
        self.assertIn('recon stale', out)
        self.assertEqual(self.state()['obligations']['O2']['status'], 'planned')


if __name__ == '__main__':
    unittest.main()
