#!/usr/bin/env python3
"""Compatibility entrypoint; implementation lives in the shared helper package."""
from helper.session_cli import main
from helper.session_cli import parser, SHARED, ROWS

if __name__ == "__main__":
    raise SystemExit(main())
