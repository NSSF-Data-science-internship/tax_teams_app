"""Client and routing policy for TaxPal's optional GraphRAG service."""

from __future__ import annotations

import asyncio
import os
import re

import httpx


GRAPH_RAG_URL = os.getenv("GRAPH_RAG_URL", "http://127.0.0.1:8002").rstrip("/")
GRAPH_RAG_ENABLED = os.getenv("GRAPH_RAG_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on",
}
GRAPH_RAG_TIMEOUT = float(os.getenv("GRAPH_RAG_TIMEOUT", "180"))
GRAPH_RAG_RETRIES = int(os.getenv("GRAPH_RAG_RETRIES", "2"))
GRAPH_RAG_MODE = os.getenv("GRAPH_RAG_MODE", "auto").strip().lower()

GLOBAL_PATTERNS = (
    r"\bacross (?:all|the)\b",
    r"\boverall\b",
    r"\bwhole tax (?:system|framework)\b",
    r"\bmain (?:themes|changes|obligations|relationships)\b",
    r"\bsummari[sz]e (?:all|the main|the overall)\b",
)
LOCAL_PATTERNS = (
    r"\brelationship between\b",
    r"\bhow (?:does|do|did) .+ (?:affect|apply|change|interact|relate)\b",
    r"\b(?:affect|impact|interact|relate|relationship|linked|depends on)\b",
    r"\bcompare\b|\bdifference between\b",
    r"\bamend(?:s|ed|ment)?\b|\boverride(?:s|n)?\b",
)


class GraphRagUnavailable(RuntimeError):
    """Raised when graph retrieval is enabled but unavailable."""


def choose_graph_search_method(question: str) -> str | None:
    """Choose graph retrieval only for questions that benefit from relationships."""
    if not GRAPH_RAG_ENABLED or GRAPH_RAG_MODE == "off":
        return None
    if GRAPH_RAG_MODE in {"local", "global", "drift"}:
        return GRAPH_RAG_MODE

    normalized = " ".join((question or "").lower().split())
    if any(re.search(pattern, normalized) for pattern in GLOBAL_PATTERNS):
        return "global"
    if any(re.search(pattern, normalized) for pattern in LOCAL_PATTERNS):
        return "local"
    return None


async def search_graph_rag(
    question: str,
    method: str,
    k: int = 1,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[dict]:
    """Query the private GraphRAG service and return standard TaxPal documents."""
    if method not in {"local", "global", "drift"}:
        raise ValueError(f"Unsupported GraphRAG search method: {method}")

    last_error: Exception | None = None
    for attempt in range(1, GRAPH_RAG_RETRIES + 1):
        try:
            async with httpx.AsyncClient(
                timeout=GRAPH_RAG_TIMEOUT,
                trust_env=False,
                transport=transport,
            ) as client:
                response = await client.post(
                    f"{GRAPH_RAG_URL}/search-graph",
                    json={"query": question, "method": method, "k": k},
                )
                response.raise_for_status()
                return response.json().get("results", [])
        except (httpx.TransportError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_error = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                break
            if attempt < GRAPH_RAG_RETRIES:
                await asyncio.sleep(2 ** (attempt - 1))

    raise GraphRagUnavailable(
        "The GraphRAG index is unavailable; vector retrieval will continue normally."
    ) from last_error
