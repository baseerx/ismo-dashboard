import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

# Internal marker joining pages - not a real character that appears in
# extracted text, lets us track page boundaries without a DB schema change.
PAGE_BREAK = "\x0c"


def extract_text_from_pdf(filepath: str) -> str:
    reader = PdfReader(filepath)
    pages = [clean_text(page.extract_text() or "") for page in reader.pages]
    return PAGE_BREAK.join(pages)


def extract_text_from_docx(filepath: str) -> str:
    doc = DocxDocument(filepath)
    return "\n".join(p.text for p in doc.paragraphs)


def extract_text_from_txt(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_text_from_markdown(filepath: str) -> str:
    return extract_text_from_txt(filepath)


def clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(filepath: str, content_type: str) -> str:
    ext = Path(filepath).suffix.lower()

    if ext == ".pdf":
        # already cleaned per-page inside extract_text_from_pdf, PAGE_BREAK preserved
        return extract_text_from_pdf(filepath)
    elif ext == ".docx":
        raw = extract_text_from_docx(filepath)
    elif ext == ".md":
        raw = extract_text_from_markdown(filepath)
    elif ext == ".txt":
        raw = extract_text_from_txt(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return clean_text(raw)