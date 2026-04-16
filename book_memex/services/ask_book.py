"""ask_book: FTS5 retrieval + LLM answer for a single book.

v1 scope: the raw question is run through safe_fts_query and sent to
FTS5 for top-k retrieval. No pre-LLM keyword extraction (deferred). The
LLM is a pluggable callable so tests can mock it. A null/missing LLM
returns a structured "no LLM configured" message instead of raising.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from book_memex.mcp.tools import search_book_content_impl


LLM = Callable[..., str]


@dataclass
class AskBookResult:
    answer: Optional[str]
    citations: List[Dict[str, Any]] = field(default_factory=list)
    segments_used: List[Dict[str, Any]] = field(default_factory=list)
    message: Optional[str] = None


# Match both bare and bracketed URI forms in LLM output.
_CITATION_RE = re.compile(
    r"book-memex://book/[^\s\]\)#]+(?:#[^\s\]\)]+)?"
)


def ask_book(
    session: Session,
    *,
    book_id: int,
    question: str,
    k: int = 8,
    llm: Optional[LLM] = None,
) -> AskBookResult:
    """Retrieve top-k segments from one book and ask the LLM to answer."""
    if not question or not question.strip():
        return AskBookResult(answer=None, message="question is required")

    if llm is None:
        return AskBookResult(
            answer=None,
            message="no LLM configured; pass llm=... or set BOOK_MEMEX_LLM env",
        )

    hits = search_book_content_impl(
        session, book_id=book_id, query=question, limit=k,
    )
    if not hits:
        return AskBookResult(
            answer=None,
            message="no matching content; try a different query or reindex the book",
        )

    prompt = _build_prompt(question, hits)
    try:
        raw = llm(prompt)
    except Exception as exc:
        return AskBookResult(
            answer=None,
            message=f"llm error: {exc}",
            segments_used=hits,
        )

    citations = _parse_citations(raw or "")
    return AskBookResult(
        answer=raw,
        citations=citations,
        segments_used=hits,
    )


def _build_prompt(question: str, hits: List[Dict[str, Any]]) -> str:
    parts = [
        "You are answering a question about a single book. Ground every claim "
        "in the passages below and cite using the book-memex URIs.",
        "",
        f"Question: {question}",
        "",
        "Passages:",
    ]
    for h in hits:
        uri = h["book_uri"]
        frag = h.get("fragment") or ""
        cite = f"{uri}#{frag}" if frag else uri
        snippet = h.get("snippet") or ""
        title = h.get("title") or h.get("segment_type", "")
        parts.append(f"[{cite}] ({title}): {snippet}")
    parts.append("")
    parts.append(
        "Answer the question using only the passages above. "
        "Include at least one citation of the form "
        "`book-memex://book/<id>#<anchor>` for each claim."
    )
    return "\n".join(parts)


def _parse_citations(text: str) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for match in _CITATION_RE.finditer(text):
        uri = match.group(0)
        if uri in seen:
            continue
        seen.add(uri)
        frag = None
        if "#" in uri:
            base, _, frag = uri.partition("#")
        else:
            base = uri
        out.append({"uri": uri, "base": base, "fragment": frag})
    return out
