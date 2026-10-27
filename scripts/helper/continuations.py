"""Versioned replay descriptors: data only, no shell or executable code."""
import base64
import json
from .graph_store import digest

PREFIX = "continue:"
# history replays as an expansion: a fresh bounded scan, not a pinned page.
ALLOWED = {"query", "inspect", "show", "history"}


def encode(argv, signature=None, purpose="Read the next page", effect="delivery"):
    payload = {"version": 1, "argv": argv, "signature": signature}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()
    if len(raw) > 16384:
        raise ValueError("Continuation request exceeds 16 KiB; shorten the query/input specification")
    token = PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return {"purpose": purpose, "effect": effect, "ref": token}


def decode(token):
    if not token.startswith(PREFIX) or len(token) > 23000:
        raise ValueError("Invalid continuation")
    try:
        raw = token[len(PREFIX):]
        value = json.loads(base64.b64decode(raw + '=' * (-len(raw) % 4), altchars=b'-_', validate=True))
    except (ValueError, UnicodeError):
        raise ValueError("Invalid continuation encoding") from None
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("Unsupported continuation version")
    argv = value.get("argv")
    if (not isinstance(argv, list) or not argv or argv[0] not in ALLOWED
        or not all(isinstance(x, str) and '\x00' not in x for x in argv)
        or any(x.startswith(PREFIX) for x in argv)):
        raise ValueError("Invalid continuation operation or arguments")
    return value


def signature(value):
    return digest(value)


def replace_option(argv, flag, value):
    result, skip = [], False
    for item in argv:
        if skip:
            skip = False
        elif item == flag:
            skip = True
        elif not item.startswith(flag + '='):
            result.append(item)
    if value is not None:
        result.extend([flag, str(value)])
    return result
