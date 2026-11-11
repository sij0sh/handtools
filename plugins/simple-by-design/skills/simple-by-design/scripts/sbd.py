#!/usr/bin/env python3
"""Start/resume one focused design task; return results through the printed command."""

import argparse
from pathlib import Path
import shlex
import sys

from engine.prompts import render
from engine.router import DispatchError
from engine.state import Store, decode


def parser():
    result = argparse.ArgumentParser(description="Focused design prompts: start, return results, resume until DONE")
    result.add_argument("--root", type=Path, default=Path.cwd(), help="task project (default: cwd)")
    result.add_argument("--request", help="start with the complete request, constraints and permissions")
    result.add_argument("command", nargs="?", choices=("done",))
    result.add_argument("ticket", nargs="?", help="opaque ticket printed with the current prompt")
    return result


def main(argv=None):
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    if args.command == "done" and (args.request is not None or args.ticket is None):
        argument_parser.error("done requires a printed ticket and no --request; send result JSON on stdin")
    if args.ticket is not None and args.command != "done":
        argument_parser.error("tickets are accepted only with done")
    store = Store(args.root)
    script = Path(__file__).resolve()
    resume = " ".join(shlex.quote(str(value)) for value in ("python3", script, "--root", store.root))
    try:
        if args.command == "done":
            document = store.submit(args.ticket, decode(sys.stdin.read()))
        elif args.request is not None:
            document = store.start(args.request)
        else:
            document = store.resume()
        if document is None:
            print(f"No current run. Start: {resume} --request '<complete request>'")
        else:
            print(render(document, script, store.root))
        return 0
    except (DispatchError, OSError, UnicodeError, RecursionError) as error:
        print(f"sbd: {error}\nResume: {resume}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
