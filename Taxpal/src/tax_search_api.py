from fastapi import FastAPI
from pydantic import BaseModel

from embedder import (
    BGEM3Embeddings,
    POSTGRES_CONNECTION,
    COLLECTION_NAME,
)

from langchain_postgres import PGVector


app = FastAPI(
    title="TaxPal Tax Law Search API"
)


class SearchRequest(BaseModel):
    query: str
    k: int = 4


print("Loading BGE-M3 embeddings...")

embeddings = BGEM3Embeddings()

print("Connecting to PGVector...")

store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=POSTGRES_CONNECTION,
    use_jsonb=True,
)

print("Tax search service ready.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "tax-search"
    }


@app.post("/search-tax-law")
def search_tax_law(request: SearchRequest):

    results = store.similarity_search(
        request.query,
        k=request.k,
    )

    return {
        "query": request.query,
        "count": len(results),
        "results": [
            {
                "text": doc.page_content,
                "metadata": doc.metadata,
            }
            for doc in results
        ],
    }