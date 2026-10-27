"""Shared bounded recording scan and lineage mechanics; no retained transcript data."""
import os
from pathlib import Path
from .reader import scan_file
from .budget import check
from .options import TEXT_BYTES_DEFAULT, TEXT_BYTES_AUTO_CAP

def _size(path):
    try:
        return os.stat(path).st_size
    except OSError:
        return 0


def text_budget(args, files, gscope):
    """Explicit --max-text-bytes, else the bytes this group will scan, within the default and the cap."""
    if args.max_text_bytes is not None:
        gscope["text_budget"] = args.max_text_bytes
        return args.max_text_bytes
    size = sum(_size(path) for path in files)
    budget = max(TEXT_BYTES_DEFAULT, min(size, args.max_scan_bytes, TEXT_BYTES_AUTO_CAP))
    gscope["text_budget"] = budget
    return budget


def _snapshot(path, scope, before):
    try:
        from pathlib import Path
        stat = Path(path).stat()
        scanned = scope.get("bytes_scanned", 0) - before
        scope.setdefault("snapshot", []).append({
            "file": str(Path(path).absolute()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "inode": stat.st_ino, "bytes_scanned": scanned, "scan_complete": scanned >= stat.st_size})
    except OSError:
        pass


def lineages(recordings):
    """Each recording's independent session: a subagent or fork counts with the session it was recorded from."""
    by_file = {r["file"]: r for r in recordings}
    def key(r, depth=0):
        parent = r.get("parent_session")
        if not parent:
            return r["session"]
        # Pi records the parent as a file path; resolve it to that recording's own lineage.
        found = by_file.get(parent)
        return key(found, depth + 1) if found is not None and found is not r and depth < 32 else parent
    return {r["file"]: key(r) for r in recordings}


def scan_group(files, options, counters):
    counters["bytes_selected"] = sum(_size(path) for path in files)
    recordings = []
    for path in files:
        check()
        if counters.get("event_limit_reached") or counters["bytes_scanned"] >= options.max_scan_bytes:
            counters["scan_complete"] = False
            counters["scan_limit_reached"] = counters["bytes_scanned"] >= options.max_scan_bytes
            counters["byte_limit_reached"] = counters["scan_limit_reached"]
            break
        before = counters["bytes_scanned"]
        recordings.append(scan_file(path, options, counters))
        counters["files_scanned"] += 1
        _snapshot(path, counters, before)
    return recordings
