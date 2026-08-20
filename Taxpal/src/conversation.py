import asyncio
import time
from typing import Any

from evidence import assess_evidence, append_source_register, build_citations, calculation_citations
from llm_client import answer_tax_question, rewrite_question_for_retrieval
from tax_search_client import TaxSearchUnavailable, search_tax_law
from tax_calculator import format_tax_answer, parse_tax_request
from trusted_web import search_trusted_web, should_search_web


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
    user_profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run one conversational RAG turn and return UI-neutral diagnostics."""
    history = history or []
    started = time.perf_counter()

    simple_reply = _simple_conversation_reply(question)
    if simple_reply:
        return {
            "answer": simple_reply,
            "documents": [],
            "citations": [],
            "evidence_assessment": {"confidence": "not_applicable", "warnings": [], "origins": {}},
            "search_query": None,
            "retrieval_used": False,
            "retrieval_reused": False,
            "rewrite_seconds": 0.0,
            "search_seconds": 0.0,
            "generation_seconds": 0.0,
            "total_seconds": time.perf_counter() - started,
        }

    try:
        calculation = parse_tax_request(question)
    except ValueError as exc:
        return {
            "answer": str(exc),
            "documents": [],
            "citations": [],
            "evidence_assessment": {"confidence": "not_applicable", "warnings": [], "origins": {}},
            "calculation": None,
            "search_query": None,
            "retrieval_used": False,
            "retrieval_reused": False,
            "calculator_used": True,
            "rewrite_seconds": 0.0,
            "search_seconds": 0.0,
            "generation_seconds": 0.0,
            "web_seconds": 0.0,
            "web_fallback_used": False,
            "web_error": None,
            "total_seconds": time.perf_counter() - started,
        }

    if calculation:
        citations = calculation_citations(calculation)
        evidence_assessment = {
            "confidence": "high" if citations else "not_applicable",
            "warnings": [] if citations else ["This uses a user-specified rate, not a verified statutory source."],
            "cited_ids": [citation["id"] for citation in citations],
            "uncited_ids": [], "invalid_ids": [], "conflict_keys": [],
            "origins": {"versioned_tax_rule": len(citations)} if citations else {},
        }
        return {
            "answer": format_tax_answer(calculation),
            "documents": [],
            "citations": citations,
            "evidence_assessment": evidence_assessment,
            "calculation": calculation,
            "search_query": None,
            "retrieval_used": False,
            "retrieval_reused": False,
            "calculator_used": True,
            "rewrite_seconds": 0.0,
            "search_seconds": 0.0,
            "generation_seconds": 0.0,
            "web_seconds": 0.0,
            "web_fallback_used": False,
            "web_error": None,
            "total_seconds": time.perf_counter() - started,
        }

    rewrite_seconds = 0.0
    search_seconds = 0.0
    web_seconds = 0.0
    web_error = None
    web_documents = []
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
        local_search_error = None
        try:
            documents = await search_tax_law(search_query, k=k)
        except TaxSearchUnavailable as exc:
            documents = []
            local_search_error = str(exc)
        search_seconds = time.perf_counter() - search_started

        if should_search_web(question, documents):
            web_started = time.perf_counter()
            try:
                web_documents = await asyncio.to_thread(
                    search_trusted_web,
                    question,
                )
                documents = documents + web_documents
            except Exception as exc:
                web_error = str(exc)
            web_seconds = time.perf_counter() - web_started

        if not documents and local_search_error:
            details = (
                f" Trusted official search also failed: {web_error}"
                if web_error
                else ""
            )
            raise TaxSearchUnavailable(local_search_error + details)

    generation_started = time.perf_counter()
    answer = await asyncio.to_thread(
        answer_tax_question,
        question,
        documents,
        history,
        user_profile,
    )
    generation_seconds = time.perf_counter() - generation_started
    citations = build_citations(documents)
    evidence_assessment = assess_evidence(answer, citations)
    answer = append_source_register(answer, citations, evidence_assessment)

    return {
        "answer": answer,
        "documents": documents,
        "citations": citations,
        "evidence_assessment": evidence_assessment,
        "search_query": search_query,
        "retrieval_used": not retrieval_reused,
        "retrieval_reused": retrieval_reused,
        "rewrite_seconds": rewrite_seconds,
        "search_seconds": search_seconds,
        "generation_seconds": generation_seconds,
        "web_seconds": web_seconds,
        "web_fallback_used": bool(web_documents),
        "web_error": web_error,
        "total_seconds": time.perf_counter() - started,
    }
