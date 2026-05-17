import re

# Matches [[...]] tokens. The inner character class is limited to 200 chars to
# prevent polynomial backtracking (ReDoS) on adversarial input.
REFERENCE_PATTERN = re.compile(r'\[\[([^\]\[]{1,200})\]\]')


def extract_references(body: str) -> list[str]:
    """Extract all [[...]] reference tokens from body text."""
    return REFERENCE_PATTERN.findall(body)


def is_numeric(s: str) -> bool:
    return s.strip().isdigit()
