#!/usr/bin/env python3
"""Compatibility entrypoint; implementation lives in the shared helper package."""
from helper.row_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
