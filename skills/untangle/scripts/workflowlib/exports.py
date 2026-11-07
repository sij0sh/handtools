"""Derived files under <root>/.agents/artifacts/untangle/<audit-id>/: current.md, audit.json, report.md."""
import time
from pathlib import Path

from . import storage
from .ledger import ART, policy_root
from .work import all_items, coverage_summary
from .checks import PITCH


def out_dir(state):
    return Path(state['root']) / ART / state['audit_id']


def render_current(state, phase):
    lines = [f'# untangle {state["audit_id"]}: rev {state["rev"]}', '', f'Phase: {phase.upper()}',
             f'Root: {state["root"]}', f'Policy: {policy_root()} (handtools {state["policy"].get("version")})']
    if state.get('units'):
        c = coverage_summary(state)
        lines += [f'Coverage: {c["reviewed"]}/{c["in_scope"]} in-scope files reviewed; {c["discovered"]} '
                  f'discovered; {len(c["excluded"])} excluded; blocked: {", ".join(c["blocked"]) or "none"}']
    if phase == 'map' and state.get('revise'):
        lines.append(f'User asked to revise the map: {state["revise"]}')
    if phase == 'dissect' and state.get('map', {}).get('conventions'):
        lines += ['', '## Project conventions (tier 2)'] + [
            f'- [{c["status"]}] {c["rule"]} ({c["source"]})' for c in state['map']['conventions']]
    if phase == 'scope':
        lines.append(f'map_rev: {state["map_rev"]}')
    if state.get('scope'):
        used = {'dissect_transitions': 'dissect', 'max_units': 'units', 'synth_reopens': 'synth',
                'challenge_rounds': 'challenge'}
        lines.append('Budgets: ' + ', '.join(f'{k} {state["counters"][used[k]]}/{v}' if k in used else f'{k} {v}'
                                             for k, v in state['scope']['budgets'].items()))
        lines.append(f'Allowed commands: {state["scope"]["allowed_commands"] or "none (static only)"}')
    if phase == 'dissect' and state['queue']:
        i = state['queue'][0]
        it = all_items(state)[i]
        lines += ['', f'## Current item: {i} ({it["kind"]}), send "item": "{i}", "rev": {state["rev"]}']
        if it['kind'] == 'flow':
            lines += [f'Entry: {it["where"]}', f'Flow to trace: {it["flow"]}']
        else:
            lines += [f'Responsibility: {it["responsibility"]}', f'Contracts: {it.get("contracts", "")}',
                      f'Depth: {it["depth"]}; passes: {it.get("passes", 0)}']
            if it.get('children'):
                lines.append(f'Children reviewed: {", ".join(it["children"])}: send "interactions".')
            lines += ['Ranges (send exactly these in "reviewed"):'] + [f'- {p}' for p in it['paths']]
            langs = sorted({state['ledger'][s.partition(':')[0]]['lang'] or '' for s in it['paths']})
            base = policy_root()
            for lang in langs:
                prof = f'languages/{lang}.md'
                lines.append(f'Profile: {base / prof}' if lang and prof in state['policy']['files']
                             else f'Profile: none for {lang or "unknown language"}; apply project and general '
                                  'rules and say so in findings.')
        lines.append(f'Queue after this: {", ".join(state["queue"][1:]) or "empty"}')
    if phase == 'checkpoint':
        cp = state['checkpoint']
        lines += ['', f'## Checkpoint: {cp["reason"]}', f'Resumes at: {cp["resume"]}',
                  f'Pending queue: {", ".join(state.get("queue", [])) or "empty"}']
    return '\n'.join(lines) + '\n'


def render_report(state, complete, reasons):
    c = coverage_summary(state)
    recs = state.get('recommendations', [])
    f = state['findings']
    head = 'COMPLETE (static assessment of the approved scope)' if complete else 'INCOMPLETE: ' + '; '.join(reasons)
    out = [f'# Untangle audit {state["audit_id"]}', '', f'Status: **{head}**',
           f'Snapshot: `{state["root"]}`, validated {time.strftime("%Y-%m-%d %H:%M:%S %Z")}; state rev '
           f'{state["rev"]}', f'Policy: simple-by-design from handtools {state["policy"].get("version")} at `{policy_root()}`',
           f'Reviewer: {state.get("reviewer", "none")}' + (' (self-review, not independent)'
                                                           if state.get('reviewer') == 'self' else ''),
           '', '## Coverage', '',
           f'- Discovered paths: {c["discovered"]}', f'- In scope: {c["in_scope"]}',
           f'- Reviewed: {c["reviewed"]}', f'- Unreviewed: {len(c["unreviewed"])}',
           f'- Blocked items: {", ".join(c["blocked"]) or "none"}',
           f'- Pending items: {", ".join(c["pending"]) or "none"}',
           f'- Excluded: {len(c["excluded"])}']
    out += [f'  - `{p}`: {r}' for p, r in sorted(c['excluded'].items())]
    out += [f'  - unreviewed `{p}`' for p in c['unreviewed']]
    out += ['', 'Full coverage does not prove semantic correctness.'
            + (' The in-scope source and policy matched the approved snapshot when this was validated.'
               if complete else '')]

    def rec(r):
        lines = ['', f'### {r["id"]}: {r["title"]}', '', f'Change: {r["change"]}']
        lines += [f'- Finding {i} at `{f[i]["where"]}` ({f[i]["evidence"]}; {f[i]["policy"]["tier"]}: '
                  f'{f[i]["policy"]["source"]}): {f[i]["summary"]}' for i in r['findings'] if i in f]
        for k in ('preserves', 'missing_evidence', 'verification', 'benefit', 'risk', 'effort'):
            if r.get(k):
                lines.append(f'- {k.replace("_", " ").capitalize()}: {r[k]}')
        for k in PITCH:
            if r.get('pitch', {}).get(k):
                lines.append(f'- {k.replace("_", " ").capitalize()}: {r["pitch"][k]}')
        if r.get('depends_on'):
            lines.append(f'- Depends on: {", ".join(r["depends_on"])}')
        return lines

    for track, title in (('A', 'Track A: preserve behavior'),
                         ('B', 'Track B: simplification bargains (approval requested; none approved)'),
                         ('gap', 'Evidence gaps')):
        out += ['', f'## {title}']
        chosen = [r for r in recs if r['track'] == track]
        out += sum((rec(r) for r in chosen), []) or ['', 'None.']
    out += ['', '## Refactor waves']
    out += [f'- {w["id"]}: {", ".join(w["recommendations"])}. Acceptance: {w["acceptance"]}'
            for w in state.get('waves', [])] or ['None.']
    used = {i for r in recs for i in r['findings']} | {d['finding'] for d in state.get('dismissed', [])}
    loose = [i for i in f if i not in used]
    out += ['', '## Findings not yet synthesized']
    out += [f'- {i} [{f[i]["track"]}] `{f[i]["where"]}`: {f[i]["summary"]}' for i in loose] or ['None.']
    out += ['', '## Dismissed findings']
    out += [f'- {d["finding"]}: {d["reason"]}' for d in state.get('dismissed', [])] or ['None.']
    out += ['', '## Challenge']
    out += [f'- [{o["verdict"]}] {o["claim"]}: {o["reason"]}' for o in state.get('objections', [])] or ['None.']
    out += ['', '## Limitations', '', f'- Commands run: {", ".join(state.get("commands_run", [])) or "none"}',
            '- Track A items are static inference unless marked verified; no equivalence tests were run.',
            '- B pitches need the user\'s decision; approving one does not authorize implementation.']
    return '\n'.join(out) + '\n'


def export(state, phase):
    out = out_dir(state)
    out.mkdir(parents=True, exist_ok=True)
    storage.write_json(out / 'audit.json', dict(state, phase=phase))
    (out / 'current.md').write_text(render_current(state, phase), encoding='utf-8')


def publish(state, complete, reasons):
    state['published'] = {'complete': complete, 'reasons': reasons}
    export(state, 'published')
    (out_dir(state) / 'report.md').write_text(render_report(state, complete, reasons), encoding='utf-8')
    return None
