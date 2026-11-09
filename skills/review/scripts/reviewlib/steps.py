"""review stages: order, prompts, and the transition for each step.

The script owns scope, fingerprints, obligations, candidate states, budgets and the report; the
agent investigates. Each printed step opens with the run state rendered from the journal (the
authority); `show` prints parts of it as JSON. report.md under <state root>/review/<project key>/
<run-id>/ is the only file written, and it is a view.
"""
from pathlib import Path

from _engine import storage
from _engine.audit import budgets, candidates, obligations, packs
from _engine.recon import guide
from . import checks, report, transitions
from .report import AREA  # noqa: F401  (flow.py reads steps.AREA)

MODE = 'stateful'
PLANNING = True  # FRAME needs a ready shared plan (engine-enforced)
ORDER = ['frame', 'recon', 'obligations', 'hunt', 'validate', 'challenge', 'report', 'checkpoint']
WORKFLOW = Path(__file__).resolve().parents[1] / 'workflow.py'
SHOW_PARTS = ('frame', 'recon', 'obligations', 'candidates', 'test_gaps', 'commands', 'objections', 'budgets',
              'coverage', 'outcome', 'checks')
RECON_CMD = f'python3 {guide.CLI} --root .'


def _at(text):
    """A step prompt that opens with the current state from the journal; @SHOW@ is the show command."""
    def prompt(root):
        state = storage.read_state(_path(root))
        return report.summary(state, root) + '\n' + text.replace('@SHOW@', f'python3 {WORKFLOW} --root {root} show')
    return prompt


def _path(root):
    return storage.state_dir(AREA, Path(root)) / 'workflow.json'


EVIDENCE = ('Evidence refs are [{"path": "shop/x.py", "lines": "10-14", "statement": "what these lines show"}]; '
            'the script hashes each file. Add "revision": "<full sha>" to cite a file as it was at that commit.')
COMMAND_RUN = ('A command run is {"command": exactly an approved command, "cwd": "worktree"|"tempdir", "revision": '
               '"<sha checked out there>"|"worktree", "exit": N, "output_sha256": "<sha256 of the full output>", '
               '"excerpt": "<= 2000 chars"}, where output is stdout and stderr combined. Never run commands in the project checkout itself: use `git worktree '
               'add <scratch dir> <sha>` (or a temp copy) and `git worktree remove --force` it afterwards. A command that fails for '
               'tooling reasons (missing dependency, timeout) is an attempt with outcome tool-failed, not evidence.')

PROMPTS = {
    'frame': _at(
        'Agree what to review with the user before reading code in depth. Report-only: never edit the project.\n'
        'Mode: diff (a change: base ref vs the checked-out HEAD or "worktree" for uncommitted changes; scope adds '
        'unchanged callers and consumers the change affects), subsystem (path specs), or bug (a reported symptom; '
        'scope is the suspected paths). State the expected behavior and where it comes from (spec, docs, tests, '
        'the report). Allowed commands default to none (static analysis); a test or build command runs project '
        'code, so list each exact command, its purpose and side effects, for the user to approve. Budgets are '
        'finite; suggested: hunt_transitions 10, validate_transitions 10, attempts_per_candidate 3, '
        'variant_obligations 5, challenge_rounds 2, max_obligations 40.\n'
        'Send {"plan": <ready shared plan>, "approved_by_user": true, "mode": "diff|subsystem|bug", "expected": '
        '"...", "diff": {"base": "main", "head": "HEAD|worktree"} (diff), "bug": {"symptom": "...", "expected": '
        '"...", "reproduction": "steps or none", "version": "..."} (bug), "scope": ["src/a.py", "src/pkg/", '
        '"src/b.py:10-80"], "allowed_commands": [{"command": "python3 -m unittest discover -s tests", "purpose": '
        '"...", "side_effects": "..."}], "budgets": {...all six...}}.\n'
        'After a reframe, earlier obligations, candidates and test gaps are kept; changed files were reopened.'),
    'recon': _at(
        'Map the contracts the scope touches: callers, downstream consumers, external interfaces and the '
        'state transitions the code owns. Use the shared recon snapshot at map depth around the scope; deepen '
        'only for a gap an obligation will need. Add related repositories only when the user supplies them.\n'
        + guide.prompt(RECON_CMD) + '\n'
        'Send {"recon_snapshot": "snap-N"} (closed), or {"recon_none": "why the review needs no external view"}. '
        'External uncertainty stays explicit as recon gaps; recon completeness is not review coverage.'),
    'obligations': _at(
        'List the finite behaviors, flows and risks to investigate, each as one (target, check) pair with a '
        'rationale. `@SHOW@ checks` prints the checks of the packs listed above (applicability, evidence '
        'needed, falsifiers, validation methods, limits). Choose only '
        'pairs that matter for this change or report: no file-by-check sweep. Include test checks (tests/...) '
        'for the contracts at risk: which important behavior would the suite fail to detect breaking? Do not '
        'exclude migrations, startup, IPC or infrastructure because they are hard to test. A target is a path '
        'spec (file or file:start-end), an entry point, or a recon id. Boundary is one of http, queue, schedule, '
        'db, file, subprocess, config, cli, library, test.\n'
        'Send {"obligations": [{"id": "O1", "target": "src/a.py:10-40", "boundary": "library", "check": '
        '"general/compatibility", "risk": "what could break", "rationale": "why this pair", "recon_refs": []}]}. '
        'Ids are never reused. Languages listed as unsupported are reported as coverage gaps.'),
    'hunt': _at(
        'Investigate the next obligations (listed above, up to 5 per step). Read surrounding code, callers and '
        'consumers; check mitigations before suspecting a bug. A suspicious pattern is a candidate, not a '
        'finding; a candidate cites a concrete violated expectation. A missing or weak test is a test gap, '
        'never a bug. In diff mode, consider unchanged callers and consumers the change affects.\n'
        + EVIDENCE + '\n' + COMMAND_RUN + '\n'
        'Send {"results": [{"id": "O1", "status": "examined", "outcome": {"performed": "what you checked", '
        '"result": "no-issue|candidates|test-gaps", "refs": ["C1", "T1"]}, "evidence": [...]}, {"id": "O2", '
        '"status": "blocked|deferred|not-applicable", "reason": "..."}, {"id": "O3", "status": "investigating", '
        '"note": "..."}], "candidates": [{"id": "C1", "obligation": "O1", "expected": "the contract and its '
        'source", "actual": "what the code does", "trigger": "input or sequence", "sources": [...evidence], '
        '"recon_refs": []}], "test_gaps": [{"id": "T1", "obligation": "O1", "contract": "...", "chain_break": '
        '"no-test|no-assertion|wrong-assertion|unrealistic-setup|not-in-ci|skipped|flaky", "consequence": "what '
        'breakage would go unnoticed", "evidence": [...]}], "commands_run": []}. outcome.refs lists exactly the '
        'candidates and test gaps raised for that obligation. Or send {"checkpoint": "reason"}.'),
    'validate': _at(
        'Validate the open candidates above (up to 3 per step). Confirm only with a repeatable counterexample '
        '(an approved command whose output shows the violation) or a complete source argument: ordered steps '
        'trigger -> fault -> effect, each cited, plus the callers and guards you checked. Look for '
        'counterevidence first: a caller that validates, a guard, a contract that allows the behavior. In diff '
        'mode, decide origin: introduced or pre-existing need baseline evidence at the merge base (refs with '
        '"revision" or a run there); otherwise unknown with a reason. Severity and confidence are separate. '
        'Mutation testing only for a named uncertainty, as an attempt with an approved command. Another '
        'symptom of a fault already confirmed is a duplicate (duplicate_of) unless it has a distinct '
        'consequence worth its own finding; say which in the verdict.\n'
        + EVIDENCE + '\n' + COMMAND_RUN + '\n'
        'Send {"candidates": [{"id": "C1", "attempt": {"method": "...", "outcome": "supports|refutes|'
        'inconclusive|tool-failed", "note": "...", "command_run": {...}, "uncertainty": "(mutation)"}, '
        '"verdict": {"state": "confirmed", "severity": "high|medium|low", "confidence": "high|medium|low", '
        '"proof": {"kind": "counterexample", "repeatable": true, "observed": "...", "command_run": {...}} | '
        '{"kind": "source_argument", "steps": [{"role": "trigger|fault|effect", "claim": "...", "evidence": '
        '[...]}], "mitigations_checked": [{"what": "...", "evidence": [...]}]}, "origin": "introduced|'
        'pre-existing|unknown", "baseline": {"statement": "...", "evidence": [...]}, "origin_reason": "...", '
        '"explains_report": true}}, {"id": "C2", "verdict": {"state": "rejected", "reason": "...", '
        '"counterevidence": [...]}}, {"id": "C3", "verdict": {"state": "duplicate", "duplicate_of": "C1"}}, '
        '{"id": "C4", "verdict": {"state": "unresolved", "reason": "what is missing"}}], "variants": '
        '[obligations for related variants worth checking], "commands_run": []}. Or send {"checkpoint": "reason"}.'),
    'challenge': _at(
        'Spawn a fresh reviewer subagent. Give it the project root and `@SHOW@` (state from the journal), not '
        'your summary; tell it to edit nothing and run only approved commands in a worktree. For each confirmed '
        'and unresolved candidate it checks counterarguments, mitigations, affected versions and downstream '
        'impact against the current source, and it names consequential omissions (callers, consumers, test '
        'gaps). If no subagent is available, review it yourself and send "reviewer": "self"; the report says '
        'so. Judge each objection.\n'
        'Send {"reviewer": "fresh|self", "objections": [{"claim": "...", "verdict": "accepted|rejected", '
        '"reason": "...", "reopen": ["C1", "O3"]}]}. Accepted objections reopen work, up to challenge_rounds.'),
    'report': _at(
        'The report below is rendered from the journal. Check it against the state; do not edit it. Present '
        'it to the user: confirmed findings, unresolved work, test gaps, coverage and limitations. Nothing is '
        'fixed; a fix is a separate task.\n\n@REPORT@\n'
        'Send {} to write @REPORT_PATH@ and close the run.'),
    'checkpoint': _at(
        'Show the user the reason, coverage and open work above and ask for one decision. Do not decide for '
        'them. Send one of:\n'
        '{"approved_by_user": true, "decision": "extend", "budgets": {"hunt_transitions": 20}, '
        '"allowed_commands": [], "scope": []}: raise the named budgets, add approved commands or scope, and '
        'resume.\n'
        '{"approved_by_user": true, "decision": "reframe"}: back to FRAME (after source drift, stale recon or a '
        'scope change); earlier work is kept and re-fingerprinted.\n'
        '{"approved_by_user": true, "decision": "publish_incomplete"}: write the report marked INCOMPLETE.'),
}


def _prompt_with_report(prompt):
    def wrapped(root):
        text = prompt(root)
        if '@REPORT@' in text:
            state = storage.read_state(_path(root))
            text = text.replace('@REPORT@', report.render(state)).replace(
                '@REPORT_PATH@', str(report.report_path(root, state['run_id'])))
        return text
    return wrapped


PROMPTS = {k: _prompt_with_report(v) for k, v in PROMPTS.items()}

DONE_MSG = (f'DONE: report.md is in the newest review-*/ folder under the review state directory '
            f'(<state root>/{AREA}/<project key>/). Present it and stop. Nothing was changed or fixed.')

CHECKS = {}  # each transition validates its own payload before changing state

TRANSITIONS = {'frame': transitions.on_frame, 'recon': transitions.on_recon,
               'obligations': transitions.on_obligations, 'hunt': transitions.on_hunt,
               'validate': transitions.on_validate, 'challenge': transitions.on_challenge,
               'report': transitions.on_report, 'checkpoint': transitions.on_checkpoint}


def advance(state, payload):
    """Return the next step, or None after the report is written."""
    phase = state['phase']
    state['rev'] = state.get('rev', 0) + 1
    root = Path(state['root'])
    if phase not in ('frame', 'checkpoint') and 'frame' in state:
        stop = transitions.guard_drift(state, root)
        if stop:
            return stop
    if phase in ('hunt', 'validate', 'challenge') and 'checkpoint' in payload:
        reason = checks.text(payload, 'checkpoint', phase.upper())
        return budgets.checkpoint_to(state, 'challenge' if phase == 'challenge' else 'work', reason)
    return TRANSITIONS[phase](state, payload)


def coverage(state):
    return {'obligations': obligations.counts(state.get('obligations', {})),
            'candidates': candidates.counts(state.get('candidates', {})),
            'test_gaps': len(state.get('test_gaps', {})),
            'unsupported': state.get('frame', {}).get('unsupported', [])}


def show(root, part=None):
    """Run state (or one part) from the journal, as JSON-ready data."""
    state = storage.read_state(_path(root))
    if part is None:
        return state
    if part not in SHOW_PARTS:
        raise ValueError(f'show: part is one of {", ".join(SHOW_PARTS)}.')
    if part == 'checks':
        return packs.load(state['frame']['packs'] if 'frame' in state else checks.PACKS)
    return coverage(state) if part == 'coverage' else state.get(part)


def on_abandon(state, root):
    """A run abandoned after FRAME leaves a report marked CANCELLED with what it covered."""
    if 'frame' not in state:
        return None
    outcome = {'result': 'cancelled', 'reasons': [f'abandoned by the user at {state["phase"].upper()}']}
    return f'Cancelled report: {report.write(state, root, outcome)}'
