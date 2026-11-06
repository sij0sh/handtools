"""Validation helpers for JSON payloads."""


def text_field(item, key, where):
    value = item.get(key) if isinstance(item, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{where}: `{key}` must be a non-empty string.')
    return value.strip()

