"""Run the TaxPal document ingestion pipeline.

Steps:
    1. Scrape tax-law pages and PDFs from configured official sources.
    2. Parse, clean, and split the documents into overlapping chunks.
    3. Embed the chunks with BGE-M3 and store them in Chroma.

Usage from ``Taxpal/src``::

    python ingest.py
    python ingest.py --scrape-only
    python ingest.py --parse-only
    python ingest.py --embed-only

Start Chroma before embedding::

    docker compose up -d chroma
"""

import json
import sys
import time
from pathlib import Path

from embedder import embed_and_store
from parser import parse_documents
from scraper import scrape_all


CHUNKS_FILE = Path(__file__).parent.parent / "data" / "chunks" / "all_chunks.json"


def run_scrape() -> list[dict]:
    """Scrape all configured sources."""
    print("=" * 60)
    print("STEP 1 / 3 - SCRAPING tax-law sources")
    print("=" * 60)
    return scrape_all()


def run_parse(scraped_docs: list[dict]) -> list[dict]:
    """Parse scraped documents into chunks."""
    print("=" * 60)
    print("STEP 2 / 3 - PARSING documents into chunks")
    print("=" * 60)
    return parse_documents(scraped_docs)


def run_embed(chunks: list[dict]) -> None:
    """Embed chunks and store them in Chroma."""
    print("=" * 60)
    print("STEP 3 / 3 - EMBEDDING chunks into Chroma")
    print("=" * 60)
    embed_and_store(chunks)


def run_full_pipeline() -> None:
    """Run all three ingestion steps."""
    started = time.time()

    print("\n" + "=" * 60)
    print("  TAXPAL - INGESTION PIPELINE")
    print("  Scrape -> Parse -> Embed -> Chroma")
    print("=" * 60 + "\n")

    scraped_docs = run_scrape()
    if not scraped_docs:
        print("No documents were scraped. Check the source configuration and network.")
        return

    chunks = run_parse(scraped_docs)
    if not chunks:
        print("No chunks were produced. Check the scraped files.")
        return

    run_embed(chunks)

    elapsed = time.time() - started
    print("\n" + "=" * 60)
    print(f"  PIPELINE COMPLETE in {elapsed:.0f} seconds")
    print(f"  Documents scraped: {len(scraped_docs)}")
    print(f"  Chunks created:    {len(chunks)}")
    print(f"  Vectors in Chroma: {len(chunks)}")
    print("=" * 60 + "\n")


def parse_saved_documents() -> None:
    """Parse files already present under ``data/raw``."""
    print("Parse-only mode: looking for scraped files in data/raw/...")
    from scraper import BASE_DIR

    documents = []
    for folder in ["ulii", "ura", "mofped"]:
        folder_path = BASE_DIR / folder
        if not folder_path.exists():
            continue
        for file_path in folder_path.iterdir():
            documents.append(
                {
                    "title": file_path.stem.replace("-", " ").title(),
                    "source": folder,
                    "url": "",
                    "path": str(file_path),
                    "type": "pdf" if file_path.suffix == ".pdf" else "html",
                }
            )

    if documents:
        run_parse(documents)
    else:
        print("No scraped files found. Run --scrape-only first.")


def embed_saved_chunks() -> None:
    """Embed the existing UTF-8 chunk export into Chroma."""
    if not CHUNKS_FILE.exists():
        print(f"No chunks file found at {CHUNKS_FILE}. Run --parse-only first.")
        return

    print(f"Loading chunks from {CHUNKS_FILE}...")
    with CHUNKS_FILE.open(encoding="utf-8") as chunks_file:
        chunks = json.load(chunks_file)
    run_embed(chunks)


if __name__ == "__main__":
    if "--scrape-only" in sys.argv:
        run_scrape()
    elif "--parse-only" in sys.argv:
        parse_saved_documents()
    elif "--embed-only" in sys.argv:
        embed_saved_chunks()
    else:
        run_full_pipeline()
