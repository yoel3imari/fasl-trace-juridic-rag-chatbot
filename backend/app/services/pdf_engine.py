import logging
from pathlib import Path
from uuid import UUID
from typing import AsyncIterator
import fitz
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    text: str
    page: int
    bounding_box: list[float]
    block_index: int
    text_direction: str = "ltr"


@dataclass
class PDFMetadata:
    page_count: int
    language: str
    detected_languages: list[str]
    title: str | None
    author: str | None
    creator: str | None


@dataclass
class ExtractionResult:
    document_id: UUID
    status: str
    metadata: PDFMetadata
    chunks: list[TextBlock]
    failed_blocks: int = 0
    error: str | None = None


def detect_language_from_text(text: str) -> str:
    """Heuristic language detection based on character analysis.

    Samples up to the first 1000 non-whitespace characters and counts
    Arabic vs Latin vs French-specific characters to determine language.
    Returns "ar" for Arabic, "fr" for French, "en" otherwise.
    """
    arabic_ranges = [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)]
    french_accents: set[int] = {
        ord(c) for c in "àâçèéêëîïôùûü"
    }

    # Sample up to first 1000 non-whitespace characters
    sample = [c for c in text if not c.isspace()][:1000]

    arabic_count = 0
    latin_count = 0
    french_count = 0

    for char in sample:
        code = ord(char)
        if any(start <= code <= end for start, end in arabic_ranges):
            arabic_count += 1
        elif code in french_accents:
            french_count += 1
            latin_count += 1
        elif 0x0041 <= code <= 0x007A or 0x00C0 <= code <= 0x00FF:
            latin_count += 1

    if arabic_count > latin_count:
        return "ar"
    if french_count > 0:
        return "fr"
    return "en"


def detect_text_direction(text: str) -> str:
    """Classify text direction for French/Arabic documents.

    Counts Arabic-script characters vs all alphabetic characters.
    Returns 'rtl' if >70% are Arabic, 'ltr' if <30% are Arabic,
    otherwise 'mixed' (bilingual document).

    Whitespace-only or empty strings default to 'ltr'.
    Non-Arabic alphabetic characters (including French accented chars)
    are treated as LTR — this is correct for the French/Arabic domain.
    """
    if not text or not text.strip():
        return "ltr"

    arabic_ranges = [
        (0x0600, 0x06FF),   # Arabic
        (0x0750, 0x077F),   # Arabic Supplement
        (0x08A0, 0x08FF),   # Arabic Extended-A
        (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
        (0x10E60, 0x10E7F), # Rumi
        (0x1EE00, 0x1EEFF), # Arabic Mathematical
    ]

    arabic_count = 0
    other_alpha_count = 0

    for char in text:
        code = ord(char)
        if any(start <= code <= end for start, end in arabic_ranges):
            arabic_count += 1
        elif code >= 0x0041:
            # All non-Arabic alphabetic: Latin, Greek, Cyrillic,
            # French accented chars (Latin Extended), etc.
            # Excludes digits, punctuation, symbols below 0x0041.
            other_alpha_count += 1

    total = arabic_count + other_alpha_count
    if total == 0:
        return "ltr"

    arabic_ratio = arabic_count / total
    if arabic_ratio > 0.7:
        return "rtl"
    elif arabic_ratio < 0.3:
        return "ltr"
    return "mixed"


def detect_document_languages(block_texts: list[str]) -> list[str]:
    """Infer document-level languages from a sample of block texts.

    Uses detect_language_from_text per block and deduplicates results.
    Returns sorted list of ISO 639-1 codes found (e.g., ['ar', 'en']).
    Defaults to ['en'] for empty input.
    """
    if not block_texts:
        return ["en"]

    languages = set()
    # Sample evenly across all blocks to catch languages appearing after page 1
    stride = max(1, len(block_texts) // 20)
    for text in block_texts[::stride]:
        lang = detect_language_from_text(text)
        languages.add(lang)

    return sorted(languages)


def _safe_detect_text_direction(text: str) -> str:
    """Call detect_text_direction with per-block fallback on exception."""
    try:
        return detect_text_direction(text)
    except (ValueError, TypeError):
        logger.warning("detect_text_direction failed for block, defaulting to 'ltr'", exc_info=True)
        return "ltr"


def convert_bbox(fitz_bbox: tuple) -> list[float]:
    x0, y0, x1, y1 = fitz_bbox
    return [x0, y0, x1 - x0, y1 - y0]


def validate_bbox(bbox: list[float]) -> bool:
    """Validate bounding box dimensions.

    Returns False if:
    - x1 < x0 or y1 < y0 (negative dimensions)
    - x1 == x0 or y1 == y0 (zero area)
    - width > 10000 or height > 10000 (unreasonable page size)
    """
    x0, y0, w, h = bbox
    if w < 0 or h < 0:
        return False
    if w == 0 or h == 0:
        return False
    if w > 10000 or h > 10000:
        return False
    return True


# TODO: Wire this to SSE streaming endpoint (Task 4 subtask 4.3 — currently unused)
async def extract_text_with_boxes(
    pdf_path: Path,
    document_id: UUID,
) -> AsyncIterator[dict]:
    yield {"type": "status", "content": "starting"}

    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        language = "en"
        pdf_meta = doc.metadata

        yield {"type": "status", "content": f"processing_pages:{page_count}"}

        chunks = []
        sample_texts: list[str] = []
        failed_blocks = 0
        for page_num in range(page_count):
            page = doc[page_num]

            blocks = page.get_text("blocks")
            for block_idx, block in enumerate(blocks):
                if len(block) >= 6:
                    try:
                        text = block[4]
                        bbox = convert_bbox(block[:4])

                        if not validate_bbox(bbox):
                            logger.warning(
                                "Skipping block with invalid bbox on page %d, block %d: %s",
                                page_num + 1, block_idx, bbox,
                            )
                            continue

                        if page_num == 0 and len(sample_texts) < 3 and text.strip():
                            sample_texts.append(text)

                        if page_num == 0 and block_idx == 0 and not sample_texts and text.strip():
                            sample_texts.append(text)

                        chunks.append({
                            "text": text,
                            "page": page_num + 1,
                            "bounding_box": bbox,
                            "block_index": block_idx,
                            "text_direction": _safe_detect_text_direction(text),
                        })
                    except Exception:
                        failed_blocks += 1
                        logger.warning(
                            "Block %d on page %d failed: %s",
                            block_idx, page_num + 1, block[4] if len(block) > 4 else "unknown",
                            exc_info=True,
                        )

            yield {"type": "progress", "content": f"page_{page_num + 1}/{page_count}"}

        doc.close()

        if sample_texts:
            language = detect_language_from_text(" ".join(sample_texts))
            detected_languages = detect_document_languages(sample_texts)
        else:
            detected_languages = ["en"]

        metadata = PDFMetadata(
            page_count=page_count,
            language=language,
            detected_languages=detected_languages,
            title=pdf_meta.get("title"),
            author=pdf_meta.get("author"),
            creator=pdf_meta.get("creator"),
        )

        yield {
            "type": "result",
            "content": {
                "document_id": str(document_id),
                "status": "extracted",
                "metadata": {
                    "page_count": metadata.page_count,
                    "language": metadata.language,
                    "detected_languages": detected_languages,
                },
                "chunk_count": len(chunks),
                "failed_blocks": failed_blocks,
            },
        }

    except Exception as e:
        yield {
            "type": "error",
            "content": str(e),
            "failed_blocks": failed_blocks,
        }


async def process_document(
    pdf_path: Path,
    document_id: UUID,
) -> ExtractionResult:
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        language = "en"
        pdf_meta = doc.metadata
        all_blocks: list[TextBlock] = []
        failed_blocks = 0

        sample_texts: list[str] = []
        for page_num in range(page_count):
            page = doc[page_num]
            blocks = page.get_text("blocks")

            for block_idx, block in enumerate(blocks):
                if len(block) >= 6:
                    try:
                        text = block[4]
                        bbox = convert_bbox(block[:4])

                        if not validate_bbox(bbox):
                            logger.warning(
                                "Skipping block with invalid bbox on page %d, block %d: %s",
                                page_num + 1, block_idx, bbox,
                            )
                            continue

                        if page_num == 0 and len(sample_texts) < 3 and text.strip():
                            sample_texts.append(text)

                        if page_num == 0 and block_idx == 0 and not sample_texts and text.strip():
                            sample_texts.append(text)

                        all_blocks.append(TextBlock(
                            text=text,
                            page=page_num + 1,
                            bounding_box=bbox,
                            block_index=block_idx,
                            text_direction=_safe_detect_text_direction(text),
                        ))
                    except Exception:
                        failed_blocks += 1
                        logger.warning(
                            "Block %d on page %d failed: %s",
                            block_idx, page_num + 1, block[4] if len(block) > 4 else "unknown",
                            exc_info=True,
                        )

        doc.close()

        if sample_texts:
            language = detect_language_from_text(" ".join(sample_texts))
            detected_languages = detect_document_languages(sample_texts)
        else:
            detected_languages = ["en"]

        metadata = PDFMetadata(
            page_count=page_count,
            language=language,
            detected_languages=detected_languages,
            title=pdf_meta.get("title"),
            author=pdf_meta.get("author"),
            creator=pdf_meta.get("creator"),
        )

        return ExtractionResult(
            document_id=document_id,
            status="processed",
            metadata=metadata,
            chunks=all_blocks,
            failed_blocks=failed_blocks,
            error=None,
        )

    except Exception as e:
        return ExtractionResult(
            document_id=document_id,
            status="failed",
            metadata=PDFMetadata(page_count=0, language="en", detected_languages=["en"], title=None, author=None, creator=None),
            chunks=[],
            failed_blocks=0,
            error=str(e),
        )