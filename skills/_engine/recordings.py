"""Exact, opt-in receipt capture from Codex, Claude Code and pi tool results.

No fuzzy discovery, current-session exclusions, prose extraction, or guessed success.
Callers supply all recording paths and an expected head before advancing a run.
"""
import json
import shlex
from pathlib import Path
from .events import PROTOCOL, replay, validate


def command_is_engine(value):
    if isinstance(value, dict):
        value = value.get('command', value.get('cmd', ''))
    if not isinstance(value, str):
        return False
    try:
        words = shlex.split(value)
    except ValueError:
        return False
    # Only a direct Python invocation, never echo/cat/embedded examples or shell composition.
    if len(words) < 3 or not Path(words[0]).name.lower().startswith(('python', 'py')):
        return False
    script = Path(words[1])
    if script.name == 'engine.py':
        writes = ('append', 'start')
    elif script.name == 'cli.py' and script.parent.name == 'recon':
        writes = ('start', 'record', 'close')
    else:
        return False
    if any(w in words for w in (';', '&&', '||', '|')):
        return False
    args = words[2:]
    while args and args[0] in ('--root', '--backend', '--recording', '--format'):
        if len(args) < 2:
            return False
        args = args[2:]
    return bool(args and args[0] in writes)



def text_content(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ''.join(x.get('text', '') for x in value if isinstance(x, dict) and x.get('type') in ('text', 'output_text'))
    return ''


def receipts(paths, run, reducers=None):
    """Receipts for `run`, replay-checked. They are evidence of what a session saw, not accepted state."""
    result = []
    for name in paths:
        path = Path(name)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('recording exceeds exact-reader 64 MiB limit; no state inferred')
        calls = {}
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError('incomplete recording %s:%s' % (path, number)) from exc
            blocks = []
            if row.get('type') == 'response_item':
                blocks = [row.get('payload', {})]
            elif row.get('type') in ('assistant', 'user'):
                blocks = (row.get('message') or {}).get('content', [])
            elif row.get('type') == 'message':
                msg = row.get('message', {})
                if msg.get('role') == 'toolResult':
                    blocks = [dict(type='tool_result', tool_use_id=msg.get('toolCallId'),
                                   content=msg.get('content'), is_error=msg.get('isError'))]
                else:
                    blocks = msg.get('content', [])
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                kind = block.get('type')
                if kind in ('function_call', 'tool_use', 'toolCall'):
                    args = block.get('arguments', block.get('input', {}))
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    calls[block.get('call_id', block.get('id'))] = command_is_engine(args)
                elif kind in ('function_call_output', 'tool_result'):
                    cid = block.get('call_id', block.get('tool_use_id'))
                    if not calls.get(cid) or block.get('is_error') is True:
                        continue
                    output = block.get('output', block.get('content'))
                    if isinstance(output, dict):
                        if output.get('exit_code') != 0:
                            continue
                        output = output.get('output')
                    value = text_content(output)
                    if value.startswith('Chunk ID:') and 'Process exited with code 0' in value and '\nFinal output:\n' in value:
                        value = value.split('\nFinal output:\n', 1)[1]
                    # Entire tool output must be a receipt, not prose containing a marker.
                    try:
                        receipt = json.loads(value)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(receipt, dict) or receipt.get('protocol') != PROTOCOL:
                        continue
                    validate(receipt)
                    if receipt['run_id'] == run:
                        result.append({**receipt, 'source_ref': '%s:%s' % (path.resolve(), number)})
    replay(result, reducers)
    return result
