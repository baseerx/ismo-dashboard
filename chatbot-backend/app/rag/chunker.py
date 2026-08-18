from typing import List, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils.text_extraction import PAGE_BREAK

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def chunk_text(text: str) -> List[Tuple[int, str]]:
    """
    Returns a list of (page_number, chunk_text) tuples.
    page_number is 1-indexed. For PDFs, pages come from PAGE_BREAK markers
    inserted at extraction time. For DOCX/TXT/MD (no real page concept),
    everything is treated as page 1.
    """
    if not text or not text.strip():
        return []

    pages = text.split(PAGE_BREAK)
    result: List[Tuple[int, str]] = []

    for page_num, page_text in enumerate(pages, start=1):
        if not page_text.strip():
            continue
        for chunk in _splitter.split_text(page_text):
            result.append((page_num, chunk))

    return result