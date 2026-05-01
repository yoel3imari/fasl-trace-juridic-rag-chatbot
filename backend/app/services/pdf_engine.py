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


@dataclass
class PDFMetadata:
    page_count: int
    language: str
    title: str | None
    author: str | None
    creator: str | None


@dataclass
class ExtractionResult:
    document_id: UUID
    status: str
    metadata: PDFMetadata
    chunks: list[TextBlock]
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
        for page_num in range(page_count):
            page = doc[page_num]

            blocks = page.get_text("blocks")
            for block_idx, block in enumerate(blocks):
                if len(block) >= 6:
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

                    if page_num == 0 and block_idx == 0 and not sample_texts:
                        sample_texts.append(text)

                    chunks.append({
                        "text": text,
                        "page": page_num + 1,
                        "bounding_box": bbox,
                        "block_index": block_idx,
                    })

            yield {"type": "progress", "content": f"page_{page_num + 1}/{page_count}"}

        doc.close()

        if sample_texts:
            language = detect_language_from_text(" ".join(sample_texts))

        metadata = PDFMetadata(
            page_count=page_count,
            language=language,
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
                },
                "chunk_count": len(chunks),
            },
        }

    except Exception as e:
        yield {
            "type": "error",
            "content": str(e),
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

        sample_texts: list[str] = []
        for page_num in range(page_count):
            page = doc[page_num]
            blocks = page.get_text("blocks")

            for block_idx, block in enumerate(blocks):
                if len(block) >= 6:
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

                    if page_num == 0 and block_idx == 0 and not sample_texts:
                        sample_texts.append(text)

                    all_blocks.append(TextBlock(
                        text=text,
                        page=page_num + 1,
                        bounding_box=bbox,
                        block_index=block_idx,
                    ))

        doc.close()

        if sample_texts:
            language = detect_language_from_text(" ".join(sample_texts))

        metadata = PDFMetadata(
            page_count=page_count,
            language=language,
            title=pdf_meta.get("title"),
            author=pdf_meta.get("author"),
            creator=pdf_meta.get("creator"),
        )

        return ExtractionResult(
            document_id=document_id,
            status="processed",
            metadata=metadata,
            chunks=all_blocks,
            error=None,
        )

    except Exception as e:
        return ExtractionResult(
            document_id=document_id,
            status="failed",
            metadata=PDFMetadata(page_count=0, language="en", title=None, author=None, creator=None),
            chunks=[],
            error=str(e),
        )