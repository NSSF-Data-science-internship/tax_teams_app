from embedder import BGEM3Embeddings, CHROMA_HOST, CHROMA_PORT, create_vector_store


print(f"Connecting to Chroma at {CHROMA_HOST}:{CHROMA_PORT}...")
store = create_vector_store(BGEM3Embeddings())

print("Connected.")
print("\nSearching tax-law documents...\n")

results = store.similarity_search_with_relevance_scores(
    "What is the standard VAT rate in Uganda?",
    k=4,
)

print(f"RESULT COUNT: {len(results)}")

for index, (document, score) in enumerate(results, 1):
    print("\n" + "=" * 60)
    print(f"RESULT {index} (relevance={score:.4f})")
    print("=" * 60)
    print("\nTEXT:")
    print(document.page_content[:1000])
    print("\nMETADATA:")
    print(document.metadata)
