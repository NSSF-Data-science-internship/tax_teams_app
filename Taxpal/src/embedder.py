"""
embedder.py
Embed TaxPal tax-law chunks with BGE-M3 and store them
in PostgreSQL using pgvector / LangChain PGVector.
"""

import os

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

from FlagEmbedding import BGEM3FlagModel


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

COLLECTION_NAME = os.environ.get("PGVECTOR_COLLECTION", "uganda_tax_law")

# Because ingest.py runs on your Windows machine:
POSTGRES_HOST = os.getenv(
    "POSTGRES_HOST",
    "localhost",
)
POSTGRES_PORT = os.getenv(
    "POSTGRES_PORT",
    "15432",
)
POSTGRES_CONNECTION = os.environ.get(
    "POSTGRES_CONNECTION",
    f"postgresql+psycopg://taxpal:taxpal_dev_password@{POSTGRES_HOST}:{POSTGRES_PORT}/taxpal"
)

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


# ---------------------------------------------------------
# Store chunks
# ---------------------------------------------------------

def embed_and_store(chunks: list[dict]):

    if not chunks:
        print("⚠ No chunks to embed.")
        return

    print(
        f"\nEmbedding {len(chunks)} chunks "
        f"into PostgreSQL/pgvector..."
    )

    embeddings = BGEM3Embeddings()

    vector_store = PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=POSTGRES_CONNECTION,
        use_jsonb=True,
    )

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
                    "title": chunk.get(
                        "title",
                        "Unknown"
                    ),
                    "source": chunk.get(
                        "source",
                        ""
                    ),
                    "url": chunk.get(
                        "url",
                        ""
                    ),
                    "section": chunk.get(
                        "section"
                    ),
                    "chunk_id": chunk.get(
                        "chunk_id"
                    ),
                    "chunk_index": chunk.get(
                        "chunk_index",
                        0
                    ),
                },
            )

            documents.append(document)

            ids.append(
                str(chunk.get("chunk_id"))
            )

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
