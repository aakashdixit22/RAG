"""Text extraction for uploaded .pdf / .txt files."""

import io

from errors import UnsupportedMediaTypeError, ValidationError


def extract_text_from_txt(file_bytes):
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1", errors="ignore")


def extract_text_from_pdf(file_bytes):
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValidationError(f"Could not read PDF file: {exc}")

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            # Skip pages that fail to parse rather than failing the whole upload
            continue
    return "\n".join(pages_text)


def extract_text(filename, file_bytes):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "txt":
        return extract_text_from_txt(file_bytes)
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    raise UnsupportedMediaTypeError(f"Unsupported file extension: .{ext or '(none)'}")
