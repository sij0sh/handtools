"""Per-dimension observations and scope-checked checkpoint reconciliation."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from helper import reconciliation


def operation(op_id, action, outcome, order, **extra):
    path = extra.get("path")
    row = {"operation_id": op_id, "recording_id": "rec", "lane": "u1", "branch": "a1",
           "order": order, "timestamp": f"2026-01-01T10:00:0{order}Z", "action": action,
           "outcome": outcome, "basis": "recorded_tool", "tool": "bash", "ref": {"offset": order},
           "path": path, "path_location": "repository" if path else None}
    row.update(extra)
    return row


def witness(witness_id, value, order, **extra):
    row = {"witness_id": witness_id, "relation": "commit", "recording_id": "rec", "lane": "u1",
           "branch": "a1", "order": order, "timestamp": f"2026-01-01T10:01:0{order}Z",
           "confidence": "recorded", "sha": value, "recorded_sha": value,
           "basis": "structured_commit_result", "subject": "Keep lock ordering",
           "ref": {"offset": order}}
    row.update(extra)
    return row


def checkpoint(cp_id="cp", boundary=5, order=9, status="resolved", **structured):
    return {"checkpoint_id": cp_id, "recording_id": "rec", "lane": "u1", "branch": "a1",
            "order": order, "boundary_order": boundary, "boundary_status": status,
            "publication_ref": {"offset": order},
            "structured": {"version": 1, **structured}}


class ObservationTests(unittest.TestCase):
    def test_dimensions_stay_independent(self):
        ops = [operation("e", "file_edit", "succeeded", 2, path="src/app.py"),
               operation("t", "command", "succeeded", 3, command="python3 -m pytest -q")]
        wits = [witness("w", "a" * 40, 4)]
        rows = reconciliation.observations(None, ops, wits)
        summary = reconciliation.summarize(rows, [])
        self.assertEqual(summary["edited"]["state"], "observed")
        self.assertEqual(summary["verified"]["state"], "observed")
        self.assertEqual(summary["committed"]["state"], "observed")
        self.assertEqual(summary["pushed"]["state"], "unknown")
        self.assertEqual(summary["live_confirmed"]["state"], "unknown")
        self.assertFalse(any(row.get("value") == "completed" for row in rows))
        self.assertEqual(set(reconciliation.DIMENSIONS), set(summary))

    def test_failed_then_passed_runs_remain_separate(self):
        ops = [operation("t1", "command", "failed", 2, command="pytest -q"),
               operation("t2", "command", "succeeded", 3, command="pytest -q")]
        rows = reconciliation.observations(None, ops, [])
        values = [row["value"] for row in rows if row["dimension"] == "verified"]
        self.assertEqual(values, ["test_run_failed", "test_run_passed"])
        self.assertEqual(len({row["observation_id"] for row in rows}), 2)

    def test_compound_command_keeps_test_and_push_observations_separate(self):
        ops = [operation("c", "command", "failed", 2,
                         command="git push origin main && pytest -q")]
        rows = reconciliation.observations(None, ops, [])
        values = {(row["dimension"], row["value"]) for row in rows}
        self.assertIn(("verified", "test_run_failed"), values)
        self.assertIn(("pushed", "push_failed"), values)

    def test_pushed_claim_compares_with_push_observation(self):
        cp = checkpoint(currentState="Changes are unpushed.")
        observations = reconciliation.observations(
            None, [operation("p", "command", "succeeded", 4, command="git push origin main")], [])
        rows = reconciliation.compare(cp, reconciliation.claims_for(cp), observations)
        pushed = [row for row in rows if row["dimension"] == "pushed"]
        self.assertEqual([row["relation"] for row in pushed], ["contradicts"])

    def test_observation_without_order_is_not_comparable(self):
        cp = checkpoint(currentState="uncommitted")
        observation = witness("w", "a" * 40, 4)
        observation["order"] = None
        rows = reconciliation.compare(cp, reconciliation.claims_for(cp),
                                      reconciliation.observations(None, [], [observation]))
        self.assertEqual([row["relation"] for row in rows], ["not_comparable"])
        self.assertEqual(rows[0]["reason"], "observation_without_order")

    def test_unknown_write_and_planning_snapshot_are_not_confirmed_edits(self):
        ops = [operation("w", "file_edit", "unknown", 2, path="src/app.py"),
               operation("p", "plan_snapshot", "succeeded", 3, basis="planning_snapshot",
                         path="src/other.py")]
        rows = reconciliation.observations(None, ops, [])
        edited = [row["value"] for row in rows if row["dimension"] == "edited"]
        self.assertEqual(edited, ["observed_snapshot"])

    def test_arbitrary_zero_exit_shell_is_not_verification(self):
        ops = [operation("c", "command", "succeeded", 2, command="make build")]
        rows = reconciliation.observations(None, ops, [])
        self.assertFalse([row for row in rows if row["dimension"] == "verified"])

    def test_failed_commit_result_is_not_committed_state(self):
        ops = [operation("e", "file_edit", "succeeded", 2, path="src/app.py")]
        wits = [witness("w", None, 3, confidence="unresolved", failed=True, sha=None, recorded_sha="b" * 40)]
        rows = reconciliation.observations(None, ops, wits)
        committed = [row for row in rows if row["dimension"] == "committed"]
        self.assertEqual([row["value"] for row in committed], ["commit_failed"])
        self.assertEqual(committed[0]["evidence_kind"], "tool_observation")
        self.assertEqual(reconciliation.summarize(rows, [])["committed"]["state"], "observed")

    def test_subject_inference_does_not_establish_committed_state(self):
        wits = [witness("w", "a" * 40, 3, confidence="inferred", basis="repo_subject")]
        rows = reconciliation.observations(None, [], wits)
        self.assertEqual(rows[0]["value"], "subject_inferred")
        self.assertEqual(rows[0]["evidence_kind"], "context")


class ClaimTests(unittest.TestCase):
    def test_uncommitted_claim_inside_coverage_contradicts(self):
        cp = checkpoint(currentState="Changes are uncommitted.")
        claims = reconciliation.claims_for(cp)
        observations = reconciliation.observations(None, [], [witness("w", "a" * 40, 4)])
        rows = reconciliation.compare(cp, claims, observations)
        self.assertEqual([row["relation"] for row in rows], ["contradicts"])
        self.assertEqual(rows[0]["reason"], "observation_inside_covered_range")

    def test_commit_after_boundary_is_later_observation_not_contradiction(self):
        cp = checkpoint(boundary=1, currentState="uncommitted")
        observations = reconciliation.observations(None, [], [witness("w", "a" * 40, 4)])
        rows = reconciliation.compare(cp, reconciliation.claims_for(cp), observations)
        self.assertEqual([row["relation"] for row in rows], ["later_observation"])
        self.assertEqual(rows[0]["reason"], "observation_after_coverage_boundary")

    def test_parallel_branch_is_not_comparable(self):
        cp = checkpoint(currentState="uncommitted")
        cp["branch"] = "a-side"
        observations = reconciliation.observations(None, [], [witness("w", "a" * 40, 4)])
        rows = reconciliation.compare(cp, reconciliation.claims_for(cp), observations)
        self.assertEqual([row["relation"] for row in rows], ["not_comparable"])

    def test_unresolved_boundary_never_permits_contradiction(self):
        cp = checkpoint(status="ambiguous", currentState="uncommitted")
        observations = reconciliation.observations(None, [], [witness("w", "a" * 40, 4)])
        rows = reconciliation.compare(cp, reconciliation.claims_for(cp), observations)
        self.assertEqual([row["relation"] for row in rows], ["not_comparable"])
        self.assertEqual(rows[0]["reason"], "unresolved_coverage_boundary")

    def test_claim_extraction_keeps_verbatim_excerpts(self):
        cp = checkpoint(openIssues=["config edit blocked"], nextActions=["run tests"],
                        verificationState="tests passed", constraints=["never edit config"])
        claims = reconciliation.claims_for(cp)
        fields = {claim["field"] for claim in claims}
        self.assertEqual(fields, {"openIssues", "nextActions", "verificationState", "constraints"})
        self.assertTrue(all(claim["value"] == claim["excerpt"] for claim in claims))
        summary = reconciliation.summarize([], claims)
        self.assertEqual(summary["blocked_remaining"]["state"], "claimed")
        self.assertEqual(summary["verified"]["state"], "claimed")

    def test_unsupported_checkpoint_shape_yields_no_invented_claims(self):
        cp = checkpoint()
        cp["structured"] = ["not", "a", "mapping"]
        self.assertEqual(reconciliation.claims_for(cp), [])


if __name__ == "__main__":
    unittest.main()
