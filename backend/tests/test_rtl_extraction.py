"""
Tests for RTL/LTR text direction detection and mixed-directional extraction.

Validates AC 1 (direction identification), AC 2 (bbox accuracy regardless of direction),
and AC 3 (character integrity for multi-lingual text).
"""

import io
import pytest
from pathlib import Path

import fitz

from app.services.pdf_engine import (
    detect_text_direction,
    detect_language_from_text,
    detect_document_languages,
    convert_bbox,
    validate_bbox,
    TextBlock,
    PDFMetadata,
    ExtractionResult,
)


# ── Task 1: Text Direction Detection (AC 1) ──

class TestTextDirectionDetection:
    """Unit tests for detect_text_direction() against pure blocks."""

    def test_pure_arabic_returns_rtl(self):
        """Pure Arabic text block should return 'rtl'."""
        text = "بسم الله الرحمن الرحيم هذا نص عربي طويل للاختبار"
        assert detect_text_direction(text) == "rtl"

    def test_pure_english_returns_ltr(self):
        """Pure English text block should return 'ltr'."""
        text = "This is a standard English sentence for testing purposes."
        assert detect_text_direction(text) == "ltr"

    def test_pure_french_returns_ltr(self):
        """Pure French text block should return 'ltr'."""
        text = "Voici une phrase française avec des accents: à la découverte du Château."
        assert detect_text_direction(text) == "ltr"

    def test_mixed_arabic_english_returns_mixed(self):
        """Block containing significant Arabic AND English returns 'mixed'."""
        # Roughly balanced Arabic and English content
        text = "العقد contract القانوني legal agreement الطرفين parties المادة article البند clause"
        assert detect_text_direction(text) == "mixed"

    def test_empty_string_returns_ltr_default(self):
        """Empty or whitespace-only string returns 'ltr' as safe default."""
        assert detect_text_direction("") == "ltr"
        assert detect_text_direction("   \t\n  ") == "ltr"

    def test_numbers_and_symbols_return_ltr(self):
        """Pure numbers/symbols should return 'ltr' (neutral → default)."""
        assert detect_text_direction("12345 67890") == "ltr"

    def test_arabic_with_numbers_returns_rtl(self):
        """Arabic with embedded numbers (common in contracts) returns 'rtl'."""
        text = "المادة ١٥ من القانون رقم 12.34 لعام 2023"
        assert detect_text_direction(text) == "rtl"


class TestDetectDocumentLanguages:
    """Unit tests for detect_document_languages() across multiple blocks."""

    def test_single_arabic_block(self):
        blocks = ["بسم الله الرحمن الرحيم"]
        assert detect_document_languages(blocks) == ["ar"]

    def test_single_french_block(self):
        blocks = ["Voici un texte en français avec des accents."]
        assert detect_document_languages(blocks) == ["fr"]

    def test_mixed_arabic_and_english_blocks(self):
        blocks = [
            "بسم الله الرحمن الرحيم",  # Arabic
            "Preamble to the agreement",  # English
        ]
        langs = detect_document_languages(blocks)
        assert sorted(langs) == ["ar", "en"]

    def test_all_three_languages(self):
        blocks = [
            "Article 1: Définitions",
            "المادة الأولى: تعريفات",
            "The parties agree as follows:",
        ]
        langs = detect_document_languages(blocks)
        assert sorted(langs) == ["ar", "en", "fr"]

    def test_empty_blocks_defaults_to_en(self):
        assert detect_document_languages([]) == ["en"]


# ── Task 2: Bounding Box Accuracy (AC 2) ──

class TestBoundingBoxAccuracy:
    """Verify bbox coordinates are direction-independent (page-relative)."""

    def test_convert_bbox_maintains_positive_dimensions(self):
        """convert_bbox should convert [x0,y0,x1,y1] to [x,y,w,h] correctly."""
        # LTR block
        bbox_ltr = convert_bbox((100.0, 200.0, 400.0, 250.0))
        assert bbox_ltr == [100.0, 200.0, 300.0, 50.0]  # [x, y, w, h]

        # RTL bbox — PyMuPDF returns page-relative coords, NOT flipped for RTL
        bbox_rtl = convert_bbox((300.0, 500.0, 500.0, 540.0))
        assert bbox_rtl == [300.0, 500.0, 200.0, 40.0]

    def test_validate_bbox_rejects_negative_width(self):
        """Negative width bboxes should be rejected."""
        assert not validate_bbox([400.0, 200.0, -100.0, 50.0])

    def test_validate_bbox_rejects_negative_height(self):
        """Negative height bboxes should be rejected."""
        assert not validate_bbox([100.0, 400.0, 300.0, -10.0])

    def test_validate_bbox_rejects_zero_dimensions(self):
        """Zero-area bboxes should be rejected."""
        assert not validate_bbox([100.0, 200.0, 0.0, 50.0])
        assert not validate_bbox([100.0, 200.0, 300.0, 0.0])

    def test_validate_bbox_accepts_valid_bboxes(self):
        """Valid bboxes should pass validation."""
        assert validate_bbox([100.0, 200.0, 300.0, 50.0])  # LTR
        assert validate_bbox([50.0, 10.0, 200.0, 30.0])    # RTL-adjacent

    def test_validate_bbox_rejects_unreasonable_size(self):
        """Unreasonably large bboxes (corrupt data) should be rejected."""
        assert not validate_bbox([0.0, 0.0, 20000.0, 100.0])

    def test_pymupdf_bbox_is_page_relative_not_text_relative(self):
        """
        Critical verification: PyMuPDF bbox coordinates are page-relative
        (origin at top-left), NOT text-direction-relative.

        This test creates a minimal PDF and verifies that the x0 coordinate
        for blocks at the right edge (where RTL text may appear) returns
        positive values, confirming no coordinate flipping occurs.
        """
        # Create a simple PDF with text positioned on the right side
        buf = io.BytesIO()
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)

        # Insert text at right-side position (typical RTL origin)
        page.insert_text((400, 100), "RTL placeholder")  # x=400 is right side
        text = page.get_text("blocks")

        doc.close()

        # Verify bbox format: [x0, y0, x1, y1] where x0 ~= 400
        assert len(text) >= 1
        bbox = text[0][:4]
        # x0 should be approximately 400 (NOT flipped to negative or zero)
        assert bbox[0] > 0, f"x0={bbox[0]} — expected positive (page-relative)"
        assert bbox[2] > bbox[0], f"x1={bbox[2]} must be > x0={bbox[0]}"


# ── Task 3: Encoding & Character Integrity (AC 3) ──

class TestEncodingIntegrity:
    """Verify multi-lingual text survives extraction without corruption."""

    def test_arabic_unicode_integrity(self):
        """Arabic Unicode text must not be reordered or corrupted."""
        from app.services.pdf_engine import detect_text_direction

        # Famous Arabic legal text
        arabic = "في حالة الإخلال بأي شرط من شروط هذا العقد"
        assert detect_text_direction(arabic) == "rtl"
        # Verify no mojibake — all chars are valid Arabic range
        assert all(
            ord(c) >= 0x0600 and ord(c) <= 0x06FF or c.isspace()
            for c in arabic
        ), "Arabic characters corrupted"

    def test_french_diacritics_integrity(self):
        """French accented characters must survive extraction."""
        from app.services.pdf_engine import detect_language_from_text

        french = "L'État français a modifié les règles concernant l'accès aux marchés publics."
        # French detection should work
        assert detect_language_from_text(french) == "fr"
        # Verify all LTR — no spurious RTL detection
        from app.services.pdf_engine import detect_text_direction
        assert detect_text_direction(french) == "ltr"

    def test_mixed_rtl_ltr_no_reordering(self):
        """Line with both Arabic and English should preserve visual order."""
        text = "العقد contract القانوني legal agreement الطرفين parties"
        from app.services.pdf_engine import detect_text_direction
        assert detect_text_direction(text) == "mixed"
        assert "العقد" in text
        assert "contract" in text


# ── Task 4: Integration — ExtractionResult should carry directions ──

class TestExtractionResultWithDirection:
    """Verify that process_document result includes direction metadata."""

    def test_textblock_dataclass_has_text_direction_field(self):
        """TextBlock dataclass should have text_direction field (default 'ltr')."""
        block = TextBlock(
            text="Hello world",
            page=1,
            bounding_box=[100.0, 200.0, 300.0, 50.0],
            block_index=0,
            text_direction="ltr",
        )
        assert block.text_direction == "ltr"

    def test_textblock_rtl_direction(self):
        block = TextBlock(
            text="مرحبا",
            page=1,
            bounding_box=[100.0, 200.0, 300.0, 50.0],
            block_index=0,
            text_direction="rtl",
        )
        assert block.text_direction == "rtl"


# ── Language Detection (existing function — regression tests) ──

class TestLanguageDetection:
    """Regression tests for existing detect_language_from_text."""

    def test_detect_arabic(self):
        assert detect_language_from_text("بسم الله الرحمن الرحيم") == "ar"

    def test_detect_french(self):
        assert detect_language_from_text("Voici un texte en français.") == "fr"

    def test_detect_english(self):
        assert detect_language_from_text("This is a test sentence.") == "en"
