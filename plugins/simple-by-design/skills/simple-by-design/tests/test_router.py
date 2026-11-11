from copy import deepcopy
import unittest

from support import REQUEST, CANDIDATE, PASS, BLOCKED, RESOLVED, REVISE, DispatchError
from engine import router


def body(result):
    return {key: value for key, value in result.items() if key != "status"}


class RouterTests(unittest.TestCase):
    def test_zero_gap_path_needs_only_candidate_and_review(self):
        draft = router.new(REQUEST)
        self.assertEqual(set(draft), {"schema_version", "phase", "ticket", "request"})
        self.assertEqual(draft["schema_version"], 5)
        self.assertEqual(draft["phase"], "draft")
        review = router.advance(draft, CANDIDATE)
        final = router.advance(review, PASS)
        self.assertEqual((draft["phase"], review["phase"], final["phase"]),
                         ("draft", "review", "complete"))
        self.assertEqual(draft["request"], final["request"])
        self.assertEqual(final["candidate"], body(CANDIDATE))
        self.assertEqual(final["review"], body(PASS))
        self.assertNotEqual(draft["ticket"], review["ticket"])
        self.assertNotIn("ticket", final)
        self.assertNotIn("candidate", draft)  # Pure transitions.
        self.assertEqual(set(final), {"schema_version", "phase", "request",
                                      "candidate", "review"})

    def test_defect_path_resolves_once_then_completes_without_loop(self):
        review = router.advance(router.new(REQUEST), CANDIDATE)
        resolve = router.advance(review, REVISE)
        self.assertEqual(resolve["phase"], "resolve")
        self.assertEqual(resolve["gaps"], REVISE["gaps"])
        self.assertEqual(resolve["candidate"], review["candidate"])
        blocked = router.advance(resolve, BLOCKED)
        self.assertEqual(blocked["phase"], "blocked")
        self.assertEqual(blocked["blocked_on"], body(BLOCKED))
        for source in (resolve, blocked):
            final = router.advance(source, RESOLVED)
            self.assertEqual(final["phase"], "complete")
            self.assertNotIn("ticket", final)
            self.assertNotIn("review", final)
            self.assertEqual(final["candidate"], {k: v for k, v in body(RESOLVED).items()
                                                  if k != "resolutions"})
            self.assertEqual(final["resolutions"], RESOLVED["resolutions"])
            self.assertEqual(set(final), {"schema_version", "phase", "request",
                                          "candidate", "gaps", "resolutions"})
        for bad in (PASS, CANDIDATE, REVISE):
            with self.assertRaises(DispatchError):
                router.advance(resolve, bad)  # Resolve cannot re-review or redraft.
        for bad in (BLOCKED, RESOLVED):
            with self.assertRaises(DispatchError):
                router.advance(review, bad)
        unmatched = {**RESOLVED, "resolutions": [{**RESOLVED["resolutions"][0], "witness": "other"}]}
        for bad in (unmatched, {**RESOLVED, "resolutions": RESOLVED["resolutions"] * 2},
                    {**RESOLVED, "resolutions": []}):
            with self.assertRaises(DispatchError):
                router.advance(resolve, bad)

    def test_invalid_results_never_mutate_the_input(self):
        states = [router.new(REQUEST)]
        states.append(router.advance(states[0], CANDIDATE))
        states.append(router.advance(states[1], REVISE))
        no_alternative = {k: v for k, v in CANDIDATE["decisions"][0].items() if k != "alternative"}
        malformed = [None, [], '', 1, {}, {'status': []}, {'status': 'DONE'},
                     {**CANDIDATE, 'summary': ''},
                     {**CANDIDATE, 'summary': '  '},
                     {**CANDIDATE, 'summary': 123},
                     {**CANDIDATE, 'next': 'DONE'},
                     {**CANDIDATE, 'criteria': []},
                     {**CANDIDATE, 'decisions': [no_alternative]},
                     {**CANDIDATE, 'decisions': [{**CANDIDATE['decisions'][0], 'revisit': ''}]},
                     {**CANDIDATE, 'decisions': [{'id': 'D1', 'choice': 'x', 'basis': 'x', 'alternative': 'x', 'tradeoff': 'x', 'revisit': 'x'}, {'id': 'D1', 'choice': 'x', 'basis': 'x', 'alternative': 'x', 'tradeoff': 'x', 'revisit': 'x'}]},
                     {'status': 'need', 'type': 'intent', 'question': 'q', 'witness': 'w', 'consequence': 'c'},
                     {k: v for k, v in RESOLVED.items() if k != 'resolutions'},
                     {'status': 'blocked', 'question': 'q', 'needs': None},
                     {'status': 'resolved', 'answer': 'x', 'basis': ''},
                     {k: v for k, v in PASS.items() if k != 'defeater'},
                     {**PASS, 'basis': 'bad\x00text'},
                     {'status': 'revise', 'gaps': []},
                     {'status': 'revise', 'gaps': [{**REVISE['gaps'][0], 'check': 'style'}]}]
        for state in states:
            for result in malformed:
                with self.subTest(prompt=state['phase'], result=result):
                    before = deepcopy(state)
                    with self.assertRaises(DispatchError):
                        router.advance(state, result)
                    self.assertEqual(state, before)

    def test_corrupt_checkpoint_fields_fail_cleanly(self):
        good = router.new(REQUEST)
        for field in good:
            for value in (None, [], {}, True, 99):
                with self.subTest(field=field, value=value):
                    bad = {**good, field: value}
                    if value == good[field] and type(value) is type(good[field]):
                        continue
                    with self.assertRaises(DispatchError):
                        router.validate(bad)
        for bad in ({}, {**good, 'extra': 'no'},
                    {**good, 'ticket': '../escape'},
                    {**good, 'phase': 'complete'},
                    {**good, 'phase': 'resolve'},
                    {**good, 'phase': 'review'},
                    {**good, 'phase': 'blocked'},
                    {**good, 'phase': 'publishing'},
                    {**good, 'schema_version': 1},
                    {**good, 'schema_version': 2},
                    {**good, 'schema_version': 3},
                    {**good, 'schema_version': 4}):
            with self.assertRaises(DispatchError):
                router.validate(bad)
        with self.assertRaisesRegex(DispatchError, 'legacy'):
            router.validate({**good, 'schema_version': 4})

    def test_phase_specific_payloads_and_complete_state_are_exact(self):
        review = router.advance(router.new(REQUEST), CANDIDATE)
        complete = router.advance(review, PASS)
        self.assertEqual(router.validate(complete), complete)
        self.assertEqual(set(complete), {"schema_version", "phase", "request",
                                         "candidate", "review"})
        for bad in (
                {key: value for key, value in complete.items() if key != "request"},
                {key: value for key, value in complete.items() if key != "candidate"},
                {key: value for key, value in complete.items() if key != "review"},
                {**complete, "ticket": review["ticket"]},
                {**complete, "gaps": REVISE["gaps"]},
                {**complete, "resolutions": RESOLVED["resolutions"]},
                {**complete, "phase": "publishing"},
                {**review, "review": body(PASS)},
                {**review, "blocked_on": body(BLOCKED)}):
            with self.subTest(bad=bad):
                with self.assertRaises(DispatchError):
                    router.validate(bad)
        old = {"schema_version": 4, "phase": "complete", "ticket": review["ticket"]}
        with self.assertRaisesRegex(DispatchError, 'legacy'):
            router.validate(old)


if __name__ == "__main__":
    unittest.main()
