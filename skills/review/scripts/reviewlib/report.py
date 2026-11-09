"""Views of the run, rendered from journal state only: the state summary that opens each printed step,
the outcome decided when the run reaches REPORT, and report.md. render() reads no files, so the
same state always renders the same bytes (re-render and replay give identical reports)."""
from pathlib import Path

from _engine import storage
from _engine.audit import budgets, candidates, obligations, packs
from _engine.recon import pin, query
from . import checks

AREA = 'review'  # state: <state root>/review/<project key>/ (storage.py)
SEVERITY = ('high', 'medium', 'low')


def report_path(root, run_id):
    return storage.state_dir(AREA, Path(root)) / run_id / 'report.md'


def stale_recon(state):
    ids = set()
    for item in list(state.get('obligations', {}).values()) + list(state.get('candidates', {}).values()):
        ids.update(item.get('recon_refs', []))
    return pin.stale(Path(state['root']), state.get('recon'), ids)


def decide(state, forced=None):
    """Outcome and reasons when the run reaches REPORT; stored in state so the report never re-reads files."""
    reasons = [f'stopped at checkpoint: {forced}'] if forced else []
    q = obligations.queue(state['obligations'])
    reasons += [f'obligations not examined: {", ".join(q)}'] if q else []
    open_c = candidates.open_ids(state['candidates'])
    reasons += [f'candidates not validated: {", ".join(open_c)}'] if open_c else []
    for status in ('blocked', 'deferred'):
        ids = [i for i in obligations.order(state['obligations']) if state['obligations'][i]['status'] == status]
        reasons += [f'{status} obligations: {", ".join(ids)}'] if ids else []
    if state['frame']['unsupported']:
        reasons.append('no check pack for: ' + ', '.join(state['frame']['unsupported']))
    if state['frame']['mode'] == 'bug' and not any((c.get('verdict') or {}).get('explains_report')
                                                   for c in state['candidates'].values()):
        reasons.append('the reported symptom is not explained by a confirmed candidate')
    state['outcome'] = {'result': 'incomplete' if reasons else 'complete', 'reasons': reasons}


def _refs(refs):
    return '; '.join(f'{r["path"]}' + (f':{r["lines"]}' if r.get('lines') else '')
                     + (f'@{r["revision"][:12]}' if r.get('revision') else '') + f' ({r["statement"]})' for r in refs)


def _flat(value):
    return ' / '.join(line.strip() for line in value.strip().splitlines())


def runs(state):
    """Every recorded command run: standalone ones, attempts', proofs' and baselines'."""
    out = list(state['commands'])
    for c in (state['candidates'][i] for i in candidates.order(state['candidates'])):
        out += [a['command_run'] for a in c['attempts'] if 'command_run' in a]
        v = c.get('verdict') or {}
        out += [x['command_run'] for x in (v.get('proof') or {}, v.get('baseline') or {}) if 'command_run' in x]
    return out


def _spent(state, name):
    """Spent against a limit; max_obligations counts obligations, attempts_per_candidate the busiest candidate."""
    if name == 'max_obligations':
        return len(state['obligations'])
    if name == 'attempts_per_candidate':
        return max((len(c['attempts']) for c in state['candidates'].values()), default=0)
    return budgets.spent(state, name)


def _coverage(state):
    obls = state['obligations']
    lines = ['## Coverage', '', '| status | count |', '| --- | --- |']
    lines += [f'| {s} | {n} |' for s, n in obligations.counts(obls).items()]
    lines += ['', '`examined` means the check ran and its outcome is recorded, not that the code is proven safe.']
    for status in ('blocked', 'deferred', 'not-applicable', 'planned', 'investigating'):
        ids = [i for i in obligations.order(obls) if obls[i]['status'] == status]
        if ids:
            lines += ['', f'{status.capitalize()}:']
            lines += [f'- {i} {obls[i]["target"]} / {obls[i]["check"]}: {obls[i].get("reason", obls[i].get("reopened", ""))}'
                      for i in ids]
    lines += ['', 'Unsupported scope (no check pack): ' + (', '.join(state['frame']['unsupported']) or 'none')]
    lines += ['', '| obligation | target | check | status | result |', '| --- | --- | --- | --- | --- |']
    lines += [f'| {i} | {obls[i]["target"]} | {obls[i]["check"]} | {obls[i]["status"]} | '
              f'{(obls[i].get("outcome") or {}).get("result", "")} |' for i in obligations.order(obls)]
    return lines


def _candidate(c):
    v = c.get('verdict') or {}
    lines = [f'### {c["id"]}: {c["actual"]}', '',
             f'- Expected: {c["expected"]}', f'- Trigger: {c["trigger"]}', f'- Obligation: {c["obligation"]}',
             f'- Sources: {_refs(c["sources"])}']
    if v.get('state') == 'confirmed':
        lines.insert(2, f'Severity {v["severity"]}, confidence {v["confidence"]}'
                     + (f', origin {v["origin"]}' if v.get('origin') else '')
                     + (', explains the reported symptom' if v.get('explains_report') else '') + '.')
        lines.insert(3, '')
        p = v['proof']
        if p['kind'] == 'counterexample':
            r = p['command_run']
            lines += [f'- Proof (counterexample): `{r["command"]}` in a {r["cwd"]} at {r["revision"][:12]}, exit '
                      f'{r["exit"]}; observed: {p["observed"]}', f'  Output excerpt: {_flat(r["excerpt"])}']
        else:
            lines += ['- Proof (source argument):']
            lines += [f'  {n}. {s["role"]}: {s["claim"]} [{_refs(s["evidence"])}]' for n, s in enumerate(p['steps'], 1)]
            lines += [f'  - mitigation checked: {m["what"]} [{_refs(m["evidence"])}]' for m in p['mitigations_checked']]
        if v.get('origin') == 'unknown':
            lines.append(f'- Origin unknown: {v["origin_reason"]}')
        elif v.get('baseline'):
            b = v['baseline']
            lines.append(f'- Baseline: {b["statement"]}' + (f' [{_refs(b["evidence"])}]' if b.get('evidence') else '')
                         + (f' (run `{b["command_run"]["command"]}`, exit {b["command_run"]["exit"]})'
                            if b.get('command_run') else ''))
    elif v.get('state') == 'rejected':
        lines += [f'- Rejected: {v["reason"]}', f'- Counterevidence: {_refs(v["counterevidence"])}']
    elif v.get('state') == 'unresolved':
        lines += [f'- Unresolved: {v["reason"]}']
    lines += [f'- Attempt {n}: {a["method"]} -> {a["outcome"]}: {a["note"]}' for n, a in enumerate(c['attempts'])]
    return lines + ['']


def render(state, outcome=None):
    """report.md text from state alone."""
    outcome = outcome or state['outcome']
    f, cands, gaps = state['frame'], state['candidates'], state['test_gaps']
    by = {s: [cands[i] for i in candidates.order(cands) if cands[i]['state'] == s] for s in candidates.STATES}
    lines = [f'# Review {state["run_id"]}: {outcome["result"].upper()}', '',
             f'Mode: {f["mode"]}. Expected behavior: {f["expected"]}']
    if f.get('diff'):
        d = f['diff']
        lines.append(f'Diff: {d["base_ref"]} ({d["merge_base"][:12]} merge base) -> {d["head_ref"]}; changed: '
                     + ', '.join(d['changed'] + [p + ' (deleted)' for p in d['deleted']]))
    if f.get('bug'):
        b = f['bug']
        explained = [c['id'] for c in by['confirmed'] if c['verdict'].get('explains_report')]
        lines.append(f'Reported symptom: {b["symptom"]} (expected: {b["expected"]}; version {b["version"]}). '
                     + (f'Explained by {", ".join(explained)}.' if explained else 'Not explained.'))
    lines.append(f'Scope: {len(f["files"])} file(s). Report-only: nothing was changed or fixed.')
    if outcome['reasons']:
        lines += ['', 'Not complete because:'] + [f'- {r}' for r in outcome['reasons']]
    lines += ['', f'## Findings (confirmed): {len(by["confirmed"])}', '']
    for c in sorted(by['confirmed'], key=lambda c: (SEVERITY.index(c['verdict']['severity']), len(c['id']), c['id'])):
        lines += _candidate(c)
    lines += [f'## Unresolved candidates: {len(by["unresolved"]) + len(by["proposed"]) + len(by["validating"])}', '']
    for c in by['unresolved'] + by['proposed'] + by['validating']:
        lines += _candidate(c)
    lines += [f'## Rejected candidates: {len(by["rejected"])}', '']
    for c in by['rejected']:
        lines += _candidate(c)
    if by['duplicate']:
        lines += ['## Duplicates', ''] + [f'- {c["id"]} duplicates {c["verdict"]["duplicate_of"]}'
                                          for c in by['duplicate']] + ['']
    lines += [f'## Test gaps: {len(gaps)} (not bug findings)', '']
    lines += [f'- {t["id"]} [{t["chain_break"]}] {t["contract"]}: {t["consequence"]} [{_refs(t["evidence"])}]'
              for t in (gaps[i] for i in sorted(gaps, key=lambda i: (len(i), i)))] or ['- none']
    lines += [''] + _coverage(state)
    recon = state.get('recon') or {}
    lines += ['', '## Recon', '', f'Pinned: {recon["run"]} at revision {recon["revision"]}.' if recon.get('run')
              else f'None: {recon.get("none", "not chosen")}.']
    lines += ['', '## Commands run', '']
    lines += [f'- `{r["command"]}` ({r["cwd"]} at {r["revision"][:12]}): exit {r["exit"]}' for r in runs(state)] \
        or ['- none (static analysis only)']
    lines += ['', '## Limitations', '']
    lim = []
    if state.get('reviewer') == 'self':
        lim.append('Challenge was a self-review, not an independent reviewer.')
    if not state.get('reviewer'):
        lim.append('No challenge round ran.')
    lim += [f'Budget {k} fully used ({_spent(state, k)}/{v}).' for k, v in sorted(state['budgets'].items())
            if _spent(state, k) >= v]
    objections = state.get('objections', [])
    lim += [f'{len(objections)} challenge objection(s); '
            f'{sum(o["verdict"] == "accepted" for o in objections)} accepted.'] if objections else []
    lines += [f'- {x}' for x in lim] or ['- none recorded']
    return '\n'.join(lines) + '\n'


def write(state, root, outcome=None):
    path = report_path(root, state['run_id'])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(state, outcome), encoding='utf-8')
    return path


def _recon_lines(state, root):
    chosen = state.get('recon')
    if not chosen:
        return []
    if chosen.get('none'):
        return [f'Recon: none ({chosen["none"]}).']
    snap = pin.snapshot(Path(root), chosen)
    files = state['frame']['files']
    lines = [f'Recon: {chosen["run"]} at revision {chosen["revision"]} (pinned).', 'Contracts touching the scope:']
    rows = [c for c in query.contracts(snap)
            if any(r.get('source') == '.' and r['path'] in files for r in snap['records'][c['id']].get('evidence', []))]
    lines += [f'- {c["id"]} [{c["direction"]}]: producers {", ".join(c["producers"])}; consumers '
              f'{", ".join(c["consumers"])}' for c in rows] or ['- none']
    lines += ['Open discovery gaps:'] + ([f'- {g["id"]}: {g["question"]}' for g in query.gaps(snap)] or ['- none'])
    gone = stale_recon(state)
    lines += [f'Stale recon citations: {", ".join(sorted(gone))} (blocks a complete report)'] if gone else []
    return lines


def summary(state, root):
    """The state block that opens every printed step."""
    if 'frame' not in state:
        return 'Current state (from the journal): new run; nothing framed yet.\n'
    f = state['frame']
    obls, cands = state['obligations'], state['candidates']
    lines = ['Current state (from the journal; `show` prints parts as JSON):',
             f'Run {state["run_id"]}, rev {state.get("rev", 0)}, mode {f["mode"]}, {len(f["files"])} file(s) in scope, '
             f'check packs {", ".join(f["packs"])}; unsupported languages: {", ".join(f["unsupported"]) or "none"}.',
             'Budgets (spent/limit): ' + ', '.join(f'{k} {_spent(state, k)}/{v}'
                                                   for k, v in sorted(state['budgets'].items())),
             'Allowed commands: ' + (', '.join(f'`{c}`' for c in checks.allowed(state)) or 'none (static analysis only)')]
    if f.get('diff'):
        lines.append(f'Diff: merge base {f["diff"]["merge_base"]} -> {f["diff"]["head_ref"]}; changed '
                     + ', '.join(f['diff']['changed']))
    lines += _recon_lines(state, root)
    lines.append('Obligations: ' + (', '.join(f'{k} {v}' for k, v in obligations.counts(obls).items() if v) or 'none'))
    q = obligations.queue(obls)[:checks.HUNT_BATCH]
    if q:
        catalog = packs.load(f['packs'])
        lines.append('Next obligations:')
        for i in q:
            o, c = obls[i], catalog[obls[i]['check']]
            lines.append(f'- {i} {o["target"]} [{o["boundary"]}] {c["id"]}: {c["title"]}. Risk: {o["risk"]}. '
                         f'Needs: {"; ".join(c["evidence_required"])}. Falsifiers: {"; ".join(c["falsifiers"])}.'
                         + (f' Reopened: {o["reopened"]}.' if o.get('reopened') else ''))
    open_c = candidates.open_ids(cands)
    lines.append('Candidates: ' + (', '.join(f'{k} {v}' for k, v in candidates.counts(cands).items() if v) or 'none'))
    lines += [f'- {i} [{cands[i]["state"]}] {cands[i]["actual"]} (attempts {len(cands[i]["attempts"])})'
              + (f' Reopened: {cands[i]["reopened"]}.' if cands[i].get('reopened') else '')
              for i in open_c[:checks.VALIDATE_BATCH]]
    lines.append(f'Test gaps: {len(state["test_gaps"])}.')
    changed = checks.drift(state, Path(root))
    if changed:
        lines.append('SOURCE CHANGED since FRAME: ' + ', '.join(changed[:20])
                     + '. The next `done` reopens the items citing these and stops at CHECKPOINT.')
    if state.get('checkpoint'):
        lines.append(f'Checkpoint: {state["checkpoint"]["reason"]} (resume: {state["checkpoint"]["resume"]}).')
    return '\n'.join(lines) + '\n'
