#!/usr/bin/env python3
"""Compatibility entrypoint; implementation lives in the shared helper package."""
from helper.runtime import main
from helper.graph_cli import parser, defaults, run, get_graph, deliver, incomplete

if __name__ == "__main__":
    raise SystemExit(main())
