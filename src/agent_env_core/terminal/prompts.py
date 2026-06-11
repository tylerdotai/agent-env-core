"""Interactive prompt detection."""

import re

PROMPT_RE = re.compile(r"(password:|confirm\?|\[y/n\]|are you sure)", re.IGNORECASE)


def contains_interactive_prompt(text: str) -> bool:
    """Return true if text contains an interactive prompt marker."""
    return PROMPT_RE.search(text) is not None
