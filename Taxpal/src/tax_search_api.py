from fastapi import FastAPI
from pydantic import BaseModel

from embedder import (
    BGEM3Embeddings,
    COLLECTION_NAME,
    CHROMA_HOST,
    CHROMA_PORT,
    create_vector_store,
)


app = FastAPI(
    title="TaxPal Tax Law Search API"
)


class SearchRequest(BaseModel):
    query: str
    k: int = 4


print("Loading BGE-M3 embeddings...")

embeddings = BGEM3Embeddings()

print(f"Connecting to Chroma at {CHROMA_HOST}:{CHROMA_PORT}...")

store = create_vector_store(embeddings)

print("Tax search service ready.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "tax-search",
        "vector_store": "chroma",
        "collection": COLLECTION_NAME,
        "document_count": store._collection.count(),
    }


@app.post("/search-tax-law")
def search_tax_law(request: SearchRequest):

    results = store.similarity_search_with_relevance_scores(
        request.query,
        k=request.k,
    )

    return {
        "query": request.query,
        "count": len(results),
        "results": [
            {
                "text": doc.page_content,
                "metadata": {**doc.metadata, "relevance_score": score},
            }
            for doc, score in results
        ],
    }
