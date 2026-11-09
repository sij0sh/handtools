"""untangle's view of the shared recon snapshot (skills/_engine/recon): the pin chosen at MAP, the
record ids that map entries and findings cite, contracts inside and outside the audit boundary,
and citations that went stale. Recon state stays in the recon journal; untangle stores only the pin.
Recon completeness never counts as review coverage, and the audit boundary never edits recon scope.
"""
from pathlib import Path

from _engine.recon import guide, query, store
from .ledger import in_scope_files, need

GUIDE_CMD = f'python3 {guide.CLI} --root .'


def pin(state, payload, where='MAP'):
    """The payload's recon choice: {'run', 'revision'} of a closed snapshot, or {'none': reason}."""
    run, none = payload.get('recon_snapshot'), payload.get('recon_none')
    need((run is None) != (none is None),
         f'{where}: send `recon_snapshot` (a closed snapshot, "snap-N") or `recon_none` (why recon is not needed).')
    if none is not None:
        need(isinstance(none, str) and none.strip(), f'{where}: `recon_none` is the reason, as text.')
        return {'none': none}
    need(isinstance(run, str) and run.startswith('snap-'), f'{where}: `recon_snapshot` is a snapshot id, snap-N.')
    _, chain, closed = store.read(Path(state['root']), run)
    need(closed, f'{where}: {run} is open; `close` it before pinning it.')
    return {'run': run, 'revision': len(chain)}


def snapshot(state, chosen=None):
    chosen = chosen or state.get('recon') or {}
    return store.read(Path(state['root']), chosen['run'])[0] if chosen.get('run') else None


def check_refs(snap, refs, where):
    """`recon_refs` must be record ids present in the pinned snapshot."""
    need(isinstance(refs, list) and all(isinstance(r, str) for r in refs), f'{where}: `recon_refs` lists record ids.')
    if not refs:
        return
    need(snap is not None, f'{where}: `recon_refs` need a pinned recon snapshot.')
    unknown = [r for r in refs if r not in snap.get('records', {})]
    need(not unknown, f'{where}: not in the pinned snapshot: {", ".join(unknown)}.')


def cited(state):
    """Every recon id cited by the map and by findings."""
    out = set()
    for key in ('entry_points', 'observables'):
        for item in state.get('map', {}).get(key, []):
            out.update(item.get('recon_refs', []))
    for f in state.get('findings', {}).values():
        out.update(f.get('recon_refs', []))
    return sorted(out)


def stale(state):
    """{id: reason} for cited ids that are stale or gone in the newest snapshot descended from the pin."""
    chosen = state.get('recon') or {}
    if not chosen.get('run'):
        return {}
    return store.stale_refs(Path(state['root']), chosen['run'], cited(state))


def fresh_refs(state, refs, chosen):
    """True when no id in `refs` changed between the pin the conclusions were made under
    (state['recon']) and the snapshot `chosen` now."""
    if not refs:
        return True
    if not chosen.get('run'):
        return False
    before = (state.get('recon') or {}).get('run')
    return not store.changed_refs(Path(state['root']), before, chosen['run'], refs)


def _inside(state, rec):
    scope = in_scope_files(state) if state.get('ledger') else set()
    return any(ref['source'] == '.' and ref['path'] in scope for ref in rec.get('evidence', []))


def render(state):
    """Lines for the current-state view and the report."""
    chosen = state.get('recon')
    if not chosen:
        return []
    if chosen.get('none'):
        return ['', f'## Recon: none ({chosen["none"]})']
    snap = snapshot(state)
    lines = ['', f'## Recon: {chosen["run"]} at revision {chosen["revision"]} (pinned; journal is authoritative)']
    inside, outside = [], []
    for c in query.contracts(snap):
        rec = snap['records'][c['id']]
        row = (f'- {c["id"]} [{c["direction"]}, {c["classification"]}]: producers {", ".join(c["producers"])}; '
               f'consumers {", ".join(c["consumers"])}; owner {c["owner"]}; compatibility {c["compatibility"]}')
        (inside if _inside(state, rec) else outside).append(row)
    lines += ['Contracts with evidence inside the audit boundary:'] + (inside or ['- none'])
    lines += ['Contracts outside the audit boundary (recon only, not reviewed here):'] + (outside or ['- none'])
    gaps = query.gaps(snap)
    lines += ['Open discovery gaps:'] + ([f'- {g["id"]}: {g["question"]} (missing: {g["missing"]})' for g in gaps]
                                         or ['- none'])
    gone = stale(state)
    if gone:
        lines += ['Stale recon citations (refresh the snapshot; dependent conclusions need another pass):']
        lines += [f'- {k}: {v}' for k, v in sorted(gone.items())]
    return lines

