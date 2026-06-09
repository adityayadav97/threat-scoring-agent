"""Extract plain text from uploaded documents (txt, md, pdf, docx)."""

from __future__ import annotations

import io

SUPPORTED_EXTENSIONS = (".txt", ".md", ".log", ".csv", ".pdf", ".docx")


class UnsupportedDocumentError(ValueError):
    """Raised when a document type cannot be parsed."""


def extract_text(filename: str, data: bytes) -> str:
    """Return the text content of ``data`` based on the file extension.

    Parameters
    ----------
    filename:
        Original file name (used only to detect the extension).
    data:
        Raw bytes of the uploaded file.
    """
    name = filename.lower()

    if name.endswith((".txt", ".md", ".log", ".csv")):
        return _decode_text(data)
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    if name.endswith(".docx"):
        return _extract_docx(data)

    raise UnsupportedDocumentError(
        f"Unsupported file type: {filename}. "
        f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
    )


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _extract_docx(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs).strip()
