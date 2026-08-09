"""
parser.py — Convert raw scraped files into clean text chunks.

WHAT THIS DOES:
    Takes the raw HTML and PDF files saved by scraper.py
    Uses the 'unstructured' library to extract clean text
    Splits the text into overlapping chunks (for better retrieval)
    Attaches metadata to each chunk (act name, source, URL)

WHAT IS A CHUNK:
    A chunk is a piece of text, roughly 500-1000 words long.
    We overlap chunks by 100 words so that if a relevant passage
    falls on a boundary, it still gets retrieved.

    Example:
        Chunk 1: "Section 19. (1) Subject to this Act, the income..."  [words 1-600]
        Chunk 2: "...the income of a resident person for a year..."    [words 500-1100]
                  ↑ overlap zone — words 500-600 appear in both

HOW TO RUN:
    from parser import parse_documents
    chunks = parse_documents(scraped_docs_list)
"""

import re
import json
from pathlib import Path
from typing import Optional


# ── Chunking parameters ───────────────────────────────────
CHUNK_SIZE = 800       # target words per chunk
CHUNK_OVERLAP = 150    # words of overlap between consecutive chunks


def _extract_text_html(file_path: str) -> str:
    """Extract text from an HTML file using unstructured."""
    try:
        from unstructured.partition.html import partition_html
        elements = partition_html(filename=file_path)
        return "\n\n".join(str(el) for el in elements if str(el).strip())
    except ImportError:
        # Fallback: use BeautifulSoup if unstructured not installed
        from bs4 import BeautifulSoup
        html = Path(file_path).read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
        # Remove script/style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)


def _extract_text_pdf(file_path: str) -> str:
    """Extract text from a PDF file using unstructured."""
    try:
        from unstructured.partition.pdf import partition_pdf
        elements = partition_pdf(filename=file_path)
        return "\n\n".join(str(el) for el in elements if str(el).strip())
    except ImportError:
        # Fallback: use PyMuPDF
        try:
            import fitz  # pymupdf
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n\n"
            return text
        except ImportError:
            print(f"    ⚠ Cannot parse PDF (install 'unstructured' or 'pymupdf'): {file_path}")
            return ""


def _detect_section(text: str) -> Optional[str]:
    """
    Try to detect a section number from the text.
    Looks for patterns like "Section 21", "S. 21(1)", "Part III", etc.
    """
    match = re.search(r"(?:Section|S\.)\s*(\d+[A-Za-z]?(?:\(\d+\))?)", text[:200])
    if match:
        return f"Section {match.group(1)}"

    match = re.search(r"(Part\s+[IVXLCDM]+)", text[:200])
    if match:
        return match.group(1)

    return None


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
                overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks by word count.

    WHY OVERLAPPING:
        If a user asks about something that spans two chunks,
        the overlap ensures at least one chunk contains the
        full relevant passage.
    """
    words = text.split()
    if len(words) <= chunk_size:
        return [text]  # text is small enough — one chunk

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)

        # Move forward by (chunk_size - overlap) words
        start += chunk_size - overlap

    return chunks


def parse_documents(scraped_docs: list[dict]) -> list[dict]:
    """
    Parse all scraped documents into chunks with metadata.

    INPUT:
        scraped_docs — list of dicts from scraper.py, each with:
            title, source, url, path, type

    OUTPUT:
        List of chunk dicts, each with:
            text     — the chunk text (500-1000 words)
            title    — which act/document it came from
            source   — "ulii", "ura", or "mofped"
            url      — original URL
            section  — detected section number (or None)
            chunk_id — unique identifier
    """
    print("\n🔧 Parsing documents into chunks...")
    all_chunks = []
    chunk_counter = 0

    for doc in scraped_docs:
        path = doc["path"]
        doc_type = doc.get("type", "html")

        if not Path(path).exists():
            print(f"  ⚠ File not found: {path}")
            continue

        print(f"  → {doc['title']}...", end=" ", flush=True)

        # Step 1: Extract text based on file type
        if doc_type == "pdf":
            text = _extract_text_pdf(path)
        else:
            text = _extract_text_html(path)

        if not text or len(text.strip()) < 50:
            print("⚠ too little text, skipping")
            continue

        # Step 2: Clean up the text
        text = re.sub(r"\n{3,}", "\n\n", text)   # collapse multiple newlines
        text = re.sub(r" {2,}", " ", text)         # collapse multiple spaces
        text = text.strip()

        # Step 3: Split into chunks
        chunks = _chunk_text(text)

        # Step 4: Create chunk dicts with metadata
        for i, chunk_text in enumerate(chunks):
            chunk_counter += 1
            section = _detect_section(chunk_text)

            all_chunks.append({
                "text": chunk_text,
                "title": doc["title"],
                "source": doc["source"],
                "url": doc["url"],
                "section": section,
                "chunk_id": f"{doc['source']}_{chunk_counter:04d}",
                "chunk_index": i,
                "total_chunks": len(chunks),
            })

        print(f"✓ {len(chunks)} chunks")

    print(f"\n  Total: {len(all_chunks)} chunks from {len(scraped_docs)} documents.\n")

    # Save chunks to JSON for inspection
    out_path = Path(__file__).parent.parent / "data" / "chunks" / "all_chunks.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    print(f"  Chunks saved to {out_path}\n")

    return all_chunks


if __name__ == "__main__":
    # Quick test with a sample
    sample = [{"title": "Test", "source": "test", "url": "http://test",
               "path": "data/raw/ulii/income-tax-act-cap-340.html", "type": "html"}]
    parse_documents(sample)