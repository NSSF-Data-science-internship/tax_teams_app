import os
import asyncio

import httpx


TAX_SEARCH_URL = os.getenv(
    "TAX_SEARCH_URL",
    "http://127.0.0.1:8001"
)
TAX_SEARCH_TIMEOUT = float(os.getenv("TAX_SEARCH_TIMEOUT", "120"))
TAX_SEARCH_RETRIES = int(os.getenv("TAX_SEARCH_RETRIES", "3"))


class TaxSearchUnavailable(RuntimeError):
    """Raised when the local retrieval service is starting or unavailable."""


async def search_tax_law(
    question: str,
    k: int = 4,
) -> list[dict]:
    """
    Search the TaxPal Chroma knowledge base.
    """

    last_error = None
    for attempt in range(1, TAX_SEARCH_RETRIES + 1):
        try:
            # tax-search is a local/private service. Ignoring ambient proxy
            # variables prevents localhost requests being sent to a corporate
            # or sandbox proxy, which can cause RemoteProtocolError.
            async with httpx.AsyncClient(
                timeout=TAX_SEARCH_TIMEOUT,
                trust_env=False,
            ) as client:
                response = await client.post(
                    f"{TAX_SEARCH_URL}/search-tax-law",
                    json={"query": question, "k": k},
                )
                response.raise_for_status()
                return response.json().get("results", [])
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < TAX_SEARCH_RETRIES:
                await asyncio.sleep(2 ** (attempt - 1))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise
            last_error = exc
            if attempt < TAX_SEARCH_RETRIES:
                await asyncio.sleep(2 ** (attempt - 1))

    raise TaxSearchUnavailable(
        "The tax-law search service is still starting or temporarily "
        "unavailable. BGE-M3 can take several minutes to load after a "
        "rebuild. Check http://localhost:8001/health and try again."
    ) from last_error
