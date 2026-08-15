import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from llm_client import GEMINI_API_KEY, GEMINI_MODEL


TRUSTED_DOMAINS = {
    "ura.go.ug": "Uganda Revenue Authority",
    "www.ura.go.ug": "Uganda Revenue Authority",
    "ulii.org": "Uganda Legal Information Institute",
    "www.ulii.org": "Uganda Legal Information Institute",
    "finance.go.ug": "Ministry of Finance, Planning and Economic Development",
    "www.finance.go.ug": "Ministry of Finance, Planning and Economic Development",
    "parliament.go.ug": "Parliament of Uganda",
    "www.parliament.go.ug": "Parliament of Uganda",
    "bou.or.ug": "Bank of Uganda",
    "www.bou.or.ug": "Bank of Uganda",
}

WEB_REQUEST_PHRASES = (
    "check official sources",
    "check online",
    "search online",
    "search the web",
    "latest",
    "current",
    "recent",
    "this year",
    "today",
)
WEB_RELEVANCE_THRESHOLD = float(os.getenv("WEB_RELEVANCE_THRESHOLD", "0.35"))


def is_trusted_domain(domain_or_url: str) -> bool:
    value = domain_or_url.strip().lower()
    host = urlparse(value).hostname if "://" in value else value
    if not host:
        return False
    return host in TRUSTED_DOMAINS


def should_search_web(question: str, documents: list[dict]) -> bool:
    normalized = question.lower()
    scores = [
        document.get("metadata", {}).get("relevance_score")
        for document in documents
    ]
    numeric_scores = [score for score in scores if isinstance(score, (int, float))]
    weak_local_evidence = (
        bool(numeric_scores)
        and max(numeric_scores) < WEB_RELEVANCE_THRESHOLD
    )
    return (
        not documents
        or weak_local_evidence
        or any(phrase in normalized for phrase in WEB_REQUEST_PHRASES)
    )


def search_trusted_web(question: str) -> list[dict]:
    """Use Gemini grounding, retaining evidence only from approved domains."""
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your-"):
        raise RuntimeError("A Gemini API key is required for trusted web search.")

    from google import genai
    from google.genai import types

    domain_query = " OR ".join(f"site:{domain}" for domain in TRUSTED_DOMAINS)
    prompt = (
        f"Research this Ugandan tax question using only these official or "
        f"approved legal domains: {', '.join(TRUSTED_DOMAINS)}.\n\n"
        f"QUESTION: {question}\n\n"
        "Give a factual evidence summary. Do not use or cite any other domain."
        f"\nSearch constraint: ({domain_query})"
    )

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.0,
        ),
    )

    if not response.candidates:
        return []
    metadata = response.candidates[0].grounding_metadata
    chunks = getattr(metadata, "grounding_chunks", None) or []
    accessed_at = datetime.now(timezone.utc).isoformat()
    documents = []
    seen = set()

    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if not web:
            continue
        domain = (getattr(web, "domain", None) or "").lower()
        uri = getattr(web, "uri", None) or ""
        if not is_trusted_domain(domain):
            continue
        identity = (domain, uri)
        if identity in seen:
            continue
        seen.add(identity)
        documents.append(
            {
                "text": response.text or "",
                "metadata": {
                    "title": getattr(web, "title", None) or TRUSTED_DOMAINS[domain],
                    "source": TRUSTED_DOMAINS[domain],
                    "url": uri,
                    "domain": domain,
                    "section": "Live official web evidence",
                    "evidence_type": "trusted_web",
                    "accessed_at": accessed_at,
                },
            }
        )

    return documents
