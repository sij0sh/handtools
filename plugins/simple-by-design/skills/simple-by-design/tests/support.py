"""Shared imports and small result fixtures; these are not real-agent trials."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from engine.router import DispatchError  # noqa: E402,F401 (re-exported for tests)
from engine.state import Store  # noqa: E402,F401 (re-exported for tests)

CLI = ROOT / "scripts" / "sbd.py"
REQUEST = "Design a report-only greeting command. Print Hello once; do not implement it."
CANDIDATE = {"status": "candidate", "summary": "Use one print('Hello') command. Report only; no implementation.",
             "criteria": ["Running the command prints exactly one line: Hello."],
             "decisions": [{"id": "D1", "choice": "Plain print, no CLI framework.",
                            "basis": "Request: print Hello once.", "alternative": "A CLI framework.",
                            "tradeoff": "No argument parsing; none required.",
                            "revisit": "Options or subcommands are requested."}]}
PASS = {"status": "pass", "pair": "none: request fixes output and count.",
        "defeater": "none: criterion fails if output differs.", "decision": "none: D1 complete.",
        "unknown": "none: language and output are stated.",
        "basis": "Local review, not delegated. Planned tests are not reported as executed."}
REVISE = {"status": "revise", "gaps": [{"check": "defeater", "witness": "Criterion passes if Hello is printed twice.",
                                        "decision": "D1"}]}
BLOCKED = {"status": "blocked", "question": "Which language?", "needs": "Requester answer."}
RESOLVED = {**CANDIDATE, "status": "resolved",
            "criteria": ["Running the command prints exactly one line, Hello, once."],
            "resolutions": [{"witness": REVISE["gaps"][0]["witness"],
                             "answer": "Criterion now requires exactly one line.",
                             "basis": "Request: print Hello once."}]}
