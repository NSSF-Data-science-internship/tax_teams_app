"""Copy TaxPal's existing pgvector records into Chroma without re-embedding.

PostgreSQL remains in use for conversation history. This script reads only the
legacy LangChain vector tables and upserts the same IDs, dense BGE-M3 vectors,
documents, and metadata into the configured Chroma collection.
"""

import json
import os
from typing import Any

import chromadb
import psycopg


POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "15432")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "taxpal")
POSTGRES_USER = os.getenv("POSTGRES_USER", "taxpal")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "taxpal_dev_password")

CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "uganda_tax_law")
SOURCE_COLLECTION = os.getenv("PGVECTOR_COLLECTION", "uganda_tax_law")
BATCH_SIZE = int(os.getenv("CHROMA_MIGRATION_BATCH_SIZE", "64"))


def _metadata(value: Any) -> dict[str, str | int | float | bool]:
    """Return metadata containing only Chroma-supported scalar values."""
    if not isinstance(value, dict):
        return {}

    cleaned: dict[str, str | int | float | bool] = {}
    for key, item in value.items():
        if item is None:
            cleaned[str(key)] = ""
        elif isinstance(item, (str, int, float, bool)):
            cleaned[str(key)] = item
        else:
            cleaned[str(key)] = json.dumps(item, ensure_ascii=False)
    return cleaned


def migrate() -> int:
    connection_string = (
        f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DATABASE} "
        f"user={POSTGRES_USER} password={POSTGRES_PASSWORD}"
    )
    query = """
        SELECT e.id, e.embedding::text, e.document, e.cmetadata
        FROM langchain_pg_embedding AS e
        JOIN langchain_pg_collection AS c ON c.uuid = e.collection_id
        WHERE c.name = %s
        ORDER BY e.id
    """

    with psycopg.connect(connection_string) as postgres:
        with postgres.cursor() as cursor:
            cursor.execute(query, (SOURCE_COLLECTION,))
            records = cursor.fetchall()

    if not records:
        raise RuntimeError(
            f"No vectors found in legacy pgvector collection '{SOURCE_COLLECTION}'."
        )

    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT, ssl=False)
    client.heartbeat()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "embedding_model": "BAAI/bge-m3"},
    )

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        collection.upsert(
            ids=[str(record[0]) for record in batch],
            embeddings=[json.loads(record[1]) for record in batch],
            documents=[record[2] or "" for record in batch],
            metadatas=[_metadata(record[3]) for record in batch],
        )
        print(f"Migrated {min(start + len(batch), len(records))}/{len(records)} records")

    count = collection.count()
    if count < len(records):
        raise RuntimeError(
            f"Chroma contains {count} records after migrating {len(records)} records."
        )

    print(
        f"Migration complete: {count} records in Chroma collection "
        f"'{COLLECTION_NAME}'."
    )
    return count


if __name__ == "__main__":
    migrate()
