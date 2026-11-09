"""Candidates: claims under validation. proposed -> validating -> confirmed|rejected|unresolved|duplicate.

Candidate: {id C<n>, obligation, expected, actual, trigger, sources (evidence), recon_refs, state,
attempts, verdict}. A suspicious pattern is a candidate, never a finding. What each terminal state
requires is the workflow's rule: settle() calls the `judge` function the workflow passes in. A stored
verdict lists every evidence ref it cites under `refs`, so drift checks can find them.
"""
import re

from . import evidence

STATES = ('proposed', 'validating', 'confirmed', 'rejected', 'unresolved', 'duplicate')
OPEN = ('proposed', 'validating')
TERMINAL = STATES[2:]
OUTCOMES = ('supports', 'refutes', 'inconclusive', 'tool-failed')
HARD_CAP = 100
ID = re.compile(r'^C[1-9][0-9]*$')
need, text = evidence.need, evidence.text


def order(ids):
    return sorted(ids, key=lambda i: (len(i), i))


def propose(cands, item, obligation, root, used, where):
    need(isinstance(item, dict), f'{where}: each candidate is an object.')
    cid = item.get('id')
    need(isinstance(cid, str) and ID.match(cid), f'{where}: candidate ids are C<n>.')
    need(cid not in used, f'{where}: {cid} was already used in this run; ids are never reused.')
    w = f'{where} {cid}'
    for key in ('expected', 'actual', 'trigger'):
        text(item, key, w)
    need(len(cands) < HARD_CAP, f'{where}: at most {HARD_CAP} candidates per run.')
    sources = evidence.hash_refs(root, item.get('sources', []), w)
    used.add(cid)
    cands[cid] = {'id': cid, 'obligation': obligation, 'expected': item['expected'], 'actual': item['actual'],
                  'trigger': item['trigger'], 'sources': sources,
                  'recon_refs': list(item.get('recon_refs', [])), 'state': 'proposed', 'attempts': []}
    return cid


def attempt(cand, item, allowed, limit, where):
    """Record one validation attempt. A tool failure is recorded as such: it is not evidence either way."""
    need(len(cand['attempts']) < limit, f'{where}: attempts_per_candidate={limit} used; settle it '
                                        '(unresolved is allowed) or send {"checkpoint": "reason"}.')
    need(isinstance(item, dict), f'{where}: `attempt` is an object.')
    text(item, 'method', where)
    need(item.get('outcome') in OUTCOMES, f'{where}: attempt outcome is one of {", ".join(OUTCOMES)}.')
    out = {'method': item['method'], 'outcome': item['outcome'], 'note': text(item, 'note', where)}
    if item['method'] == 'mutation':
        out['uncertainty'] = text(item, 'uncertainty', f'{where} (mutation testing resolves a named uncertainty)')
    if 'command_run' in item:
        out['command_run'] = evidence.command_run(item['command_run'], allowed, where)
    need(item['method'] != 'mutation' or 'command_run' in out, f'{where}: mutation testing needs a command_run.')
    cand['attempts'].append(out)
    cand['state'] = 'validating'
    return out


def settle(cand, verdict, judge, where):
    """Terminal state through the workflow's `judge(candidate, verdict, where) -> stored verdict`."""
    need(cand['state'] in OPEN, f'{where}: {cand["id"]} is already {cand["state"]}.')
    need(isinstance(verdict, dict) and verdict.get('state') in TERMINAL,
         f'{where}: verdict.state is one of {", ".join(TERMINAL)}.')
    cand['verdict'] = judge(cand, verdict, where)
    cand['state'] = verdict['state']


def reopen(cand, why):
    cand.update(state='proposed', reopened=why)
    cand.pop('verdict', None)


def open_ids(cands):
    return [i for i in order(cands) if cands[i]['state'] in OPEN]


def counts(cands):
    out = {s: 0 for s in STATES}
    for c in cands.values():
        out[c['state']] += 1
    return out


def cited(cand):
    """Evidence refs a candidate rests on: its sources plus the `refs` its stored verdict lists."""
    return list(cand['sources']) + list((cand.get('verdict') or {}).get('refs', []))
