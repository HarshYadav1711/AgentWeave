"""Deterministic helpers: tag extraction and merging (no ML, no external APIs)."""

from __future__ import annotations

import re

# Short, fixed list so behavior is predictable and explainable in a demo.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "have",
        "been",
        "this",
        "that",
        "with",
        "from",
        "they",
        "will",
        "your",
        "into",
        "than",
        "then",
        "also",
        "its",
        "who",
        "how",
        "any",
        "may",
        "use",
        "used",
        "using",
        "such",
        "each",
        "which",
        "their",
        "about",
        "there",
        "here",
        "when",
        "what",
        "where",
        "while",
        "some",
        "more",
        "very",
        "just",
        "only",
        "over",
        "other",
        "many",
        "much",
        "well",
        "help",
        "helps",
        "agent",
        "agents",
        "service",
        "services",
    }
)

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def extract_keywords_from_description(description: str, *, max_keywords: int = 24) -> list[str]:
    """
    Extract simple keywords from free text.

    Rules (deterministic):
    - Split into alphanumeric tokens (letters/digits only; punctuation is a separator).
    - Lowercase each token; drop tokens shorter than 3 characters.
    - Drop tokens in a small fixed stopword list.
    - De-duplicate while preserving first-seen order.
    - Cap the list at ``max_keywords`` (keeps earlier tokens first).
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in _TOKEN_RE.findall(description or ""):
        tok = raw.lower()
        if len(tok) < 3 or tok in _STOPWORDS:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= max_keywords:
            break
    return out


def merge_manual_and_extracted_tags(manual: list[str], extracted: list[str]) -> list[str]:
    """
    Combine caller-provided tags with extracted keywords.

    - Manual tags keep their order (after validation they are stripped non-empty strings).
    - Extracted keywords are appended next, skipping duplicates (case-insensitive).
    """
    seen: set[str] = set()
    merged: list[str] = []
    for t in manual:
        key = t.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(t)
    for t in extracted:
        key = t.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(t)
    return merged
