import asyncio
import time
from typing import Any

from llm_client import answer_tax_question, rewrite_question_for_retrieval
from tax_search_client import search_tax_law


GREETING_WORDS = {"hi", "hello", "hey", "good morning", "good afternoon"}
THANKS_WORDS = {"thanks", "thank you", "okay thanks", "great thanks"}
REUSE_EVIDENCE_PHRASES = (
    "explain that",
    "explain it",
    "more simply",
    "simpler terms",
    "give me an example",
    "summarise that",
    "summarize that",
)


def _simple_conversation_reply(question: str) -> str | None:
    normalized = " ".join(question.lower().strip().rstrip("!?.").split())
    if normalized in GREETING_WORDS:
        return (
            "Hello! I’m TaxPal. I can help you understand Ugandan taxes and "
            "tax laws. What would you like to know?"
        )
    if normalized in THANKS_WORDS:
        return "You’re welcome. Is there another Ugandan tax question I can help with?"
    return None


def _last_documents(history: list[dict]) -> list[dict]:
    for message in reversed(history):
        documents = message.get("documents")
        if message.get("role") == "assistant" and documents:
            return documents
    return []


def _can_reuse_evidence(question: str, history: list[dict]) -> bool:
    normalized = question.lower()
    return bool(_last_documents(history)) and any(
        phrase in normalized for phrase in REUSE_EVIDENCE_PHRASES
    )


async def run_conversation_turn(
    question: str,
    history: list[dict] | None = None,
    k: int = 4,
) -> dict[str, Any]:
    """Run one conversational RAG turn and return UI-neutral diagnostics."""
    history = history or []
    started = time.perf_counter()

    simple_reply = _simple_conversation_reply(question)
    if simple_reply:
        return {
            "answer": simple_reply,
            "documents": [],
            "search_query": None,
            "retrieval_used": False,
            "retrieval_reused": False,
            "rewrite_seconds": 0.0,
            "search_seconds": 0.0,
            "generation_seconds": 0.0,
            "total_seconds": time.perf_counter() - started,
        }

    rewrite_seconds = 0.0
    search_seconds = 0.0
    retrieval_reused = _can_reuse_evidence(question, history)

    if retrieval_reused:
        search_query = None
        documents = _last_documents(history)
    else:
        rewrite_started = time.perf_counter()
        search_query = await asyncio.to_thread(
            rewrite_question_for_retrieval,
            question,
            history,
        )
        rewrite_seconds = time.perf_counter() - rewrite_started

        search_started = time.perf_counter()
        documents = await search_tax_law(search_query, k=k)
        search_seconds = time.perf_counter() - search_started

    generation_started = time.perf_counter()
    answer = await asyncio.to_thread(
        answer_tax_question,
        question,
        documents,
        history,
    )
    generation_seconds = time.perf_counter() - generation_started

    return {
        "answer": answer,
        "documents": documents,
        "search_query": search_query,
        "retrieval_used": not retrieval_reused,
        "retrieval_reused": retrieval_reused,
        "rewrite_seconds": rewrite_seconds,
        "search_seconds": search_seconds,
        "generation_seconds": generation_seconds,
        "total_seconds": time.perf_counter() - started,
    }
