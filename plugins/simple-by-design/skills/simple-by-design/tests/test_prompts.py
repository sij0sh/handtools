"""Content/disclosure regressions, not tests of model reasoning or adherence."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from support import ROOT, CLI, REQUEST, CANDIDATE, PASS, REVISE, BLOCKED, RESOLVED
from engine import router
from engine.prompts import DRAFT, RESOLVE, REVIEW, GUIDANCE_PATH, DONE, render, summary


class PromptTests(unittest.TestCase):
    def test_authority_source_order_and_evidence_limits_are_explicit(self):
        self.assertIn('explictly requested, locally established decisions/conventions, '
                      'best design practices, then the simplest adequate option', DRAFT)
        self.assertIn('Routine reversible choices need no justification', DRAFT)
        for rule in ('Defects override precedent', 'cheapest authorized observation',
                     'before material harm', 'never present it as observed',
                     'Resolve every review gap once', 'there is no further review'):
            self.assertIn(rule, RESOLVE)

    def test_review_retains_counterexamples(self):
        for rule in ('delegate when available', 'Pair:', 'Defeater:', 'Decision:', 'Unknown:',
                     'criteria pass while the goal fails', 'deferred dependency',
                     'serious alternative, tradeoff, revisit condition',
                     'reason for each absent defect'):
            self.assertIn(rule, REVIEW)

    def test_conditional_gate_and_single_pass_results(self):
        for term in ('"Conditional:"', 'prerequisite', 'verifier', 'Test the gate in the criteria',
                     'If readiness is required now, block',
                     'DONE completes the report, not its prerequisites'):
            self.assertIn(term, RESOLVE)
        self.assertEqual(set(router.RESULTS['draft']), {'candidate'})
        self.assertEqual(set(router.RESULTS['review']), {'pass', 'revise'})
        self.assertEqual(set(router.RESULTS['resolve']), {'resolved', 'blocked'})

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
        resolve = router.advance(router.advance(router.new(REQUEST), CANDIDATE), REVISE)
        self.assertIn(json.dumps(str(GUIDANCE_PATH)), render(resolve, CLI, Path('/unrelated/task')))

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
        complete = router.advance(router.advance(router.new(REQUEST), CANDIDATE), PASS)
        text = summary(complete)
        fields = (REQUEST, CANDIDATE['summary'], CANDIDATE['criteria'][0],
                  CANDIDATE['decisions'][0]['id'], PASS['pair'], PASS['defeater'],
                  PASS['decision'], PASS['unknown'], PASS['basis'],
                  'Design complete, not implementation.')
        fields += tuple(CANDIDATE['decisions'][0][key]
                        for key in ('choice', 'basis', 'alternative', 'tradeoff', 'revisit'))
        for value in fields:
            self.assertIn(value, text)
        output = render(complete, CLI, Path('/unrelated/task'))
        self.assertEqual(output, text + '\n\n' + DONE)

    def test_resolved_summary_pairs_each_gap_with_its_resolution(self):
        resolve = router.advance(router.advance(router.new(REQUEST), CANDIDATE), REVISE)
        text = summary(router.advance(router.advance(resolve, BLOCKED), RESOLVED))
        resolution = RESOLVED['resolutions'][0]
        self.assertIn(f"- (defeater, D1) {resolution['witness']} → {resolution['answer']} "
                      f"(basis: {resolution['basis']})", text)
        self.assertIn(RESOLVED['criteria'][0], text)
        self.assertNotIn(CANDIDATE['criteria'][0], text)
        empty = router.advance(router.advance(router.new(REQUEST), CANDIDATE), PASS)
        empty = {**empty, 'candidate': {**empty['candidate'], 'decisions': []}}
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
