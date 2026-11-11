"""Scripted result sequences check protocol only, not actual agent adherence."""

import tempfile
import unittest

from support import Store, DispatchError, PASS
from engine.prompts import summary


def candidate(summary, criteria=('Checkable outcome.',), decisions=()):
    return {'status': 'candidate', 'summary': summary, 'criteria': list(criteria),
            'decisions': list(decisions)}


def decision(id, choice, alternative='Serious rival.', revisit='Assumption fails.'):
    return {'id': id, 'choice': choice, 'basis': 'assumption: typical load.',
            'alternative': alternative, 'tradeoff': 'Simpler, less flexible.', 'revisit': revisit}


def gap(check, witness, target="D1"):
    return {'status': 'revise', 'gaps': [{'check': check, 'witness': witness, 'decision': target}]}


def resolved(summary, criteria, decisions, *answers):
    return {**candidate(summary, criteria, decisions), 'status': 'resolved',
            'resolutions': [{'witness': w, 'answer': a, 'basis': b} for w, a, b in answers]}


class ScenarioFixtures(unittest.TestCase):
    def run_steps(self, request, *results):
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            state = store.start(request)
            for result in results:
                state = store.submit(state['ticket'], result)
            if state['phase'] == 'complete':
                state['text'] = summary(state)
            return state

    def test_trivial_task_without_decisions_passes_with_no_resolve(self):
        state = self.run_steps('Design a command printing Hello once.',
                               candidate('Single print.', ['Prints exactly one line: Hello.']), PASS)
        self.assertEqual(state['phase'], 'complete')
        self.assertNotIn('resolutions', state)
        self.assertIn('None consequential.', state['text'])

    def test_unknown_intent_blocks_for_requester_then_completes_once(self):
        witness = 'Hello and Hola both fit; requester would differ.'
        state = self.run_steps(
            'Design a greeting for regulated bilingual support; required language is unresolved.',
            candidate('Print a greeting.'), gap('unknown', witness, 'new'),
            {'status': 'blocked', 'question': 'Which language?', 'needs': 'Requester answer.'},
            resolved('Print Hello.', ['Prints exactly one line: Hello.'], [],
                     (witness, 'English.', 'Requester said English.')))
        self.assertEqual(state['phase'], 'complete')
        self.assertIn('(unknown, new) ' + witness + ' → English.', state['text'])

    def test_criteria_pass_while_goal_fails_is_resolved_without_rereview(self):
        weak = candidate('Cache results.', ['Cache returns a value.'], [decision('D1', 'In-memory dict.')])
        witness = 'A stale value also satisfies the criterion.'
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            state = store.start('Design a cache that never serves stale prices.')
            state = store.submit(state['ticket'], weak)
            state = store.submit(state['ticket'], gap('defeater', witness))
            self.assertEqual(state['phase'], 'resolve')
            self.assertEqual(state['candidate'], {k: v for k, v in weak.items() if k != 'status'})
            with self.assertRaises(DispatchError):
                store.submit(state['ticket'], PASS)  # No second review.
            state = store.submit(state['ticket'], resolved(
                'Cache with TTL below price update interval.',
                ['No read returns a price older than its update interval.'],
                [decision('D1', 'In-memory dict with TTL.')],
                (witness, 'TTL bounds staleness.', 'Request: never stale.')))
            self.assertEqual(state['phase'], 'complete')
            self.assertNotIn('ticket', state)

    def test_decision_missing_alternative_is_rejected_structurally(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            state = store.start('Design storage.')
            bare = {k: v for k, v in decision('D1', 'SQLite.').items() if k != 'alternative'}
            with self.assertRaises(DispatchError):
                store.submit(state['ticket'], candidate('Use SQLite.', decisions=[bare]))

    def test_fact_gap_and_explicit_deferral_resolve_in_one_pass(self):
        conditional = 'Conditional: authorized operator must compare packet loss/server timing before D1 diagnosis; alert threshold remains deferred.'
        diagnostic = {**decision('D1', 'Compare causes; do not select a production fix.'),
                      'basis': 'Unknown production cause; no access granted.',
                      'revisit': 'Operator supplies measured loss/server timing.'}
        loss, alert = 'Loss vs slow server give different fixes.', 'Paging at 1% vs 5% differs to on-call.'
        state = self.run_steps(
            'Design diagnosis for intermittent timeout; no production access.',
            candidate('Fix the network.', decisions=[decision('D1', 'Retune TCP.')]),
            {'status': 'revise', 'gaps': [{'check': 'unknown', 'witness': loss, 'decision': 'D1'},
                                          {'check': 'unknown', 'witness': alert, 'decision': 'new'}]},
            resolved(conditional, ['Operator measurements gate D1; no paging before requester selects threshold.'],
                     [diagnostic],
                     (loss, 'Unknown: conditional diagnosis only.', 'No production access granted.'),
                     (alert, 'deferred: requester decides after trial.', 'Requester deferred.')))
        self.assertIn(loss + ' → Unknown: conditional', state['text'])
        self.assertIn('deferred: requester decides', state['text'])
        self.assertIn('Conditional:', state['text'])
        self.assertEqual(len(state['resolutions']), 2)

    def test_engineering_means_and_delegated_tradeoff_need_no_approval_route(self):
        for request in ('Design a local Python report generator; follow project conventions.',
                        'Design storage; choose cost/latency within $20/month and 200ms; no deployment.'):
            with self.subTest(request=request):
                choice = {**decision('D1', 'Smallest conventional in-scope option.'),
                          'basis': 'Request constraints/delegation; applicable project defaults.'}
                state = self.run_steps(request, candidate('Choose within bounds.', decisions=[choice]), PASS)
                self.assertEqual(state['phase'], 'complete')
                self.assertNotIn('resolutions', state)

    def test_unsafe_missing_fact_blocks_ready_choice_without_artifact(self):
        state = self.run_steps(
            'Choose a ready destructive migration now; production inspection is not authorized.',
            candidate('Drop old table.', decisions=[decision('D1', 'Drop table.')]),
            gap('unknown', 'No backup makes D1 destructive and unrecoverable.'),
            {'status': 'blocked', 'question': 'Is a restore-tested backup available?',
             'needs': 'Authorized operator must supply restore-test evidence before D1 can be ready.'})
        self.assertEqual(state['phase'], 'blocked')
        self.assertNotIn('text', state)

    def test_unsettled_permission_blocks_instead_of_using_design_authority(self):
        state = self.run_steps(
            'Design a report; whether it may send customer data to an external API is unresolved.',
            candidate('Send to external API.', decisions=[decision('D1', 'External API.')]),
            gap('unknown', 'External API and local processing differ in permission.'),
            {'status': 'blocked', 'question': 'May customer data leave the system?',
             'needs': 'Requester permission, not a convention or reversible engineering choice.'})
        self.assertEqual(state['phase'], 'blocked')

    def test_settled_java_executor_choice_can_be_revised_for_unowned_work(self):
        weak = candidate('Use the existing executor.', decisions=[decision('D1', 'Follow executor convention.')])
        witness = 'Executor convention alone does not join work or observe failed futures.'
        state = self.run_steps(
            'Design Java background work; the project executor choice is already settled.',
            weak, gap('defeater', witness),
            resolved('Keep executor convention; own all submitted work.',
                     ['Shutdown cancels and joins work; failures are observed, including shutdown.'],
                     [{**decision('D1', 'Explicit executor/future lifecycle.'),
                       'basis': 'Request convention plus common/Java resource contract.',
                       'tradeoff': 'More lifecycle code; no unowned background work.'}],
                     (witness, 'Own lifecycle explicitly.', 'Java resource contract.')))
        self.assertEqual(state['phase'], 'complete')
        self.assertIn('failures are observed', state['text'])

    def test_nonsoftware_instruction_design_uses_observable_rule(self):
        state = self.run_steps(
            'Design an agent instruction for report-only requests; no software architecture.',
            candidate('When request is report-only, return a report without modifying the target.',
                      ['For a report-only request, target bytes remain unchanged.']), PASS)
        self.assertEqual(state['phase'], 'complete')
        self.assertIn('None consequential.', state['text'])
        self.assertIn('target bytes remain unchanged', state['text'])

    def test_hidden_conditional_prerequisite_is_resolved_into_summary_and_criteria(self):
        weak = candidate('Destructive migration is ready.', ['Migration procedure is documented.'],
                         [decision('D1', 'Drop old table.', revisit='Verify restore-tested backup first.')])
        gate = 'Conditional: operator verifies restore-tested backup; do not act on D1 until verified.'
        witness = 'An unmet prerequisite hidden in revisit lets a ready summary mislead.'
        state = self.run_steps(
            'Design a conditional migration report; operator will verify backup readiness later.',
            weak, gap('defeater', witness),
            resolved(gate, ['Operator restore-test evidence gates D1; no destructive step before it.'],
                     [{**decision('D1', 'Drop only after verified backup.'),
                       'basis': 'Unknown backup readiness; conditional, not observed.',
                       'revisit': 'Restore test fails or evidence is unavailable.'}],
                     (witness, 'Gate moved into summary and criteria.', 'Readiness unverified.')))
        self.assertEqual(state['phase'], 'complete')
        self.assertIn(gate, state['text'])
        self.assertIn('no destructive step before it', state['text'])

    def test_deferred_intent_is_not_silently_selected_by_a_dependent_choice(self):
        witness = 'A conventional default silently selects explicitly deferred paging intent.'
        state = self.run_steps(
            'Design alert measurement; paging threshold is explicitly deferred to requester.',
            candidate('Page at 1%.', decisions=[decision('D1', 'Use conventional 1% threshold.')]),
            gap('defeater', witness),
            resolved('Collect measurements only; no paging until requester chooses threshold.',
                     ['No paging configuration is enabled before requester decision.'], [],
                     (witness, 'Paging removed until requester decides.', 'Requester deferred threshold.')))
        self.assertIn('no paging until requester chooses', state['text'])


if __name__ == '__main__':
    unittest.main()
