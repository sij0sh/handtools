"""Golden path: a planned feature surfaces the earlier similar commit, its request and current paths."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from helper import recall


class RecallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.repo, self.cache, self.archive = self.home / "repo", self.home / "cache", self.home / "recordings"
        self.repo.mkdir()
        self.archive.mkdir()
        self.git("init", "-q")
        self.commit("Initial table view", **{"ui/table.tsx": "export function Table() {}\n"})
        self.export = self.commit("Add export button to table toolbar", **{
            "ui/export-button.tsx": "export function ExportButton() {}\n",
            "ui/table.tsx": "import { ExportButton } from './export-button';\n"})
        self.commit("Tune table spacing", **{"ui/table.css": ".table { gap: 4px }\n"})

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), "-c", "user.name=Test",
                                        "-c", "user.email=test@example.com", *args], text=True).strip()

    def commit(self, message, **files):
        for path, text in files.items():
            dest = self.repo / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def session(self, request, sha, subject):
        command = f'git commit -m "{subject}"'
        rows = [{"type": "session", "id": "past", "cwd": str(self.repo), "timestamp": "2026-08-01T10:00:00Z"},
                {"type": "message", "id": "u", "timestamp": "2026-08-01T10:00:01Z",
                 "message": {"role": "user", "content": request}},
                {"type": "message", "id": "a", "parentId": "u", "timestamp": "2026-08-01T10:05:00Z",
                 "message": {"role": "assistant", "content": [
                     {"type": "toolCall", "id": "c", "name": "bash", "arguments": {"command": command}}]}},
                {"type": "message", "id": "r", "parentId": "a", "timestamp": "2026-08-01T10:05:01Z",
                 "message": {"role": "toolResult", "toolCallId": "c", "toolName": "bash", "isError": False,
                             "content": [{"type": "text", "text": f"[main {sha[:7]}] {subject}\n 2 files changed"}]}}]
        (self.archive / "past.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    def recall(self, *words, sessions=True):
        extra = ["--recordings", str(self.archive)] if sessions else ["--no-sessions"]
        p = subprocess.run([sys.executable, str(ROOT / "scripts/remember.py"), "recall", *words, *extra,
                            "--repo", str(self.repo), "--cache", str(self.cache)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return json.loads(p.stdout)

    def test_planned_feature_finds_earlier_similar_commit(self):
        out = self.recall("add", "a", "csv", "download", "button", "to", "the", "table", sessions=False)
        top = out["results"][0]
        self.assertEqual(top["sha"], self.export)
        self.assertEqual(top["paths"][0], "ui/export-button.tsx")
        self.assertEqual(out["scope"]["terms"], ["csv", "download", "button", "table"])
        self.assertEqual(out["scope"]["window"]["commits"], 3)

    def test_linked_session_supplies_the_original_request(self):
        self.session("Users need to export the table; add a button", self.export, "Add export button to table toolbar")
        top = self.recall("export", "button")["results"][0]
        self.assertEqual(top["sha"], self.export)
        self.assertEqual(top["request"], "Users need to export the table; add a button")
        self.assertIn("@", top["cite"])

    def test_moved_and_deleted_paths_report_current_state(self):
        (self.repo / "ui/actions").mkdir()
        self.git("mv", "ui/export-button.tsx", "ui/actions/export-button.tsx")
        self.git("rm", "-q", "ui/table.css")
        self.git("commit", "-qm", "Reorganize ui actions")
        rows = {r["sha"]: r for r in self.recall("export", "button", "table", "spacing", sessions=False)["results"]}
        self.assertIn("ui/export-button.tsx -> ui/actions/export-button.tsx", rows[self.export]["paths"])
        spacing = next(r for r in rows.values() if r["subject"] == "Tune table spacing")
        self.assertEqual(spacing["paths"], ["ui/table.css -> gone"])

    def test_generic_words_only_is_an_input_error(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts/remember.py"), "recall", "add", "new", "ui",
                            "--no-sessions", "--repo", str(self.repo), "--cache", str(self.cache)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("descriptive words", json.loads(p.stdout)["error"])

    def test_rare_terms_outweigh_project_wide_terms(self):
        commits = [{"sha": str(i), "subject": f"table tweak {i}", "committed_at": "2026-01-01"} for i in range(9)]
        commits.append({"sha": "x", "subject": "table export", "committed_at": "2025-01-01"})
        _, rows = recall.rank("table export", commits, [], [], [], str(self.repo))
        self.assertEqual(rows[0]["sha"], "x")


if __name__ == "__main__":
    unittest.main()
