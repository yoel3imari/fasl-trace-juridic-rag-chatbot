"""
Legal-aware chunking service for the Fasl Trace RAG engine.

Takes ``list[TextBlock]`` from the PDF engine and produces structured
:class:`Chunk` objects using clause-boundary-aware splitting (legal document
structure), with a semantic sentence-based fallback when no legal structure
is detected.  20 % sliding-window overlap is applied in the fallback path.
Section titles are extracted from headings near chunk boundaries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.pdf_engine import TextBlock

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# Public types
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class Chunk:
    """A single chunk produced by the legal-aware chunking service.

    Attributes
    ----------
    text:
        The chunk content.
    page_number:
        The page that contributes the most characters to this chunk.
    chunk_index:
        0-based index among all chunks produced for the document.
    section_title:
        Extracted heading near the chunk boundary, if one was found.
    metadata:
        Arbitrary key-value pairs attached at chunking time (language,
        character offsets, bounding boxes of constituent blocks, …).
    text_blocks:
        The original :class:`TextBlock` objects that overlap this chunk's
        character span in the merged document text.
    """

    text: str
    page_number: int
    chunk_index: int
    section_title: str | None
    metadata: dict
    text_blocks: list = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════


def chunk_document(text_blocks: list) -> list[Chunk]:
    """Produce structured Chunks from a list of page-level TextBlocks.

    The pipeline merges all blocks into a single continuous text string,
    detects legal clause boundaries, and splits accordingly.  If fewer
    than three clause boundaries are found, a sentence-based fallback
    with 20 % sliding-window overlap is used instead.

    Parameters
    ----------
    text_blocks:
        The output of ``pdf_engine.process_document().chunks`` (or any
        list of :class:`~app.services.pdf_engine.TextBlock`).

    Returns
    -------
    list[Chunk]
        Ordered list of chunks ready for embedding and storage.
    """
    if not text_blocks:
        logger.info("chunk_document called with empty text_blocks list — returning []")
        return []

    config = get_chunking_config()

    # ── sort by (page, block_index) to guarantee document order ──
    sorted_blocks = sorted(text_blocks, key=lambda b: (b.page, b.block_index))

    # Step 1 — merge blocks into continuous text with page / block tracking
    merged_text, page_intervals, block_map = _merge_blocks(sorted_blocks)

    if not merged_text.strip():
        return []

    # Step 2 — detect document-level language
    language = _detect_chunk_language(merged_text)

    # Step 3 — try clause-boundary splitting
    boundaries = _find_clause_boundaries(merged_text)

    if len(boundaries) >= 3:
        logger.info(
            "Clause-boundary splitting: %d boundaries found", len(boundaries)
        )
        raw_sections = _split_at_boundaries(merged_text, boundaries)
        sections = _merge_small_sections(raw_sections, min_chars=100)
        chunks = _build_chunks_from_sections(
            sections,
            merged_text,
            page_intervals,
            block_map,
            sorted_blocks,
            language,
            config,
        )
    else:
        logger.info(
            "Semantic fallback: %d clause boundaries (< 3) — using sentence split",
            len(boundaries),
        )
        chunks = _semantic_split(
            merged_text,
            page_intervals,
            block_map,
            sorted_blocks,
            language,
            config,
        )

    # Step 4 — extract section titles from heading patterns
    for chunk in chunks:
        chunk.section_title = _find_heading_near(
            merged_text, chunk.metadata.get("char_start", 0)
        )

    # Step 5 — finalise chunk indices
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i

    logger.info("chunk_document produced %d chunks", len(chunks))
    return chunks


def get_chunking_config() -> dict:
    """Return the current chunking configuration from application settings.

    Keys
    ----
    target_size : int
        Target tokens per chunk (default 768).
    min_size : int
        Minimum tokens per chunk (default 512).
    max_size : int
        Absolute maximum tokens per chunk (default 1024).
    overlap_ratio : float
        Fraction of chunk length to overlap with the previous chunk when
        using sentence-based splitting (default 0.2 = 20 %).
    """
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "target_size": getattr(settings, "chunk_target_size", 768),
        "min_size": getattr(settings, "chunk_min_size", 512),
        "max_size": getattr(settings, "chunk_max_size", 1024),
        "overlap_ratio": getattr(settings, "chunk_overlap_ratio", 0.2),
    }


# ══════════════════════════════════════════════════════════════════════════
# Private helpers — token estimation / boundary detection / heading
# ══════════════════════════════════════════════════════════════════════════


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ``word_count * 1.3``.

    This is intentionally a simple heuristic — word-piece tokenizers vary
    between embedding models, and absolute precision is not necessary for
    v1 chunk-boundary decisions.
    """
    if not text or not text.strip():
        return 0
    return max(1, int(len(text.split()) * 1.3))


# ── Clause-boundary patterns (English / French / Arabic) ───────────────
# Combined single regex that matches any supported language's legal
# structure marker at the start of a line.

_COMBINED_CLAUSE_RE = re.compile(
    r"(?m)^(?:"
    r"Article|Section|Clause|CHAPTER|TITLE|PART|"
    r"Article|Section|Clause|CHAPITRE|TITRE|PARTIE|"
    r"المادة|الفصل|الفقرة|القسم|الباب"
    r")\s+\d+"
)

# ── Heading patterns scanned near chunk boundaries ─────────────────────
_HEADING_PATTERNS = [
    re.compile(r"^(?:[A-Z][A-Z\s]{2,})$"),  # ALL-CAPS LINE
    re.compile(r"^\d+(?:\.\d+)*\s+[A-Z]"),  # 1. / 1.1. / 1.1.1. Title
    re.compile(r"^(?:Article|Section|Clause)\s+\d+[\.\:\s]"),  # Article 1:
    re.compile(r"^(?:المادة|الفصل|الفقرة|القسم|الباب)\s+\d+"),  # Arabic
]

# ── Sentence-splitting patterns ────────────────────────────────────────
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_AR_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟])\s+")


def _find_clause_boundaries(text: str) -> list[int]:
    """Return sorted character positions where legal clauses start.

    Matches ``Article`` / ``Section`` / ``Clause`` / ``CHAPTER`` /
    ``TITLE`` / ``PART`` (EN, FR) and Arabic equivalents at the
    beginning of a line, followed by a number.
    """
    return sorted(match.start() for match in _COMBINED_CLAUSE_RE.finditer(text))


def _find_heading_near(text: str, position: int) -> str | None:
    """Scan roughly 200 characters before *position* for a heading pattern.

    Matches all-caps lines, numbered headings (``1.``, ``1.1.``),
    Article/Section headers, and Arabic legal headings.
    """
    if position <= 0:
        return None

    start = max(0, position - 200)
    preceding = text[start:position]

    for line in preceding.split("\n"):
        line = line.strip()
        if not line:
            continue
        for pattern in _HEADING_PATTERNS:
            if pattern.match(line):
                return line[:120] if len(line) > 120 else line
    return None


def _detect_chunk_language(text: str) -> str:
    """Detect the dominant language of *text*.

    Delegates to :func:`app.services.pdf_engine.detect_language_from_text`
    to reuse the existing character-range heuristic.
    """
    from app.services.pdf_engine import detect_language_from_text  # lazy import

    return detect_language_from_text(text)


# ══════════════════════════════════════════════════════════════════════════
# Block merging and position tracking
# ══════════════════════════════════════════════════════════════════════════


def _merge_blocks(text_blocks: list) -> tuple[str, list, list]:
    """Concatenate all block texts in order and build position indexes.

    Returns
    -------
    merged_text : str
        The single concatenated document text.
    page_intervals : list[tuple[int, int, int]]
        Each entry ``(start_char, end_char, page_number)``.
    block_map : list[tuple[int, int, int, list[float]]]
        Each entry ``(start_char, end_char, block_index, bounding_box)``.
    """
    parts: list[str] = []
    page_intervals: list[tuple[int, int, int]] = []
    block_map: list[tuple[int, int, int, list[float]]] = []
    pos = 0

    for i, block in enumerate(text_blocks):
        # Insert a newline separator between blocks to preserve paragraph
        # boundaries and ensure clause-boundary regex (`^`) can match.
        sep = "\n" if i > 0 else ""
        text = sep + block.text
        end = pos + len(text)
        parts.append(text)
        page_intervals.append((pos, end, block.page))
        bounding_box = getattr(block, "bounding_box", [])
        block_map.append((pos, end, block.block_index, bounding_box))
        pos = end

    return "".join(parts), page_intervals, block_map


def _get_majority_page(
    page_intervals: list[tuple[int, int, int]],
    chunk_start: int,
    chunk_end: int,
) -> int:
    """Return the page contributing the most characters to ``[start, end)``."""
    page_chars: dict[int, int] = {}
    for start, end, page in page_intervals:
        if start >= chunk_end or end <= chunk_start:
            continue
        overlap = min(end, chunk_end) - max(start, chunk_start)
        page_chars[page] = page_chars.get(page, 0) + overlap
    if not page_chars:
        return 1
    return max(page_chars, key=lambda k: page_chars[k])


def _get_text_blocks_for_range(
    block_map: list,
    text_blocks: list,
    chunk_start: int,
    chunk_end: int,
) -> list:
    """Return the original ``TextBlock`` objects whose character range overlaps ``[start, end)``.

    *block_map* and *text_blocks* must be aligned (same order, same length)
    — as returned by :func:`_merge_blocks` and its input.
    """
    result: list = []
    for (start, end, _block_idx, _bbox), block in zip(block_map, text_blocks):
        if start < chunk_end and end > chunk_start:
            result.append(block)
    return result


def _get_dominant_direction(blocks: list) -> str:
    """Return the most common ``text_direction`` (``ltr`` / ``rtl`` / ``mixed``)."""
    counts: dict[str, int] = {}
    for b in blocks:
        d = getattr(b, "text_direction", "ltr") or "ltr"
        counts[d] = counts.get(d, 0) + 1
    if not counts:
        return "ltr"
    return max(counts, key=lambda k: counts[k])


# ══════════════════════════════════════════════════════════════════════════
# Clause-boundary splitting pipeline
# ══════════════════════════════════════════════════════════════════════════


def _split_at_boundaries(text: str, boundaries: list[int]) -> list[dict]:
    """Split *text* at every clause-boundary character position.

    Returns a list of ``{"text", "char_start", "char_end"}`` dicts
    representing the segments between consecutive boundaries.
    """
    sections: list[dict] = []
    prev = 0
    for b in boundaries:
        if b > prev:
            section_text = text[prev:b].strip()
            if section_text:
                sections.append(
                    {"text": section_text, "char_start": prev, "char_end": b}
                )
        prev = b

    # Tail after the last boundary
    if prev < len(text):
        tail = text[prev:].strip()
        if tail:
            sections.append(
                {"text": tail, "char_start": prev, "char_end": len(text)}
            )
    return sections


def _merge_small_sections(sections: list[dict], min_chars: int = 100) -> list[dict]:
    """Merge sections shorter than *min_chars* into the *following* section.

    When a small section is merged, it is prepended (with ``\\n``) to the
    next section and the character range is widened to cover both.  This
    ensures that document headers or short clause-preamble lines stay
    attached to the content they introduce.
    """
    if not sections:
        return []

    result: list[dict] = list(sections)  # make a mutable copy

    i = 0
    while i < len(result):
        if len(result[i]["text"]) < min_chars and i + 1 < len(result):
            # Merge current (small) section into the following one
            nxt = result[i + 1]
            nxt["text"] = result[i]["text"] + "\n" + nxt["text"]
            nxt["char_start"] = result[i]["char_start"]
            result.pop(i)
            # Stay at same index — the (potentially merged) section
            # that is now at position i may still be small.
        else:
            i += 1

    return result


def _build_chunks_from_sections(
    sections: list[dict],
    merged_text: str,
    page_intervals: list,
    block_map: list,
    text_blocks: list,
    language: str,
    config: dict,
) -> list[Chunk]:
    """Convert clause-boundary sections into :class:`Chunk` objects.

    Sections whose token count exceeds ``max_size`` are further split
    on sentence boundaries.
    """
    chunks: list[Chunk] = []
    max_size = config["max_size"]

    for section in sections:
        tokens = _estimate_tokens(section["text"])
        if tokens <= max_size:
            chunks.append(
                _section_to_chunk(
                    section, page_intervals, block_map, text_blocks, language
                )
            )
        else:
            logger.info(
                "Section at char %d exceeds max_size (%d tokens) — splitting on sentences",
                section["char_start"],
                tokens,
            )
            sub_sections = _split_oversized_section(section, merged_text, max_size)
            for sub in sub_sections:
                chunks.append(
                    _section_to_chunk(
                        sub, page_intervals, block_map, text_blocks, language
                    )
                )

    return chunks


def _split_oversized_section(
    section: dict,
    full_text: str,
    max_tokens: int,
) -> list[dict]:
    """Split a section that is larger than *max_tokens* into smaller pieces.

    Splitting is done greedily on sentence boundaries.  Each output piece
    stays within ``max_tokens`` except when a single sentence already
    exceeds the limit (rare for legal text).
    """
    sentences = _split_sentences(section["text"])
    if not sentences:
        return [section]

    pieces: list[dict] = []
    current_sents: list[str] = []
    current_start = section["char_start"]

    for sent in sentences:
        candidate_sents = current_sents + [sent]
        candidate_text = " ".join(candidate_sents)

        if _estimate_tokens(candidate_text) <= max_tokens or not current_sents:
            current_sents = candidate_sents
        else:
            # Finalise current piece
            piece_text = " ".join(current_sents)
            piece_end = current_start + len(piece_text)
            pieces.append(
                {"text": piece_text, "char_start": current_start, "char_end": piece_end}
            )
            current_start = piece_end
            current_sents = [sent]

    # Last piece
    if current_sents:
        piece_text = " ".join(current_sents)
        pieces.append(
            {
                "text": piece_text,
                "char_start": current_start,
                "char_end": current_start + len(piece_text),
            }
        )

    return pieces


def _section_to_chunk(
    section: dict,
    page_intervals: list,
    block_map: list,
    text_blocks: list,
    language: str,
) -> Chunk:
    """Convert a ``{"text", "char_start", "char_end"}`` dict into a :class:`Chunk`."""
    char_start = section["char_start"]
    char_end = section["char_end"]
    text = section["text"]

    page_number = _get_majority_page(page_intervals, char_start, char_end)
    blocks = _get_text_blocks_for_range(block_map, text_blocks, char_start, char_end)
    bboxes = [getattr(b, "bounding_box", []) for b in blocks]

    metadata = {
        "language": language,
        "char_start": char_start,
        "char_end": char_end,
        "bounding_boxes": bboxes,
        "text_direction": _get_dominant_direction(blocks),
    }

    return Chunk(
        text=text,
        page_number=page_number,
        chunk_index=0,  # assigned by caller
        section_title=None,  # assigned by caller
        metadata=metadata,
        text_blocks=blocks,
    )


# ══════════════════════════════════════════════════════════════════════════
# Semantic fallback — sentence-based splitting with 20 % overlap
# ══════════════════════════════════════════════════════════════════════════


def _split_sentences(text: str) -> list[str]:
    """Split *text* into sentences.

    Uses Arabic-aware punctuation (``؟``) when Arabic characters are
    detected in the first 200 characters of the input.
    """
    has_arabic = any(
        "\u0600" <= c <= "\u06FF" or "\u0750" <= c <= "\u077F" for c in text[:200]
    )
    pattern = _AR_SENTENCE_SPLIT_RE if has_arabic else _SENTENCE_SPLIT_RE
    return [p.strip() for p in pattern.split(text) if p.strip()]


def _semantic_split(
    merged_text: str,
    page_intervals: list,
    block_map: list,
    text_blocks: list,
    language: str,
    config: dict,
) -> list[Chunk]:
    """Split *merged_text* into chunks at sentence boundaries with overlap.

    This is the fallback path used when fewer than 3 clause boundaries
    are found.  Sentences are greedily merged up to ``target_size``
    tokens, with each chunk sharing a 20 % overlapping tail with the
    next chunk.
    """
    if not merged_text.strip():
        return []

    sentences = _split_sentences(merged_text)
    if not sentences:
        return []

    # ── Build character-position index for each sentence ────────────
    sent_positions: list[tuple[str, int, int]] = []
    search_pos = 0
    for sent in sentences:
        idx = merged_text.find(sent, search_pos)
        if idx == -1:
            idx = search_pos  # fallback — approximate
        end = idx + len(sent)
        sent_positions.append((sent, idx, end))
        search_pos = end

    target_tokens = config["target_size"]
    min_tokens = config["min_size"]
    max_tokens = config["max_size"]
    overlap_ratio = config["overlap_ratio"]

    chunks: list[Chunk] = []
    current_idx = 0

    while current_idx < len(sent_positions):
        chunk_sents: list[str] = []
        chunk_start_char = sent_positions[current_idx][1]

        # ── Accumulate sentences up to target / max size ────────────
        i = current_idx
        while i < len(sent_positions):
            sent_text = sent_positions[i][0]

            candidate_text = (
                sent_text
                if not chunk_sents
                else " ".join(chunk_sents + [sent_text])
            )
            candidate_tokens = _estimate_tokens(candidate_text)

            # Always accept at least one sentence
            if not chunk_sents:
                chunk_sents.append(sent_text)
                i += 1
                continue

            # Stop if adding this sentence would exceed max_tokens
            if candidate_tokens > max_tokens:
                break

            chunk_sents.append(sent_text)
            current_tokens = _estimate_tokens(" ".join(chunk_sents))

            # If we have reached target (and are above min), stop
            if current_tokens >= target_tokens and current_tokens >= min_tokens:
                i += 1
                break

            i += 1

        # ── Ensure we meet the minimum size (grab more if possible) ──
        while i < len(sent_positions):
            candidate = " ".join(chunk_sents + [sent_positions[i][0]])
            if _estimate_tokens(candidate) <= max_tokens:
                chunk_sents.append(sent_positions[i][0])
                i += 1
            else:
                break

        chunk_text = " ".join(chunk_sents)
        chunk_end_char = (
            sent_positions[i - 1][2] if i > current_idx else sent_positions[current_idx][2]
        )

        # Build chunk object
        chunks.append(
            _build_chunk_from_range(
                chunk_text,
                chunk_start_char,
                chunk_end_char,
                page_intervals,
                block_map,
                text_blocks,
                language,
            )
        )

        # ── Compute next start with 20 % sliding-window overlap ──────
        if i >= len(sent_positions):
            break

        chunk_len = chunk_end_char - chunk_start_char
        overlap_chars = int(chunk_len * overlap_ratio)
        overlap_start = chunk_end_char - overlap_chars

        # Walk backwards from *i* to find the sentence containing overlap_start
        next_idx = i
        while next_idx > 0 and sent_positions[next_idx - 1][1] > overlap_start:
            next_idx -= 1

        # Guarantee forward progress — at least one sentence
        if next_idx <= current_idx:
            next_idx = current_idx + 1

        current_idx = next_idx

    return chunks


def _build_chunk_from_range(
    text: str,
    char_start: int,
    char_end: int,
    page_intervals: list,
    block_map: list,
    text_blocks: list,
    language: str,
) -> Chunk:
    """Construct a single :class:`Chunk` from a character span in the merged text."""
    page_number = _get_majority_page(page_intervals, char_start, char_end)
    blocks = _get_text_blocks_for_range(block_map, text_blocks, char_start, char_end)
    bboxes = [getattr(b, "bounding_box", []) for b in blocks]

    metadata = {
        "language": language,
        "char_start": char_start,
        "char_end": char_end,
        "bounding_boxes": bboxes,
        "text_direction": _get_dominant_direction(blocks),
    }

    return Chunk(
        text=text,
        page_number=page_number,
        chunk_index=0,
        section_title=None,
        metadata=metadata,
        text_blocks=blocks,
    )
