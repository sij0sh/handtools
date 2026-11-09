"""Coverage obligations: a finite list of (target, check) pairs to examine, each with a reason.

Obligation: {id O<n>, target (path spec, flow or recon id), boundary, risk, check, rationale,
status, outcome | reason, evidence, recon_refs}. `examined` records the check performed and its
result; it never means proven safe. Only pairs the agent proposes with a rationale and the check's
applicability allows are accepted, under a hard cap, so there is no file-by-check product.
"""
import re

from . import evidence, packs

STATUSES = ('planned', 'investigating', 'examined', 'blocked', 'deferred', 'not-applicable')
OPEN = ('planned', 'investigating')
RESULTS = ('no-issue', 'candidates', 'test-gaps')
HARD_CAP = 200
ID = re.compile(r'^O[1-9][0-9]*$')
need, text = evidence.need, evidence.text


def order(ids):
    """Ids in numeric order (O2 before O10)."""
    return sorted(ids, key=lambda i: (len(i), i))


def add(obls, items, catalog, mode, cap, used, where):
    """Validate new obligations and add them as planned, all or none. `used` is every id ever issued."""
    need(isinstance(items, list), f'{where}: `obligations` must be a list.')
    new, issued = {}, set()
    pairs = {(o['target'], o['check']) for o in obls.values()}
    for o in items:
        need(isinstance(o, dict), f'{where}: each obligation is an object.')
        oid = o.get('id')
        need(isinstance(oid, str) and ID.match(oid), f'{where}: obligation ids are O<n>.')
        need(oid not in used and oid not in issued, f'{where}: {oid} was already used in this run; ids are never reused.')
        target = text(o, 'target', f'{where} {oid}')
        boundary = o.get('boundary')
        need(boundary in packs.BOUNDARIES, f'{where} {oid}: `boundary` is one of {", ".join(packs.BOUNDARIES)}.')
        text(o, 'risk', f'{where} {oid}')
        text(o, 'rationale', f'{where} {oid}')
        check = catalog.get(o.get('check'))
        need(check is not None, f'{where} {oid}: unknown check `{o.get("check")}`; see the loaded packs.')
        # A path spec's language comes from its extension; flows and recon ids have none.
        need(packs.applies(check, packs.language(target.split(':')[0]), boundary, mode),
             f'{where} {oid}: {check["id"]} does not apply to {target} ({boundary}, {mode} mode).')
        need((target, check['id']) not in pairs, f'{where} {oid}: {target} already has {check["id"]}.')
        pairs.add((target, check['id']))
        issued.add(oid)
        new[oid] = {'id': oid, 'target': target, 'boundary': boundary, 'risk': o['risk'],
                     'check': check['id'], 'rationale': o['rationale'], 'status': 'planned',
                     'evidence': [], 'recon_refs': list(o.get('recon_refs', []))}
    total = len(obls) + len(new)
    need(total <= min(cap, HARD_CAP), f'{where}: {total} obligations exceed max_obligations={min(cap, HARD_CAP)}.')
    obls.update(new)
    used.update(issued)


def resolve(obl, report, root, issued, where):
    """Apply one hunt report. `issued` = ids of candidates and test gaps this obligation produced."""
    status = report.get('status')
    need(status in STATUSES and status != 'planned', f'{where}: status is one of {", ".join(STATUSES[1:])}.')
    obl.pop('outcome', None)
    obl.pop('reason', None)
    if status == 'examined':
        out = report.get('outcome')
        need(isinstance(out, dict), f'{where}: examined needs `outcome` {{"performed", "result", "refs"}}.')
        text(out, 'performed', where)
        need(out.get('result') in RESULTS, f'{where}: outcome.result is one of {", ".join(RESULTS)}.')
        refs = out.get('refs', [])
        need(isinstance(refs, list) and set(refs) == set(issued),
             f'{where}: outcome.refs must list exactly the candidates and test gaps raised for it: {sorted(issued)}.')
        kinds = {r[0] for r in refs}
        need((out['result'] == 'no-issue') == (not refs), f'{where}: result no-issue means no refs, and refs need a result.')
        need(out['result'] != 'candidates' or 'C' in kinds, f'{where}: result candidates needs a C# ref.')
        need(out['result'] != 'test-gaps' or 'T' in kinds, f'{where}: result test-gaps needs a T# ref.')
        obl['evidence'] = evidence.hash_refs(root, report.get('evidence', []), where)
        obl['outcome'] = {'performed': out['performed'], 'result': out['result'], 'refs': sorted(refs)}
    else:
        need(not issued, f'{where}: only an examined obligation raises candidates or test gaps.')
        obl['reason'] = text(report, 'reason' if status != 'investigating' else 'note', where)
        obl['evidence'] = evidence.hash_refs(root, report.get('evidence', []), where, required=False)
    obl['status'] = status


def reopen(obl, why):
    obl.update(status='planned', reopened=why)
    obl.pop('outcome', None)


def queue(obls):
    return [i for i in order(obls) if obls[i]['status'] in OPEN]


def counts(obls):
    out = {s: 0 for s in STATUSES}
    for o in obls.values():
        out[o['status']] += 1
    return out
