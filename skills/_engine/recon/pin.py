"""A workflow's pin on a closed recon snapshot: choosing it, checking cited record ids, and finding
citations that went stale in newer snapshots. Workflows store only the pin ({'run', 'revision'}
or {'none': reason}); recon state stays in the recon journal. Shared by untangle and review.
"""
from pathlib import Path

from . import store


def need(cond, msg):
    if not cond:
        raise ValueError(msg)


def choose(root, payload, where):
    """The payload's recon choice: `recon_snapshot` (a closed snap-N) or `recon_none` (the reason)."""
    run, none = payload.get('recon_snapshot'), payload.get('recon_none')
    need((run is None) != (none is None),
         f'{where}: send `recon_snapshot` (a closed snapshot, "snap-N") or `recon_none` (why recon is not needed).')
    if none is not None:
        need(isinstance(none, str) and none.strip(), f'{where}: `recon_none` is the reason, as text.')
        return {'none': none}
    need(isinstance(run, str) and run.startswith('snap-'), f'{where}: `recon_snapshot` is a snapshot id, snap-N.')
    _, chain, closed = store.read(Path(root), run)
    need(closed, f'{where}: {run} is open; `close` it before pinning it.')
    return {'run': run, 'revision': len(chain)}


def snapshot(root, chosen):
    """Reduced state of the pinned snapshot, or None without one."""
    return store.read(Path(root), chosen['run'])[0] if (chosen or {}).get('run') else None


def check_refs(snap, refs, where):
    """`recon_refs` must be record ids present in the pinned snapshot."""
    need(isinstance(refs, list) and all(isinstance(r, str) for r in refs), f'{where}: `recon_refs` lists record ids.')
    if not refs:
        return
    need(snap is not None, f'{where}: `recon_refs` need a pinned recon snapshot.')
    unknown = [r for r in refs if r not in snap.get('records', {})]
    need(not unknown, f'{where}: not in the pinned snapshot: {", ".join(unknown)}.')


def stale(root, chosen, ids):
    """{id: reason} for cited ids that are stale or gone in the newest snapshot descended from the pin."""
    if not (chosen or {}).get('run') or not ids:
        return {}
    return store.stale_refs(Path(root), chosen['run'], sorted(ids))


def fresh(root, before, chosen, refs):
    """True when no id in `refs` changed between the pin `before` and the snapshot `chosen`."""
    if not refs:
        return True
    if not (chosen or {}).get('run'):
        return False
    return not store.changed_refs(Path(root), (before or {}).get('run'), chosen['run'], refs)
