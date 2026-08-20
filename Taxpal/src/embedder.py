"""
embedder.py
Embed TaxPal tax-law chunks with BGE-M3 and store them in Chroma.
"""

import os

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma

from FlagEmbedding import BGEM3FlagModel


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION", "uganda_tax_law")
CHROMA_HOST = os.environ.get("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "18000"))

BATCH_SIZE = 32


# ---------------------------------------------------------
# LangChain-compatible BGE-M3 embeddings
# ---------------------------------------------------------

class BGEM3Embeddings(Embeddings):

    def __init__(self):
        print("Loading BGE-M3 model...")
        self.model = BGEM3FlagModel(
            "BAAI/bge-m3",
            use_fp16=True,
        )
        print("✓ BGE-M3 loaded.")

    def embed_documents(self, texts):
        output = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

        return [
            vector.tolist()
            for vector in output["dense_vecs"]
        ]

    def embed_query(self, text):
        output = self.model.encode(
            [text],
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

        return output["dense_vecs"][0].tolist()


def create_vector_store(embeddings: Embeddings | None = None) -> Chroma:
    """Connect to TaxPal's server-backed Chroma collection."""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings or BGEM3Embeddings(),
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        ssl=False,
        collection_metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------
# Store chunks
# ---------------------------------------------------------

def embed_and_store(chunks: list[dict]):

    if not chunks:
        print("⚠ No chunks to embed.")
        return

    print(
        f"\nEmbedding {len(chunks)} chunks "
        f"into Chroma at {CHROMA_HOST}:{CHROMA_PORT}..."
    )

    embeddings = BGEM3Embeddings()

    vector_store = create_vector_store(embeddings)

    total = 0

    for batch_start in range(
        0,
        len(chunks),
        BATCH_SIZE,
    ):

        batch = chunks[
            batch_start:
            batch_start + BATCH_SIZE
        ]

        documents = []

        ids = []

        for chunk in batch:

            document = Document(
                page_content=chunk["text"],
                metadata={
                    "title": chunk.get("title") or "Unknown",
                    "source": chunk.get("source") or "",
                    "url": chunk.get("url") or "",
                    "section": chunk.get("section") or "",
                    "chunk_id": str(chunk.get("chunk_id") or ""),
                    "chunk_index": int(chunk.get("chunk_index") or 0),
                    "evidence_type": "local_document",
                    "publication_date": chunk.get("publication_date") or "",
                    "effective_from": chunk.get("effective_from") or "",
                    "effective_to": chunk.get("effective_to") or "",
                },
            )

            documents.append(document)

            chunk_id = chunk.get("chunk_id")
            if not chunk_id:
                chunk_id = f"chunk_{batch_start + len(ids):06d}"
            ids.append(str(chunk_id))

        vector_store.add_documents(
            documents=documents,
            ids=ids,
        )

        total += len(documents)

        print(
            f"✓ {total}/{len(chunks)} stored"
        )

    print(
        f"\n✅ Finished storing "
        f"{total} chunks in '{COLLECTION_NAME}'."
    )


# ---------------------------------------------------------
# Optional direct test
# ---------------------------------------------------------

if __name__ == "__main__":

    test_chunks = [
        {
            "text": (
                "Value Added Tax is imposed "
                "under the Value Added Tax Act."
            ),
            "title": "VAT Act",
            "source": "local",
            "url": "",
            "section": "Test",
            "chunk_id": "test_001",
            "chunk_index": 0,
        }
    ]

    embed_and_store(test_chunks)
