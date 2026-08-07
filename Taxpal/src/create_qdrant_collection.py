from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams
)


QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "uganda_tax_law"


client = QdrantClient(
    url=QDRANT_URL
)


existing = [
    collection.name
    for collection in client.get_collections().collections
]


if COLLECTION_NAME in existing:
    print(
        f"Collection '{COLLECTION_NAME}' already exists."
    )

else:

    client.create_collection(
        collection_name=COLLECTION_NAME,

        vectors_config=VectorParams(
            size=1024,
            distance=Distance.COSINE
        )
    )

    print(
        f"Created collection: {COLLECTION_NAME}"
    )