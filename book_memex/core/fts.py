"""FTS5 query-safety helper.

User input is passed through `safe_fts_query()` before being handed to
FTS5's MATCH. By default each token is wrapped as a phrase, which makes
FTS5 operators (AND, OR, NEAR), prefix wildcards (*), and sign operators
(- !) inert. Callers who want to opt into raw FTS5 syntax pass
advanced=True.
"""

from __future__ import annotations

import re

# Whitespace-based tokenization. Also split on double quotes so that
# a user typing `foo "bar" baz` gets three tokens: foo, bar, baz.
_TOKENIZER = re.compile(r'[^\s"]+')


def safe_fts_query(user_input: str, *, advanced: bool = False) -> str:
    """Convert a user-provided search string into a safe FTS5 MATCH query.

    In default mode, each whitespace-separated token is wrapped in double
    quotes (FTS5 phrase syntax), which treats operators and special chars
    as literal text. Empty input returns an empty string.

    In advanced mode, the input is returned as-is. Callers opt in via
    advanced=True when they want to expose raw FTS5 syntax (wildcards,
    NEAR, AND/OR) to power users.
    """
    if not isinstance(user_input, str):
        raise TypeError(f"expected str, got {type(user_input).__name__}")

    if advanced:
        return user_input

    if not user_input.strip():
        return ""

    tokens = _TOKENIZER.findall(user_input)
    if not tokens:
        return ""

    # FTS5 escapes embedded double quotes by doubling them.
    quoted = [f'"{t.replace(chr(34), chr(34) * 2)}"' for t in tokens]
    return " ".join(quoted)
