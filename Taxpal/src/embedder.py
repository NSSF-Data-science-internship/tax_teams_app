"""
embedder.py — Embed text chunks with BGE-M3 and store in Qdrant.

WHAT THIS DOES:
    Takes the text chunks from parser.py
    Converts each chunk into two types of vectors using BGE-M3:
        - DENSE vector  (1024 floats) → captures meaning
        - SPARSE vector (keyword weights) → captures exact terms
    Stores both in Qdrant with metadata for hybrid search

WHAT IS AN EMBEDDING:
    An embedding is a list of numbers that represents the "meaning"
    of a piece of text. Two texts about the same topic will have
    similar numbers. Example (simplified to 3 dimensions):

        "Income tax rate for companies"  → [0.82, 0.15, 0.91]
        "Corporate tax percentage"       → [0.80, 0.17, 0.89]  ← similar!
        "Weather in Kampala today"       → [0.12, 0.95, 0.03]  ← very different

    Real embeddings have 1024 dimensions, not 3.

WHAT IS HYBRID SEARCH:
    Dense search finds semantically similar text ("what is WHT" matches
    "withholding tax"). Sparse search finds exact keyword matches
    ("Section 21(1)(a)" matches "Section 21(1)(a)"). Combining both
    gives you the best of both worlds.

HOW TO RUN:
    from embedder import embed_and_store
    embed_and_store(chunks_list)

REQUIREMENTS:
    pip install FlagEmbedding qdrant-client torch
"""

import json
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, SparseVectorParams, Distance,
    PointStruct, SparseVector,
)

from config import Config

# ── Config ────────────────────────────────────────────────
QDRANT_URL = Config.QDRANT_URL
COLLECTION = Config.QDRANT_COLLECTION
BATCH_SIZE = 32  # how many chunks to embed + upload at once


def _get_model():
    """
    Load the BGE-M3 embedding model.

    This downloads ~2GB the first time. After that it's cached.
    If your machine doesn't have a GPU, it will run on CPU (slower but works).
    """
    print("  Loading BGE-M3 model (first time takes a few minutes)...")
    from FlagEmbedding import BGEM3FlagModel
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    print("  ✓ Model loaded.")
    return model


def create_collection(client: QdrantClient):
    """
    Create the Qdrant collection with hybrid vector config.

    This sets up TWO vector spaces in one collection:
        "dense"  → 1024-dim vectors for semantic search
        "sparse" → variable-length vectors for keyword search
    """
    # Check if collection already exists
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION in collections:
        print(f"  Collection '{COLLECTION}' already exists. Deleting and recreating...")
        client.delete_collection(COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "dense": VectorParams(
                size=1024,               # BGE-M3 produces 1024-dim vectors
                distance=Distance.COSINE, # cosine similarity for matching
            )
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams()  # sparse vectors for keyword matching
        },
    )
    print(f"  ✓ Collection '{COLLECTION}' created with hybrid vector config.\n")


def embed_and_store(chunks: list[dict]):
    """
    Embed all chunks with BGE-M3 and store in Qdrant.

    INPUT:
        chunks — list of dicts from parser.py, each with:
            text, title, source, url, section, chunk_id

    PROCESS:
        1. Load BGE-M3 model
        2. Create Qdrant collection (if not exists)
        3. For each batch of chunks:
           a. Embed text → get dense + sparse vectors
           b. Upload to Qdrant with metadata payload
    """
    if not chunks:
        print("  ⚠ No chunks to embed.")
        return

    # Connect to Qdrant
    client = QdrantClient(url=QDRANT_URL)
    print(f"\n🧮 Embedding {len(chunks)} chunks into Qdrant...")
    print(f"  Qdrant URL: {QDRANT_URL}")
    print(f"  Collection: {COLLECTION}")

    # Create collection
    create_collection(client)

    # Load BGE-M3
    model = _get_model()

    # Process in batches
    total_stored = 0
    for batch_start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[batch_start:batch_start + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"  Batch {batch_num}/{total_batches} ({len(texts)} chunks)...", end=" ", flush=True)

        # ── Embed ─────────────────────────────────────────
        # BGE-M3 returns both dense and sparse in one call
        output = model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,  # we don't need ColBERT for this
        )

        dense_vecs = output["dense_vecs"]       # shape: [batch_size, 1024]
        sparse_dict = output["lexical_weights"]  # list of {token_id: weight}

        # ── Build Qdrant points ───────────────────────────
        points = []
        for i, chunk in enumerate(batch):
            # Convert sparse weights to Qdrant format
            sparse_indices = list(sparse_dict[i].keys())
            sparse_values = list(sparse_dict[i].values())

            point = PointStruct(
                id=total_stored + i,  # unique integer ID
                vector={
                    "dense": dense_vecs[i].tolist(),
                    "sparse": SparseVector(
                        indices=[int(idx) for idx in sparse_indices],
                        values=[float(val) for val in sparse_values],
                    ),
                },
                payload={
                    # This metadata is what the LLM uses for citations
                    "text": chunk["text"],
                    "title": chunk["title"],
                    "source": chunk["source"],
                    "url": chunk["url"],
                    "section": chunk.get("section"),
                    "chunk_id": chunk["chunk_id"],
                    "chunk_index": chunk.get("chunk_index", 0),
                },
            )
            points.append(point)

        # ── Upload to Qdrant ──────────────────────────────
        client.upsert(collection_name=COLLECTION, points=points)
        total_stored += len(points)
        print(f"✓ ({total_stored}/{len(chunks)} stored)")

    # Verify
    info = client.get_collection(COLLECTION)
    print(f"\n  ✅ Done! Collection '{COLLECTION}' now has {info.points_count} points.\n")


if __name__ == "__main__":
    # Quick test: embed a few sample chunks
    test_chunks = [
        {
            "text": "Section 19. Tax rate for companies. The tax rate for a resident company is thirty percent of the chargeable income.",
            "title": "Income Tax Act",
            "source": "ulii",
            "url": "https://ulii.org/test",
            "section": "Section 19",
            "chunk_id": "test_0001",
        },
        {
            "text": "Section 5. Imposition of tax. A tax to be known as value added tax shall be charged on every taxable supply made by a taxable person.",
            "title": "VAT Act",
            "source": "ulii",
            "url": "https://ulii.org/test2",
            "section": "Section 5",
            "chunk_id": "test_0002",
        },
    ]
    embed_and_store(test_chunks)