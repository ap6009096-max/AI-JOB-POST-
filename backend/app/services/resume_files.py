from __future__ import annotations

import io
import logging
import zipfile

MAX_RESUME_BYTES = 5 * 1024 * 1024

MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_PNG = "image/png"
MIME_JPEG = "image/jpeg"

ALLOWED_MIME_TYPES = {MIME_PDF, MIME_DOCX, MIME_PNG, MIME_JPEG}

EXTENSIONS = {
    MIME_PDF: "pdf",
    MIME_DOCX: "docx",
    MIME_PNG: "png",
    MIME_JPEG: "jpg",
}

logger = logging.getLogger(__name__)


class ResumeFileError(ValueError):
    pass


def _is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return False
    return any(name.startswith("word/") for name in names) and "[Content_Types].xml" in names


def sniff_mime_type(data: bytes) -> str | None:
    if data.startswith(b"%PDF"):
        return MIME_PDF
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return MIME_PNG
    if data.startswith(b"\xff\xd8\xff"):
        return MIME_JPEG
    if _is_docx(data):
        return MIME_DOCX
    return None


def validate_resume_file(*, data: bytes, declared_type: str | None, filename: str | None) -> str:
    if not data:
        logger.info("resume_upload_rejected reason=empty filename=%s", filename)
        raise ResumeFileError("Resume file is empty")
    if len(data) > MAX_RESUME_BYTES:
        logger.info("resume_upload_rejected reason=too_large size=%s filename=%s", len(data), filename)
        raise ResumeFileError("Resume must be 5 MB or smaller")
    sniffed = sniff_mime_type(data)
    if sniffed is None:
        logger.info("resume_upload_rejected reason=unknown_type filename=%s", filename)
        raise ResumeFileError("Upload a PDF, DOCX, PNG, or JPG resume")
    declared = (declared_type or "").split(";")[0].strip().lower()
    if declared in {"image/jpg", "image/pjpeg"}:
        declared = MIME_JPEG
    if declared and declared not in ALLOWED_MIME_TYPES:
        logger.info("resume_upload_rejected reason=declared_mime mime=%s filename=%s", declared, filename)
        raise ResumeFileError("Upload a PDF, DOCX, PNG, or JPG resume")
    if declared and declared != sniffed:
        logger.info(
            "resume_upload_rejected reason=mime_mismatch declared=%s sniffed=%s filename=%s",
            declared,
            sniffed,
            filename,
        )
        raise ResumeFileError("File type does not match the selected format")
    return sniffed
