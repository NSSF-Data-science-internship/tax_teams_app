"""
ingest.py — Run the full ingestion pipeline.

WHAT THIS DOES (in order):
    1. SCRAPE  — downloads tax law pages/PDFs from ULII, URA, MoFPED
    2. PARSE   — extracts text, cleans it, splits into overlapping chunks
    3. EMBED   — converts chunks to BGE-M3 vectors, stores in Qdrant

After this runs, your Qdrant database is populated and ready
for the Langflow RAG flow to query.

HOW TO RUN:
    # Make sure Docker services are running first:
    docker compose up -d    (starts Qdrant + Langflow)

    # Then run the pipeline:
    cd Taxpal/src
    python ingest.py

    # Or run individual steps:
    python ingest.py --scrape-only
    python ingest.py --parse-only
    python ingest.py --embed-only

PREREQUISITES:
    pip install beautifulsoup4 lxml requests unstructured FlagEmbedding qdrant-client torch
"""

import sys
import json
import time
from pathlib import Path

from scraper import scrape_all
from parser import parse_documents
from embedder import embed_and_store


CHUNKS_FILE = Path(__file__).parent.parent / "data" / "chunks" / "all_chunks.json"


def run_scrape() -> list[dict]:
    """Step 1: Scrape all sources."""
    print("=" * 60)
    print("STEP 1 / 3 — SCRAPING tax law sources")
    print("=" * 60)
    return scrape_all()


def run_parse(scraped_docs: list[dict]) -> list[dict]:
    """Step 2: Parse scraped docs into chunks."""
    print("=" * 60)
    print("STEP 2 / 3 — PARSING documents into chunks")
    print("=" * 60)
    return parse_documents(scraped_docs)


def run_embed(chunks: list[dict]):
    """Step 3: Embed chunks and store in Qdrant."""
    print("=" * 60)
    print("STEP 3 / 3 — EMBEDDING chunks into Qdrant")
    print("=" * 60)
    embed_and_store(chunks)


def run_full_pipeline():
    """Run all three steps."""
    start = time.time()

    print("\n" + "═" * 60)
    print("  TAXPAL — INGESTION PIPELINE")
    print("  Scrape → Parse → Embed → Store")
    print("═" * 60 + "\n")

    # Step 1: Scrape
    scraped_docs = run_scrape()
    if not scraped_docs:
        print("⚠ No documents scraped. Check your internet connection.")
        return

    # Step 2: Parse
    chunks = run_parse(scraped_docs)
    if not chunks:
        print("⚠ No chunks produced. Check the scraped files.")
        return

    # Step 3: Embed + Store
    run_embed(chunks)

    elapsed = time.time() - start
    print("\n" + "═" * 60)
    print(f"  ✅ PIPELINE COMPLETE in {elapsed:.0f} seconds")
    print(f"  Documents scraped:  {len(scraped_docs)}")
    print(f"  Chunks created:     {len(chunks)}")
    print(f"  Vectors in Qdrant:  {len(chunks)}")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    if "--scrape-only" in sys.argv:
        run_scrape()
    elif "--parse-only" in sys.argv:
        # Load previously scraped docs list
        # (the scraper saves paths, so we rebuild the list from data/raw/)
        print("Parse-only mode: looking for scraped files in data/raw/...")
        from scraper import BASE_DIR
        docs = []
        for folder in ["ulii", "ura", "mofped"]:
            folder_path = BASE_DIR / folder
            if folder_path.exists():
                for f in folder_path.iterdir():
                    docs.append({
                        "title": f.stem.replace("-", " ").title(),
                        "source": folder,
                        "url": "",
                        "path": str(f),
                        "type": "pdf" if f.suffix == ".pdf" else "html",
                    })
        if docs:
            run_parse(docs)
        else:
            print("No scraped files found. Run --scrape-only first.")

    elif "--embed-only" in sys.argv:
        # Load previously parsed chunks
        if CHUNKS_FILE.exists():
            print(f"Loading chunks from {CHUNKS_FILE}...")
            with open(CHUNKS_FILE) as f:
                chunks = json.load(f)
            run_embed(chunks)
        else:
            print(f"No chunks file found at {CHUNKS_FILE}. Run --parse-only first.")
    else:
        run_full_pipeline()
