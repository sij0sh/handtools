"""Content/disclosure regressions, not tests of model reasoning or adherence."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import ROOT, CLI, REQUEST, CANDIDATE, PASS, NEED, BLOCKED, RESOLVED
from engine import router
from engine.prompts import DRAFT, RESOLVE, REVIEW, GUIDANCE_PATH, DONE, render, summary


class PromptTests(unittest.TestCase):
    def test_authority_source_order_and_evidence_limits_are_explicit(self):
        self.assertIn('request/delegation → supported decisions/conventions → applicable defaults → simplest adequate', DRAFT)
        for rule in ('Defects defeat precedent', 'defaults never settle goals/permissions',
                     'Honor approvals/deferrals', 'material unresolved user-owned intent',
                     'never edit report-only targets', 'Expose assumptions'):
            self.assertIn(rule, DRAFT)
        for rule in ('request/documents/delegation first', 'pause until answered',
                     'never silently choose deferred intent', 'never invent authority or answers',
                     'cheapest authorized observation', 'before material harm/commitment',
                     'explicit detection/revisit conditions', 'never as observation'):
            self.assertIn(rule, RESOLVE)
        self.assertNotIn('never pick', RESOLVE)

    def test_review_retains_counterexamples_and_challenges_false_authority(self):
        for rule in ('Delegate if available', 'otherwise review locally', 'Pair:', 'Defeater:',
                     'Decision:', 'not assumed truths', 'criteria passing while goal fails',
                     'unsafe assumptions', 'hidden deferred dependencies',
                     'serious alternative/tradeoff/revisit', 'Alternatives alone require no question',
                     'planned/executed tests', 'delegated/local basis', '"none: why"'):
            self.assertIn(rule, REVIEW)

    def test_conditional_readiness_gate_is_in_resolve_and_review_not_new_state(self):
        for instructions in (RESOLVE, REVIEW):
            for term in ('"Conditional:"', 'prerequisite', 'verifier', 'criteria test'):
                self.assertIn(term, instructions)
        self.assertIn('decisions not to act on', RESOLVE)
        self.assertIn('If readiness is required now, block', RESOLVE)
        self.assertIn('DONE completes the report, not its prerequisites', RESOLVE)
        self.assertIn('Readiness required: need', REVIEW)
        self.assertEqual(set(router.RESULTS['draft']), {'candidate', 'need'})
        self.assertEqual(set(router.RESULTS['resolve']), {'resolved', 'blocked'})
        self.assertEqual(set(router.RESULTS['review']), {'pass', 'revise', 'need'})

    def test_disclosure_is_domain_not_gap_gated_in_draft_and_review(self):
        for request in ('Design Java work using our already-settled executor convention.',
                        'Design an agent instruction; no software implementation.',
                        'Design seating for a wedding; no software or agent instructions.'):
            draft = router.new(request)
            for state in (draft, router.advance(draft, CANDIDATE)):
                with self.subTest(request=request, prompt=state['phase']):
                    output = render(state, CLI, Path('/unrelated/task'))
                    self.assertIn(json.dumps(str(GUIDANCE_PATH)), output)
                    self.assertIn('software—common/relevant language rows even for settled choices', output)
                    self.assertIn('agent-instructions—instruction rule; otherwise skip', output)
                    self.assertIn('Reuse context; separate reviewers read independently', output)
        resolve = router.advance(router.new(REQUEST), NEED)
        self.assertNotIn(str(GUIDANCE_PATH), render(resolve, CLI, Path('/unrelated/task')))

    def test_reference_contains_one_common_contract_and_ten_compact_profiles(self):
        text = GUIDANCE_PATH.read_text()
        rows = [line.split('|')[1].strip() for line in text.splitlines()
                if line.startswith('| ')][1:]
        self.assertEqual(rows, ['C', 'C++', 'C#', 'Go', 'Java', 'JavaScript',
                                'Python', 'Rust', 'SQL', 'TypeScript'])
        for term in ('one authoritative owner', 'cleanup owners', 'cancel/shut down, join',
                     'observe failures', 'never correctness/safety', 'unlisted languages',
                     'identifiable trigger, changed decision and observable outcome'):
            self.assertIn(term, text)
        self.assertLessEqual(len(text.split()), 350)

    def test_complete_summary_contains_full_record_and_ends_with_done_marker(self):
        resolve = router.advance(router.new(REQUEST), NEED)
        blocked = router.advance(resolve, BLOCKED)
        redraft = router.advance(blocked, RESOLVED)
        complete = router.advance(router.advance(redraft, CANDIDATE), PASS)
        text = summary(complete)
        fields = (REQUEST, CANDIDATE['summary'], CANDIDATE['criteria'][0],
                  CANDIDATE['decisions'][0]['id'], '## Resolutions', NEED['question'],
                  RESOLVED['answer'], RESOLVED['basis'], PASS['pair'], PASS['defeater'],
                  PASS['decision'], PASS['basis'], 'Design complete, not implementation.')
        fields += tuple(CANDIDATE['decisions'][0][key]
                        for key in ('choice', 'basis', 'alternative', 'tradeoff', 'revisit'))
        for value in fields:
            self.assertIn(value, text)
        output = render(complete, CLI, Path('/unrelated/task'))
        self.assertEqual(output, text + '\n\n' + DONE)
        self.assertTrue(output.endswith(DONE))

    def test_summary_omits_resolutions_when_empty_and_marks_no_decisions(self):
        complete = router.advance(router.advance(router.new(REQUEST), CANDIDATE), PASS)
        text = summary(complete)
        self.assertNotIn('## Resolutions', text)
        empty = {**complete, 'candidate': {**complete['candidate'], 'decisions': []}}
        self.assertIn('None consequential.', summary(empty))

    def test_done_marker_is_not_injected_into_incomplete_prompts(self):
        marker = 'DONE: design recorded in .agents/decision.json'
        candidate = {**CANDIDATE,
                     'summary': f'The literal {marker} appears in context.'}
        review = router.advance(router.new(REQUEST), candidate)
        output = render(review, CLI, Path('/unrelated/task'))
        self.assertIn(marker, output)
        self.assertFalse(output.endswith(DONE))

    def test_installed_reference_path_survives_foreign_cwd_and_spaces(self):
        with tempfile.TemporaryDirectory(prefix='sbd install ') as temporary:
            base = Path(temporary)
            skill, project = base / 'skill with spaces', base / 'task project'
            shutil.copytree(ROOT / 'scripts', skill / 'scripts',
                            ignore=shutil.ignore_patterns('__pycache__'))
            (skill / 'references').mkdir()
            shutil.copy2(GUIDANCE_PATH, skill / 'references/design.md')
            project.mkdir()
            command = [sys.executable, str(skill / 'scripts/sbd.py'), '--root', str(project)]
            first = subprocess.run(command + ['--request', REQUEST], cwd='/',
                                   capture_output=True, text=True, check=True)
            checkpoint = json.loads((project / '.agents/decision.json').read_text())
            second = subprocess.run(command + ['done', checkpoint['ticket']], cwd='/',
                                    input=json.dumps(CANDIDATE), capture_output=True,
                                    text=True, check=True)
            path = json.dumps(str(skill / 'references/design.md'))
            for output in (first.stdout, second.stdout):
                self.assertIn(path, output)
                self.assertNotIn(json.dumps(str(GUIDANCE_PATH)), output)
            self.assertFalse((project / 'references').exists())


if __name__ == '__main__':
    unittest.main()
