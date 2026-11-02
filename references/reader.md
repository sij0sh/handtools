# Setup

- Python 3.11+, standard library only; SQL runs on stdlib SQLite.
- Optional tree-sitter packages (`requirements.txt`) add Rust, Go, TS/JS and shell definitions and imports; a missing grammar is reported per file, not installed.
- The macOS `/usr/bin/python3` from Xcode is 3.9: use Homebrew or python.org.
- `scripts/profiles` declares how harness JSONL becomes event rows; `settings.json` lists recording roots.
- Unknown, malformed, oversized records stay visible as gaps; recorded branch/parent links kept where present.
