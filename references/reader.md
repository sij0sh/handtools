# Setup

Python 3.11+ standard library only; SQL runs on stdlib SQLite. Optional tree-sitter
packages (`requirements.txt`) add Rust, Go, TS/JS and shell definitions and imports;
a missing grammar is reported per file, never installed. The macOS `/usr/bin/python3`
from Xcode is 3.9: use Homebrew or python.org.

`scripts/profiles` declares how each harness's JSONL becomes event rows; `settings.json`
lists recording roots. Unknown, malformed and oversized records stay visible as gaps,
and recorded branch/parent links are preserved where present.
