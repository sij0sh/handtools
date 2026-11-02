"""Transient operation/checkpoint facts and structured commit witnesses."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from helper import commit_links, operation_facts
from helper.git_resolve import GitResolver
from helper.options import ScanOptions
from helper.reader import scan_file
from helper.records import RecordCache, new_scope

FIXTURE = ROOT / "tests/fixtures/recordings/pi-slice1.jsonl"


def recording():
    return scan_file(FIXTURE, ScanOptions(harness="pi", max_text_bytes=1024 * 1024), new_scope())


class OperationFactTests(unittest.TestCase):
    def setUp(self):
        self.recording = recording()
        self.rows, self.coverage = operation_facts.operations([self.recording], RecordCache())

    def test_multi_path_plan_snapshot_is_one_operation(self):
        plan = [row for row in self.rows if row["action"] == "plan_snapshot"]
        self.assertEqual(len(plan), 2)
        self.assertEqual(len({row["operation_id"] for row in plan}), 1)
        self.assertEqual([row["association"] for row in plan], [0, 1])
        self.assertEqual({row["path"] for row in plan}, {"src/app.py", "src/other.py"})
        self.assertTrue(all(row["basis"] == "planning_snapshot" for row in plan))

    def test_unknown_write_keeps_unknown_outcome_and_no_edit_claim(self):
        write = next(row for row in self.rows if row["tool"] == "write")
        self.assertEqual(write["outcome"], "unknown")
        self.assertEqual(write["pairing"], "call_without_result")
        self.assertEqual(write["operation_id"], write["association_key"].rsplit(":", 1)[0])
        self.assertFalse(self.coverage["complete"])

    def test_structured_tools_are_distinct_from_native_operations(self):
        commit = next(row for row in self.rows if row["action"] == "commit_plan" and row["outcome"] == "succeeded")
        self.assertEqual(commit["interpretation"], "structured")
        self.assertEqual(commit["adapter"], "pi:git_commit_plan")
        unknown = next(row for row in self.rows if row["tool"] == "mystery")
        self.assertEqual(unknown["interpretation"], "generic")
        self.assertEqual(self.coverage["unsupported_tools"], {"mystery": 1})

    def test_checkpoint_boundaries_resolve_by_lane_not_publication_time(self):
        rows, coverage = operation_facts.checkpoints([self.recording], RecordCache())
        ok = next(row for row in rows if row["coverage_end_id"] == "u1")
        stale = next(row for row in rows if row["coverage_end_id"] == "u2")
        self.assertEqual(ok["boundary_status"], "resolved")
        self.assertEqual(ok["boundary_order"], 1)
        self.assertEqual(stale["boundary_status"], "off_branch")
        self.assertLess(stale["boundary_order"], stale["order"])
        self.assertEqual(coverage["resolved"], 1)
        self.assertEqual(coverage["off_branch"], 1)


    def test_missing_commit_result_is_not_inferred_from_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "missing.jsonl"
            rows = [
                {"type": "session", "id": "missing", "cwd": temp},
                {"type": "message", "id": "u", "message": {"role": "user", "content": "Commit it"}},
                {"type": "message", "id": "a", "parentId": "u", "message": {"role": "assistant", "content": [
                    {"type": "toolCall", "id": "c", "name": "git_commit_plan",
                     "arguments": {"subject": "Plan", "sha": "d" * 40}}]}},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            recording = scan_file(path, ScanOptions(harness="pi"), new_scope())
            rows = commit_links.witnesses([recording], GitResolver(), RecordCache(), ROOT)
            self.assertTrue(rows)
            self.assertIsNone(rows[0]["sha"])
            self.assertIsNone(rows[0]["recorded_sha"])
            self.assertEqual(rows[0]["confidence"], "unresolved")

    def test_missing_and_unsupported_checkpoint_boundaries_stay_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "checkpoint.jsonl"
            rows = [
                {"type": "session", "id": "checkpoint", "cwd": temp},
                {"type": "shadow-compact.checkpoint", "id": "cp-missing", "coverageEndEntryId": "absent",
                 "structured": {"version": 1, "objective": "Missing boundary"}},
                {"type": "shadow-compact.checkpoint", "id": "cp-invalid", "structured": "not an object"},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            recording = scan_file(path, ScanOptions(harness="pi"), new_scope())
            facts, coverage = operation_facts.checkpoints([recording], RecordCache())
            self.assertEqual({row["boundary_status"] for row in facts}, {"missing", "invalid"})
            self.assertGreaterEqual(coverage["unsupported"], 1)
            self.assertFalse(coverage["complete"])
    def test_realistic_custom_checkpoint_variants_are_interpreted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "checkpoints.jsonl"
            rows = [
                {"type": "session", "id": "variants", "cwd": temp},
                {"type": "message", "id": "u", "message": {"role": "user", "content": "Boundary"}},
                {"type": "custom", "id": "cp-v3", "parentId": "u", "customType": "shadow-compact.checkpoint",
                 "data": {"version": 3, "summary": "legacy rendering",
                          "structured": {"objective": "Current shape"},
                          "coverage": {"coverageEndEntryId": "u"}}},
                {"type": "custom", "id": "cp-v1", "parentId": "u", "customType": "shadow-compact.checkpoint.v1",
                 "data": {"version": 1, "summary": "No coverage yet"}},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            recording = scan_file(path, ScanOptions(harness="pi"), new_scope())
            facts, coverage = operation_facts.checkpoints([recording], RecordCache())
            self.assertEqual(len(facts), 2)
            self.assertEqual([row["coverage_end_id"] for row in facts], ["u", None])
            self.assertEqual(facts[0]["boundary_status"], "resolved")
            self.assertEqual(facts[0]["structured"], {"objective": "Current shape"})
            self.assertEqual(facts[1]["boundary_status"], "invalid")
            self.assertEqual(facts[1]["structured"], "No coverage yet")

    def test_realistic_git_record_details_are_commit_witnesses(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "record.jsonl"
            call = {"type": "message", "id": "a", "message": {"role": "assistant", "content": [
                {"type": "toolCall", "id": "ok", "name": "git_record",
                 "arguments": {"subject": "Record it", "paths": ["src/app.py"]}}]}}
            success = {"type": "message", "id": "r-ok", "parentId": "a", "message": {
                "role": "toolResult", "toolCallId": "ok", "isError": False,
                "content": [{"type": "text", "text": "Created 123456789abc: Record it (1 path)."}],
                "details": {"sha": "d" * 40, "subject": "Record it"}}}
            failure = {"type": "message", "id": "r-fail", "parentId": "fail", "message": {
                "role": "toolResult", "toolCallId": "fail", "isError": True,
                "content": [{"type": "text", "text": "fatal: cannot commit"}], "details": {}}}
            rows = [
                {"type": "session", "id": "record", "cwd": temp},
                {"type": "message", "id": "u", "message": {"role": "user", "content": "Record"}},
                {"type": "message", "id": "fail", "parentId": "u", "message": {"role": "assistant", "content": [
                    {"type": "toolCall", "id": "fail", "name": "git_record", "arguments": {"subject": "Fail"}}]}},
                call, success, failure,
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            recording = scan_file(path, ScanOptions(harness="pi"), new_scope())
            facts, coverage = operation_facts.operations([recording], RecordCache())
            self.assertEqual(coverage["commit_records"], 2)
            self.assertTrue(any(row["action"] == "commit_record" for row in facts))
            witnesses = commit_links.witnesses([recording], GitResolver(), RecordCache(), ROOT)
            ok = next(row for row in witnesses if row["recorded_sha"] == "d" * 40)
            bad = next(row for row in witnesses if row["recorded_sha"] is None and row["failed"])
            self.assertTrue(ok["basis"].startswith("structured_commit_record"))
            self.assertFalse(ok["failed"])
            self.assertEqual(ok["subject"], "Record it")
            self.assertIsNone(bad["sha"])

    def test_structured_commit_result_is_a_witness_but_failure_is_not(self):
        rows = commit_links.witnesses([self.recording], GitResolver(), RecordCache(), ROOT)
        success = next(row for row in rows if row["recorded_sha"] == "b" * 40)
        failed = next(row for row in rows if row["recorded_sha"] == "c" * 40)
        self.assertEqual(success["sha"], "b" * 40)
        self.assertIn(success["basis"], ("structured_commit_result", "structured_commit_result+repo"))
        self.assertFalse(success["failed"])
        self.assertIsNone(failed["sha"])
        self.assertTrue(failed["failed"])
        self.assertEqual(success["relation"], "commit")
        self.assertIsNotNone(success["witness_id"])


if __name__ == "__main__":
    unittest.main()
