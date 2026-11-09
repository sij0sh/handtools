"""Pure reducer for recon `record.accepted` events: (state, event) -> state.

State of one snapshot run: {"snapshot": {...}, "records": {id: record}, "dropped": {id: reason},
"cost": {"files", "bytes", "commands"}}. Re-recording an id supersedes it; the chain keeps the
accepting events, so history is never rewritten. Duplicate events never reach here: replay dedupes.
"""
from . import records


def reduce(state, event):
    payload = event['payload']
    records.validate_envelope(payload)
    recs = dict(state.get('records', {}))
    dropped = dict(state.get('dropped', {}))
    accepted = {'revision': event['revision'], 'event_id': event['event_id']}
    for r in payload['records']:
        prior = recs.pop(r['id'], None)
        chain = (prior or {}).get('supersedes', []) + ([prior['accepted']] if prior else [])
        if r.get('drop'):
            dropped[r['id']] = {'reason': r['reason'], 'accepted': accepted, 'supersedes': chain}
            continue
        dropped.pop(r['id'], None)
        recs[r['id']] = dict(r, type=records.type_of(r['id']), status=r.get('status', 'current'),
                             accepted=accepted, supersedes=chain)
    cost = dict(state.get('cost') or {'files': 0, 'bytes': 0, 'commands': []})
    add = payload.get('cost', {})
    cost = {'files': cost['files'] + add.get('files', 0), 'bytes': cost['bytes'] + add.get('bytes', 0),
            'commands': cost['commands'] + add.get('commands', [])}
    return dict(state, records=recs, dropped=dropped, cost=cost)


REDUCERS = {records.SCHEMA: reduce}
