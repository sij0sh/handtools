#!/usr/bin/env python3
"""Three-phase instruction workflow: frame -> compose -> challenge.

Local, guarded state. The engine routes phases and runs one challenge review; it
never writes the target instruction. Python 3.11+, POSIX, standard library only.
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
PRINCIPLES = Path(__file__).resolve().parents[1] / 'references' / 'principles.md'


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
    keys(state, ('version', 'root', 'request', 'ticket', 'phase',
                 'frame', 'candidate', 'challenge', 'fingerprint'))
    require(state['version'] == 2 and type(state['version']) is int, 'unsupported state version')
    require(state['root'] == str(root), 'state root mismatch')
    require(text(state['request']), 'invalid request')
    require(state['phase'] in PHASES, 'invalid phase')
    require(state['frame'] is None or frame_ok(state['frame']), 'invalid frame')
    require(state['candidate'] is None or text(state['candidate'], CANDIDATE), 'invalid candidate')
    require(state['challenge'] is None or pass_ok(state['challenge']) or revise_ok(state['challenge']),
            'invalid challenge')
    require(state['fingerprint'] is None or text(state['fingerprint'], 200), 'invalid target fingerprint')
    if state['phase'] == 'complete':
        require(state['ticket'] == '', 'complete state needs no ticket')
        require(frame_ok(state['frame']) and text(state['candidate'], CANDIDATE), 'complete state lacks work')
        require(pass_ok(state['challenge']) or revise_ok(state['challenge']), 'complete state lacks challenge')
    else:
        require(re.fullmatch(r'[0-9a-f]{32}', state['ticket']) is not None, 'invalid ticket')
    if state['phase'] == 'frame':
        require(state['frame'] is None and state['candidate'] is None
                and state['challenge'] is None, 'frame state mismatch')
    elif state['phase'] == 'compose':
        require(frame_ok(state['frame']) and state['challenge'] is None, 'compose state mismatch')
    elif state['phase'] == 'challenge':
        require(frame_ok(state['frame']) and text(state['candidate'], CANDIDATE)
                and state['challenge'] is None, 'challenge state mismatch')


def new_state(root, request):
    require(text(request), 'request must be nonempty text')
    return {'version': 2, 'root': str(root), 'request': request, 'ticket': uuid.uuid4().hex,
            'phase': 'frame', 'frame': None, 'candidate': None,
            'challenge': None, 'fingerprint': None}


def rotate(state):
    state['ticket'] = uuid.uuid4().hex


def advance(root, state, result):
    require(isinstance(result, dict), 'result must be a JSON object')
    status, phase = result.get('status'), state['phase']
    if phase == 'frame':
        require(status == 'frame' and frame_ok(result), 'frame result shape invalid')
        state.update(frame=result, phase='compose', candidate=None,
                     challenge=None, fingerprint=fingerprint(root, result['target']))
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
        require(pass_ok(result) or revise_ok(result), 'challenge needs pass or revise result')
        state.update(challenge=result, phase='complete', ticket='')
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


def compose_prompt():
    return f'''TASK: compose

Read {PRINCIPLES}. Write the smallest instruction set that preserves the intended outcome and
constraints. Do not write the target yet.

Return JSON:
{{"status":"compose","candidate":"full candidate text"}}'''


def challenge_prompt():
    return '''TASK: challenge

Use one subagent; this is the only challenge review. Do not revise or write the
candidate. Justify retention by removal. For each instruction, ask: "What distinct,
consequential failure would removing this permit?" Remove or combine instructions
without a defensible answer. Move mechanical enforcement into scripts or references.
Report a recommendation; the main orchestrator decides what to do with it.

Return pass:
{"status":"pass","case":"...","evidence":"...","necessity":"...","removed":["..."],"unresolved":["..."]}
or revise:
{"status":"revise","case":"compliant-but-failing case","evidence":"why it fails","fix":"affected text to revise"}'''


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
        print(f'DONE\nOutput contract: {contract}')
        print('Removed rules: ' + ('; '.join(challenge['removed']) if challenge['removed'] else 'none reported'))
        print('Unresolved risks: ' + ('; '.join(challenge['unresolved']) if challenge['unresolved'] else 'none reported'))
    else:
        print(f"DONE: challenge recommends revision\nOutput contract: {contract}")
        print(f"Challenge finding: {challenge['case']}")
        print(f"Evidence: {challenge['evidence']}")
        print(f"Suggested fix: {challenge['fix']}")
    print('Decide whether to apply the candidate as-is, revise it, or stop; the engine does not revise or write the target.')


def show(root, state):
    if state['phase'] == 'complete':
        finished(state)
        return
    prompt = {'frame': frame_prompt, 'compose': compose_prompt, 'challenge': challenge_prompt}[state['phase']]
    print(prompt())
    print(f"State: {root / STATE}")
    context = {key: state[key] for key in ('request', 'phase', 'frame', 'candidate')}
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
