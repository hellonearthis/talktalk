"""Pure text normalization and sentence chunking for low-latency TTS."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_CLAUSE_SPLIT_RE = re.compile(r"(?<=[,;:\u2014-])\s+")


def normalize_clipboard_text(raw_text: str) -> str:
    """Collapse excessive whitespace and strip surrounding blanks."""
    if not raw_text:
        return ""
    # Preserve paragraph breaks as single newlines before sentence splitting
    lines = [
        _WHITESPACE_RE.sub(" ", line).strip()
        for line in raw_text.splitlines()
    ]
    return "\n".join(line for line in lines if line)


def _split_long_segment(segment: str, max_chars: int) -> list[str]:
    """Split a long sentence on clause boundaries, then word boundaries."""
    if len(segment) <= max_chars:
        return [segment]

    parts: list[str] = []
    clauses = _CLAUSE_SPLIT_RE.split(segment)
    current = ""

    for clause in clauses:
        candidate = f"{current} {clause}".strip() if current else clause
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            parts.append(current)
            current = ""

        if len(clause) <= max_chars:
            current = clause
            continue

        # Fallback: split by words
        words = clause.split(" ")
        word_buf = ""
        for word in words:
            word_cand = f"{word_buf} {word}".strip() if word_buf else word
            if len(word_cand) <= max_chars:
                word_buf = word_cand
            else:
                if word_buf:
                    parts.append(word_buf)
                word_buf = word
        if word_buf:
            current = word_buf

    if current:
        parts.append(current)

    return parts


def chunk_text_for_tts(
    raw_text: str,
    first_chunk_max_chars: int = 120,
    max_chunk_chars: int = 320,
) -> list[str]:
    """Split text into TTS chunks with a small first chunk for fast TTFA."""
    cleaned = normalize_clipboard_text(raw_text)
    if not cleaned:
        return []

    raw_sentences = [
        s.strip() for s in _SENTENCE_SPLIT_RE.split(cleaned) if s.strip()
    ]
    if not raw_sentences:
        return []

    chunks: list[str] = []
    for index, sentence in enumerate(raw_sentences):
        limit = first_chunk_max_chars if index == 0 else max_chunk_chars
        split_parts = _split_long_segment(sentence, limit)
        for part in split_parts:
            if (
                chunks
                and len(chunks) > 1
                and len(chunks[-1]) + 1 + len(part) <= max_chunk_chars
            ):
                chunks[-1] = f"{chunks[-1]} {part}"
            else:
                chunks.append(part)

    return chunks

