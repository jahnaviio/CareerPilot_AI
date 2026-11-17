"""Document text extraction: PDF (PyMuPDF), DOCX (python-docx), optional OCR fallback for scans."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from config import settings
from core.security import clean_untrusted_text

log = logging.getLogger(__name__)


class ExtractionError(ValueError):
    """User-presentable extraction failure."""


@dataclass
class ExtractedDocument:
    text: str
    pages: int
    method: str  # pdf_text | pdf_ocr | docx
    warnings: list[str]


def extract_text(data: bytes, ext: str) -> ExtractedDocument:
    if ext == "pdf":
        return _pdf(data)
    if ext == "docx":
        return _docx(data)
    raise ExtractionError("Unsupported file type.")


def _pdf(data: bytes) -> ExtractedDocument:
    import pymupdf
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # corrupted / malformed
        raise ExtractionError("This PDF could not be opened. It may be corrupted.") from exc
    try:
        if doc.needs_pass:
            raise ExtractionError("This PDF is password-protected. Remove the password and upload it again.")
        if doc.page_count > settings.max_resume_pages:
            raise ExtractionError(f"This PDF has {doc.page_count} pages; resumes are limited to {settings.max_resume_pages}.")
        pages = [p.get_text("text") for p in doc]
        text = clean_untrusted_text("\n".join(pages))
        warnings: list[str] = []
        if len(text) >= 80:
            return ExtractedDocument(text, doc.page_count, "pdf_text", warnings)
        # Likely scanned. OCR is optional and only used when enabled and available.
        if settings.ocr_enabled:
            ocr = _ocr_pdf(doc)
            if ocr:
                return ExtractedDocument(clean_untrusted_text(ocr), doc.page_count, "pdf_ocr",
                                         ["Text was read with OCR; please check the extracted details."])
            raise ExtractionError("This looks like a scanned PDF. Please upload a PDF with selectable text, or a Word (DOCX) file.")
        raise ExtractionError("No readable text found. This looks like a scanned PDF. Please upload a PDF with selectable text, or a Word (DOCX) file.")
    finally:
        doc.close()


def _ocr_pdf(doc) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    out = []
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            out.append(pytesseract.image_to_string(img))
    except Exception:  # tesseract binary missing, etc.
        log.warning("OCR failed", exc_info=True)
        return ""
    return "\n".join(out)


def _docx(data: bytes) -> ExtractedDocument:
    from docx import Document
    try:
        d = Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("This DOCX could not be opened. It may be corrupted.") from exc
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:  # resumes often put skills in tables
        for row in t.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells if c.text.strip()))
    text = clean_untrusted_text("\n".join(parts))
    if len(text) < 40:
        raise ExtractionError("No readable text found in this DOCX.")
    return ExtractedDocument(text, max(1, len(text) // 3000 + 1), "docx", [])
