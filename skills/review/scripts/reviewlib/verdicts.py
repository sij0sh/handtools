"""review's verdict rules: what confirms, rejects, merges or leaves a bug candidate unresolved, and what
a test gap is. The shared audit bookkeeping calls judge(); these rules are review's alone.

- confirmed: a repeatable counterexample (an approved command's run) or a complete source argument
  (trigger -> fault -> effect, every step cited, callers and guards checked). Diff mode adds origin
  (introduced | pre-existing with baseline evidence at the merge base, or unknown with a reason).
- rejected: counterevidence that neutralizes the claim. A failed tool is never counterevidence.
- duplicate: another live candidate. unresolved: a reason and at least one recorded attempt.
A missing or weak test is a test gap, never a finding.
"""
import re

from _engine.audit import evidence
from . import checks

LEVELS = ('high', 'medium', 'low')
ORIGINS = ('introduced', 'pre-existing', 'unknown')
ROLES = ('trigger', 'fault', 'effect')
CHAIN_BREAKS = ('no-test', 'no-assertion', 'wrong-assertion', 'unrealistic-setup', 'not-in-ci', 'skipped', 'flaky')
TEST_GAP_CAP = 100
TID = re.compile(r'^T[1-9][0-9]*$')
need, text = evidence.need, evidence.text


def _steps(root, items, where, roles=False):
    need(isinstance(items, list) and items, f'{where}: list at least one step.')
    out = []
    for i, s in enumerate(items):
        w = f'{where} [{i}]'
        need(isinstance(s, dict), f'{w}: each step is an object.')
        item = {'evidence': evidence.hash_refs(root, s.get('evidence', []), w)}
        if roles:
            need(s.get('role') in ROLES, f'{w}: role is one of {", ".join(ROLES)}.')
            item.update(role=s['role'], claim=text(s, 'claim', w))
        else:
            item['what'] = text(s, 'what', w)
        out.append(item)
    return out


def _proof(root, proof, allowed, where):
    need(isinstance(proof, dict) and proof.get('kind') in ('counterexample', 'source_argument'),
         f'{where}: confirmed needs `proof` with kind counterexample|source_argument.')
    if proof['kind'] == 'counterexample':
        need(proof.get('repeatable') is True, f'{where}: a counterexample must be repeatable ("repeatable": true).')
        return {'kind': 'counterexample', 'repeatable': True, 'observed': text(proof, 'observed', where),
                'command_run': evidence.command_run(proof.get('command_run'), allowed, f'{where} command_run')}
    steps = _steps(root, proof.get('steps'), f'{where} steps', roles=True)
    missing = [r for r in ROLES if r not in {s['role'] for s in steps}]
    need(not missing, f'{where}: a source argument covers trigger -> fault -> effect; missing {", ".join(missing)}.')
    need(steps[-1]['role'] == 'effect', f'{where}: a source argument ends at the observable effect.')
    mitigations = _steps(root, proof.get('mitigations_checked'), f'{where} mitigations_checked (callers, guards)')
    return {'kind': 'source_argument', 'steps': steps, 'mitigations_checked': mitigations}


def _origin(root, v, frame, allowed, where):
    origin = v.get('origin')
    need(origin in ORIGINS, f'{where}: diff mode needs origin {"|".join(ORIGINS)}.')
    if origin == 'unknown':
        return {'origin': origin, 'origin_reason': text(v, 'origin_reason', where)}
    base = frame['diff']['merge_base']
    b = v.get('baseline')
    need(isinstance(b, dict) and (b.get('evidence') or b.get('command_run')),
         f'{where}: origin {origin} needs `baseline` evidence at the merge base {base}: '
         '{"evidence": [refs with "revision": merge base]} or {"command_run": a run at the merge base}.')
    out = {'origin': origin, 'baseline': {'statement': text(b, 'statement', where)}}
    if b.get('evidence'):
        refs = evidence.hash_refs(root, b['evidence'], f'{where} baseline')
        need(all(r.get('revision') == base for r in refs), f'{where}: baseline refs need "revision": "{base}".')
        out['baseline']['evidence'] = refs
    if b.get('command_run'):
        run = evidence.command_run(b['command_run'], allowed, f'{where} baseline')
        need(run['revision'] == base, f'{where}: the baseline run must be at the merge base {base}.')
        out['baseline']['command_run'] = run
    return out


def judge_for(state, root):
    """The judge passed to audit.candidates.settle for this run."""
    frame, cands = state['frame'], state['candidates']

    def judge(cand, v, where):
        kind = v['state']
        if kind == 'confirmed':
            need(v.get('severity') in LEVELS and v.get('confidence') in LEVELS,
                 f'{where}: confirmed needs severity and confidence (high|medium|low), judged separately.')
            out = {'state': kind, 'severity': v['severity'], 'confidence': v['confidence'],
                   'proof': _proof(root, v.get('proof'), checks.allowed(state), where)}
            if frame['mode'] == 'diff':
                out.update(_origin(root, v, frame, checks.allowed(state), where))
            if frame['mode'] == 'bug' and v.get('explains_report') is True:
                out['explains_report'] = True
            refs = [r for s in out['proof'].get('steps', []) + out['proof'].get('mitigations_checked', [])
                    for r in s['evidence']]
            out['refs'] = refs + out.get('baseline', {}).get('evidence', [])
            return out
        if kind == 'rejected':
            basis = v.get('attempts', [])
            need(isinstance(basis, list) and all(type(i) is int and 1 <= i <= len(cand['attempts']) for i in basis),
                 f'{where}: `attempts` lists this candidate\'s attempt numbers (1 = first).')
            failed = [i for i in basis if cand['attempts'][i - 1]['outcome'] == 'tool-failed']
            need(not failed, f'{where}: attempt(s) {failed} failed as tools; a failed tool is not evidence against '
                             'the claim. Leave the candidate unresolved or find counterevidence.')
            refs = evidence.hash_refs(root, v.get('counterevidence', []), f'{where} counterevidence')
            return {'state': kind, 'reason': text(v, 'reason', where), 'counterevidence': refs,
                    'attempts': basis, 'refs': refs}
        if kind == 'duplicate':
            other = v.get('duplicate_of')
            need(other in cands and other != cand['id'] and cands[other]['state'] != 'duplicate',
                 f'{where}: duplicate needs `duplicate_of`, another candidate that is not itself a duplicate.')
            return {'state': kind, 'duplicate_of': other, 'refs': []}
        need(cand['attempts'], f'{where}: unresolved needs at least one recorded attempt (what was tried).')
        return {'state': kind, 'reason': text(v, 'reason', where), 'refs': []}

    return judge


def test_gap(gaps, item, obligation, root, used, where):
    """A test gap: a contract the suite would not catch breaking. Never a bug finding."""
    need(isinstance(item, dict), f'{where}: each test gap is an object.')
    tid = item.get('id')
    need(isinstance(tid, str) and TID.match(tid), f'{where}: test gap ids are T<n>.')
    need(tid not in used, f'{where}: {tid} was already used in this run; ids are never reused.')
    need(len(gaps) < TEST_GAP_CAP, f'{where}: at most {TEST_GAP_CAP} test gaps per run.')
    w = f'{where} {tid}'
    need(item.get('chain_break') in CHAIN_BREAKS, f'{w}: chain_break is one of {", ".join(CHAIN_BREAKS)}.')
    gap = {'id': tid, 'obligation': obligation, 'contract': text(item, 'contract', w),
           'chain_break': item['chain_break'], 'consequence': text(item, 'consequence', w),
           'evidence': evidence.hash_refs(root, item.get('evidence', []), w)}
    used.add(tid)
    gaps[tid] = gap
    return tid
