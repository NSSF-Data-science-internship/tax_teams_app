from embedder import (
    BGEM3Embeddings,
    POSTGRES_CONNECTION,
    COLLECTION_NAME,
)

from langchain_postgres import PGVector


print("Connecting to PostgreSQL + pgvector...")

embeddings = BGEM3Embeddings()

store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=POSTGRES_CONNECTION,
    use_jsonb=True,
)

print("Connected.")
print("\nSearching tax-law documents...\n")

results = store.similarity_search(
    "What is the standard VAT rate in Uganda?",
    k=4,
)

print(f"RESULT COUNT: {len(results)}")

for i, doc in enumerate(results, 1):
    print("\n" + "=" * 60)
    print(f"RESULT {i}")
    print("=" * 60)

    print("\nTEXT:")
    print(doc.page_content[:1000])

    print("\nMETADATA:")
    print(doc.metadata)