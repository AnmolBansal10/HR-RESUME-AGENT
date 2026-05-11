"""
file_parser.py
Handles file validation, text extraction from PDF/DOCX, and PII masking.
All extracted content is treated as passive data — never executed as instructions.
"""
import io
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_TEXT_CHARS = 15_000  # hard cap to avoid token overflow


# ─── Validation ───────────────────────────────────────────────────────────────

def is_valid_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def is_valid_size(file_bytes: bytes, max_mb: int) -> bool:
    return len(file_bytes) <= max_mb * 1024 * 1024


# ─── Text Extraction ──────────────────────────────────────────────────────────

def _sanitize(raw: str) -> str:
    """Strip null bytes, normalise whitespace, truncate."""
    text = raw.replace("\x00", "")
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_TEXT_CHARS]


def extract_pdf(file_bytes: bytes) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text("text") for page in doc]
        doc.close()
        return _sanitize("\n".join(pages))
    except Exception as e:
        logger.error("PDF extraction error: %s", e)
        return ""


def extract_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return _sanitize("\n".join(paragraphs))
    except Exception as e:
        logger.error("DOCX extraction error: %s", e)
        return ""


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Dispatch to the correct parser based on extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_pdf(file_bytes)
    if ext == ".docx":
        return extract_docx(file_bytes)
    raise ValueError(f"Unsupported file type: {ext}")


# ─── PII Masking ──────────────────────────────────────────────────────────────

def mask_pii(text: str) -> str:
    """Mask email addresses and phone numbers before any storage or logging."""
    # Email
    text = re.sub(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        "[EMAIL_REDACTED]",
        text,
    )
    # Phone (handles +91, (123) 456-7890, etc.)
    text = re.sub(
        r"(\+?\d[\d\s\-().]{7,}\d)",
        "[PHONE_REDACTED]",
        text,
    )
    return text
