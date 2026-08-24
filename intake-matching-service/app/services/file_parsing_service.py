"""Extracts plain text from an uploaded resume file.

Supports PDF and DOCX. Legacy .doc (the pre-2007 binary Word format) has no reliable pure-Python
parser - it's rejected with a clear message asking the caller to convert to PDF/DOCX, rather than
silently returning garbage text.
"""
import io
import logging

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.exceptions import InvalidStateError

logger = logging.getLogger("app.services.file_parsing")

SUPPORTED_EXTENSIONS = ("pdf", "docx", "doc")


def _extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(file_bytes: bytes) -> str:
    document = DocxDocument(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def extract_text(filename: str, file_bytes: bytes) -> tuple[str, str]:
    """Returns (extracted_text, file_type). Raises InvalidStateError for unsupported/unreadable files."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise InvalidStateError(
            f"Unsupported file type '.{extension}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    if extension == "doc":
        raise InvalidStateError(
            "Legacy .doc files aren't supported - please convert the resume to .docx or .pdf and re-upload."
        )

    try:
        text = _extract_pdf_text(file_bytes) if extension == "pdf" else _extract_docx_text(file_bytes)
    except InvalidStateError:
        raise
    except Exception as exc:
        logger.exception("Failed to extract text from %s", filename)
        raise InvalidStateError(f"Could not read '{filename}': {exc}") from exc

    text = text.strip()
    if not text:
        raise InvalidStateError(f"No extractable text found in '{filename}' - is it a scanned/image-only file?")
    return text, extension
