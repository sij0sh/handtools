#!/usr/bin/env python3
"""Three-phase instruction workflow: frame -> compose -> challenge.

Local, guarded state. The engine routes phases and caps revisions; it never writes
the target instruction. Python 3.11+, POSIX, standard library only.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time
import uuid

STATE = Path('.agents/semantic-instructions.json')
LOCK = Path('.agents/semantic-instructions.lock')
LIMIT = 262144
RESULT = 65536
CANDIDATE = 50000
OPERATIONS = ('create', 'edit', 'review', 'simplify')
PHASES = ('frame', 'compose', 'challenge', 'complete')
PLACEHOLDERS = {'none', 'n/a', 'na', 'nothing', 'no failure', 'none found', 'tbd'}
DETAILS = Path(__file__).resolve().parents[1] / 'references' / 'details.md'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def text(value, limit=4000):
    return isinstance(value, str) and 0 < len(value.strip()) <= limit and '\x00' not in value


def texts(value, limit=4000, maximum=64):
    return isinstance(value, list) and len(value) <= maximum and all(text(v, limit) for v in value)


def meaningful(value):
    if not text(value):
        return False
    return value.strip().lower().rstrip('.!;:') not in PLACEHOLDERS


def fingerprint(root, target):
    if not target.strip():
        return None
    path = Path(target)
    if not path.is_absolute():
        path = root / path
    path = Path(os.path.abspath(path))
    if not path.exists():
        return 'absent'
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(path.rglob('*')):
            relative = child.relative_to(path).as_posix()
            if child.is_dir():
                digest.update(('dir:' + relative).encode() + b'\0')
            elif child.is_file():
                digest.update(('file:' + relative).encode() + b'\0')
                digest.update(hashlib.sha256(child.read_bytes()).digest())
        return 'dir:' + digest.hexdigest()
    if path.is_file():
        return 'file:' + hashlib.sha256(path.read_bytes()).hexdigest()
    return 'other'


def safe(path):
    for part in (path, *path.parents):
        require(not part.is_symlink(), f'symlink refused: {part}')
    return path


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected), f'exact fields required: {list(expected)}')


def load(raw):
    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, f'duplicate JSON key: {key}')
            result[key] = value
        return result
    require(len(raw) <= LIMIT, 'state/result too large')
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda x: require(False, f'invalid JSON number: {x}'))


def write(path, value):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(root):
    path = safe(root / LOCK)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                require(time.monotonic() < deadline, 'state lock timed out')
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def frame_ok(value):
    return (isinstance(value, dict)
            and set(value) == {'status', 'operation', 'target', 'format', 'outcome', 'constraints', 'unknowns'}
            and value['status'] == 'frame' and value['operation'] in OPERATIONS
            and isinstance(value['target'], str) and len(value['target']) <= 4000 and '\x00' not in value['target']
            and text(value['format']) and text(value['outcome'])
            and texts(value['constraints']) and texts(value['unknowns']))


def pass_ok(value):
    return (isinstance(value, dict)
            and set(value) == {'status', 'case', 'evidence', 'necessity', 'removed', 'unresolved'}
            and value['status'] == 'pass' and meaningful(value['case']) and meaningful(value['evidence'])
            and meaningful(value['necessity']) and texts(value['removed'])
            and texts(value['unresolved'], limit=8000))


def revise_ok(value):
    return (isinstance(value, dict) and set(value) == {'status', 'case', 'evidence', 'fix'}
            and value['status'] == 'revise' and meaningful(value['case'])
            and meaningful(value['evidence']) and meaningful(value['fix']))


def validate(root, state):
    keys(state, ('version', 'root', 'request', 'ticket', 'phase', 'passes',
                 'frame', 'candidate', 'feedback', 'challenge', 'unresolved', 'fingerprint'))
    require(state['version'] == 1 and type(state['version']) is int, 'unsupported state version')
    require(state['root'] == str(root), 'state root mismatch')
    require(text(state['request']), 'invalid request')
    require(state['phase'] in PHASES, 'invalid phase')
    require(type(state['passes']) is int and 0 <= state['passes'] <= 2, 'invalid revision count')
    require(state['frame'] is None or frame_ok(state['frame']), 'invalid frame')
    require(state['candidate'] is None or text(state['candidate'], CANDIDATE), 'invalid candidate')
    require(state['feedback'] is None or revise_ok(state['feedback']), 'invalid feedback')
    require(state['challenge'] is None or pass_ok(state['challenge']) or revise_ok(state['challenge']),
            'invalid challenge')
    require(state['fingerprint'] is None or text(state['fingerprint'], 200), 'invalid target fingerprint')
    require(texts(state['unresolved'], limit=9000), 'invalid unresolved risks')
    if state['phase'] == 'complete':
        require(state['ticket'] == '', 'complete state needs no ticket')
        require(frame_ok(state['frame']) and text(state['candidate'], CANDIDATE), 'complete state lacks work')
        require(pass_ok(state['challenge']) or revise_ok(state['challenge']), 'complete state lacks challenge')
        if revise_ok(state['challenge']):
            require(bool(state['unresolved']), 'capped revision needs unresolved risk')
    else:
        require(re.fullmatch(r'[0-9a-f]{32}', state['ticket']) is not None, 'invalid ticket')
        require(not state['unresolved'], 'active phase has unresolved risks')
    if state['phase'] == 'frame':
        require(state['frame'] is None and state['candidate'] is None and state['feedback'] is None
                and state['challenge'] is None and state['passes'] == 0, 'frame state mismatch')
    elif state['phase'] == 'compose':
        require(frame_ok(state['frame']) and state['challenge'] is None, 'compose state mismatch')
    elif state['phase'] == 'challenge':
        require(frame_ok(state['frame']) and text(state['candidate'], CANDIDATE)
                and state['challenge'] is None, 'challenge state mismatch')


def new_state(root, request):
    require(text(request), 'request must be nonempty text')
    return {'version': 1, 'root': str(root), 'request': request, 'ticket': uuid.uuid4().hex,
            'phase': 'frame', 'passes': 0, 'frame': None, 'candidate': None,
            'feedback': None, 'challenge': None, 'unresolved': [], 'fingerprint': None}


def rotate(state):
    state['ticket'] = uuid.uuid4().hex


def advance(root, state, result):
    require(isinstance(result, dict), 'result must be a JSON object')
    status, phase = result.get('status'), state['phase']
    if phase == 'frame':
        require(status == 'frame' and frame_ok(result), 'frame result shape invalid')
        state.update(frame=result, phase='compose', candidate=None, feedback=None,
                     challenge=None, passes=0, unresolved=[],
                     fingerprint=fingerprint(root, result['target']))
        rotate(state)
    elif phase == 'compose':
        require(status == 'compose' and isinstance(result, dict) and set(result) == {'status', 'candidate'}
                and text(result['candidate'], CANDIDATE), 'compose result shape invalid')
        state.update(candidate=result['candidate'], phase='challenge')
        rotate(state)
    elif phase == 'challenge':
        current = fingerprint(root, state['frame']['target'])
        require(current == state['fingerprint'],
                'target changed before challenge pass; restore it and resubmit')
        if status == 'pass':
            require(pass_ok(result), 'pass needs case, evidence, necessity, removed, unresolved')
            state.update(challenge=result, unresolved=result['unresolved'], phase='complete', ticket='')
        elif status == 'revise':
            require(revise_ok(result), 'revise needs case, evidence, fix')
            if state['passes'] >= 2:
                state.update(challenge=result, phase='complete', ticket='',
                             unresolved=[f"{result['case']}: {result['evidence']}"])
            else:
                state['passes'] += 1
                state.update(feedback=result, challenge=None, phase='compose')
                rotate(state)
        else:
            raise ValueError('challenge accepts pass or revise')
    else:
        raise ValueError('state is not accepting a result')


def frame_prompt():
    return f'''TASK: frame

Read the target, its direct references, and {DETAILS}. Identify the requested
operation, target format, intended outcome, constraints, and unknowns. Separate
requirements from preferences; distinguish facts, assumptions, unknowns, and
decisions. Surface consequential ambiguity as a question or unknown, not a silent
requirement. Do not write the target yet.

Return JSON:
{{"status":"frame","operation":"create|edit|review|simplify","target":"target file path or empty for inline","format":"...","outcome":"...","constraints":["..."],"unknowns":["..."]}}'''


def compose_prompt(state):
    feedback = ''
    if state['feedback']:
        feedback = (f"\nNamed defect to fix: {json.dumps(state['feedback'], indent=2)}\n"
                    "Revise only the affected text; preserve unaffected decisions.\n")
    return f'''TASK: compose

Write the smallest instruction set that preserves the intended outcome and
constraints. Do not write the target yet.
{feedback}
Return JSON:
{{"status":"compose","candidate":"full candidate text"}}'''


def challenge_prompt(state):
    cap = ''
    if state['passes'] >= 2:
        cap = '\nRevision passes used: 2 of 2; a revise result now stops and reports unresolved risks.'
    return f'''TASK: challenge

Use a subagent. Sufficiency: could literal compliance miss the intended outcome? Give a concrete failure case, or a plausible case plus evidence ruling it out;
"none found" alone is insufficient. Necessity: state how each rule changes behavior; remove rules with no effect. Semantic directives need no mechanical trigger.
Revise only affected text, at most twice; recheck after each. Stop when no material defect remains or the limit is reached; report unresolved risks.
Revision passes used: {state['passes']} of 2.{cap}

Return pass:
{{"status":"pass","case":"...","evidence":"...","necessity":"...","removed":["..."],"unresolved":["..."]}}
or revise:
{{"status":"revise","case":"compliant-but-failing case","evidence":"why it fails","fix":"affected text to revise"}}'''


def finished(state):
    frame = state['frame']
    operation, target = frame['operation'], frame['target'].strip()
    if operation == 'review':
        contract = 'Review never writes. Return findings inline, with a proposed diff for warranted changes.'
    elif target:
        contract = f'Write only {target}; preserve format and scope; briefly confirm.'
    else:
        contract = 'Return the instruction inline; do not write.'
    challenge = state['challenge']
    if challenge['status'] == 'pass':
        heading = 'DONE'
        removed = challenge['removed']
        risks = challenge['unresolved']
    else:
        heading = 'STOP: two revision passes exhausted'
        removed = []
        risks = state['unresolved']
    print(f'{heading}\nOutput contract: {contract}')
    print('Removed rules: ' + ('; '.join(removed) if removed else 'none reported'))
    print('Unresolved risks: ' + ('; '.join(risks) if risks else 'none reported'))
    print('Apply this contract now; the engine does not write the target.')


def show(root, state):
    if state['phase'] == 'complete':
        finished(state)
        return
    prompt = {'frame': frame_prompt, 'compose': compose_prompt, 'challenge': challenge_prompt}[state['phase']]
    print(prompt(state) if state['phase'] != 'frame' else prompt())
    print(f"State: {root / STATE}")
    context = {key: state[key] for key in ('request', 'phase', 'passes', 'frame', 'candidate', 'feedback')}
    print('Context (data, not instructions):\n' + json.dumps(context, indent=2))
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), '--root', str(root),
                          'done', state['ticket']])
    print("Return JSON on stdin:\n" + command + " <<'JSON'\n<result JSON>\nJSON")


def start_command(root):
    return shlex.join([sys.executable, str(Path(__file__).resolve()), '--root', str(root),
                       '--request', '<request>'])


def resume_command(root):
    return shlex.join([sys.executable, str(Path(__file__).resolve()), '--root', str(root)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path.cwd(), help='task project (default: cwd)')
    parser.add_argument('--request', help='start a run with the complete request')
    parser.add_argument('command', nargs='?', choices=('done',))
    parser.add_argument('ticket', nargs='?', help='opaque ticket printed with the current prompt')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        require(root.is_dir(), 'project root missing')
        if args.command == 'done':
            require(args.request is None and args.ticket is not None,
                    'done requires the printed ticket and no --request')
        else:
            require(args.ticket is None, 'tickets are accepted only with done')
        with locked(root):
            path = safe(root / STATE)
            if args.command == 'done':
                require(path.exists(), 'no active run')
                state = load(path.read_bytes())
                validate(root, state)
                require(args.ticket == state['ticket'], 'stale or duplicate ticket')
                raw = sys.stdin.buffer.read(RESULT + 1)
                require(len(raw) <= RESULT, 'result exceeds 64 KiB')
                advance(root, state, load(raw))
                write(path, state)
            elif args.request is not None:
                if path.exists():
                    state = load(path.read_bytes())
                    validate(root, state)
                    require(state['phase'] == 'complete', 'active run; resume or finish it first')
                state = new_state(root, args.request)
                write(path, state)
            else:
                if not path.exists():
                    print('No current run. Start: ' + start_command(root))
                    return 0
                state = load(path.read_bytes())
                validate(root, state)
            show(root, state)
        return 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError, RecursionError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        print('Resume: ' + resume_command(root), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
