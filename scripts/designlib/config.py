"""Skill-directory files: SKILL.md settings and the reference texts prompts cite."""
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / 'SKILL.md'
DEFAULTS = SKILL_DIR / 'references' / 'defaults.md'
CONTRACT = SKILL_DIR / 'references' / 'contract.md'
LANGUAGES = SKILL_DIR / 'languages'
INSTRUCTIONS = SKILL_DIR / 'references' / 'instructions.md'

DEFAULT_MAX_CHALLENGES = 3
_METADATA = re.compile(r'metadata:\s*(#.*)?')
_KEY = re.compile(r'\s+max-challenges\s*:.*')
_VALUE = re.compile(r'\s+max-challenges:\s*["\']?(\d+)["\']?\s*(#.*)?')


def max_challenges(path=SKILL_MD):
    """Return `metadata.max-challenges` from SKILL.md frontmatter, default 3."""
    try:
        lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    except FileNotFoundError:
        return DEFAULT_MAX_CHALLENGES
    if not lines or lines[0].strip() != '---':
        return DEFAULT_MAX_CHALLENGES
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
    if end is None:
        return DEFAULT_MAX_CHALLENGES
    found = []
    in_metadata = False
    for line in lines[1:end]:
        if line and not line[0].isspace():
            in_metadata = bool(_METADATA.fullmatch(line.rstrip()))
        elif in_metadata and _KEY.fullmatch(line):
            found.append(line.rstrip())
    if not found:
        return DEFAULT_MAX_CHALLENGES
    if len(found) > 1:
        raise ValueError(f'{path}: duplicate metadata.max-challenges.')
    match = _VALUE.fullmatch(found[0])
    if not match or int(match.group(1)) < 1:
        raise ValueError(f'{path}: metadata.max-challenges must be an integer >= 1.')
    return int(match.group(1))


def references():
    """Values the step prompts cite: reference paths, defaults text, language names."""
    return {
        'defaults': DEFAULTS,
        'defaults_text': DEFAULTS.read_text(encoding='utf-8').strip(),
        'contract': CONTRACT,
        'languages': LANGUAGES,
        'language_list': ', '.join(sorted(p.stem for p in LANGUAGES.glob('*.md'))),
        'instructions': INSTRUCTIONS,
    }
