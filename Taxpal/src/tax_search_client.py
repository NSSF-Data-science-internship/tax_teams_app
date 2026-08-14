import os

import httpx


TAX_SEARCH_URL = os.getenv(
    "TAX_SEARCH_URL",
    "http://localhost:8001"
)


async def search_tax_law(
    question: str,
    k: int = 4,
) -> list[dict]:
    """
    Search the TaxPal pgvector knowledge base.
    """

    async with httpx.AsyncClient(
        timeout=60.0
    ) as client:

        response = await client.post(
            f"{TAX_SEARCH_URL}/search-tax-law",
            json={
                "query": question,
                "k": k,
            },
        )

        response.raise_for_status()

        data = response.json()

        return data.get("results", [])