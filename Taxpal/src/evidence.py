import re
from datetime import date
from typing import Any


def build_citations(documents: list[dict]) -> list[dict[str, Any]]:
    citations = []
    for index, document in enumerate(documents, start=1):
        metadata = document.get("metadata") or {}
        citations.append(
            {
                "id": f"S{index}",
                "title": metadata.get("title") or "Untitled source",
                "section": metadata.get("section") or "",
                "publisher": metadata.get("source") or metadata.get("publisher") or "Unknown publisher",
                "url": metadata.get("url") or "",
                "evidence_type": metadata.get("evidence_type") or "local_document",
                "publication_date": metadata.get("publication_date") or metadata.get("published_at") or "",
                "effective_from": metadata.get("effective_from") or "",
                "effective_to": metadata.get("effective_to") or "",
                "accessed_at": metadata.get("accessed_at") or "",
                "relevance_score": metadata.get("relevance_score"),
                "claim_key": metadata.get("claim_key"),
                "claim_value": metadata.get("claim_value"),
            }
        )
    return citations


def _conflicts(citations: list[dict]) -> list[str]:
    claims: dict[str, set[str]] = {}
    for citation in citations:
        key, value = citation.get("claim_key"), citation.get("claim_value")
        if key and value is not None:
            claims.setdefault(str(key), set()).add(str(value))
    return [key for key, values in claims.items() if len(values) > 1]


def assess_evidence(answer: str, citations: list[dict]) -> dict[str, Any]:
    valid_ids = {citation["id"] for citation in citations}
    cited_ids = set(re.findall(r"\[(S\d+)\]", answer))
    invalid_ids = sorted(cited_ids - valid_ids)
    conflicts = _conflicts(citations)
    warnings = []

    if not citations:
        warnings.append("No supporting evidence was available.")
    if citations and not (cited_ids & valid_ids):
        warnings.append("The generated answer has no claim-level source markers.")
    if invalid_ids:
        warnings.append(f"The answer referenced unknown source IDs: {', '.join(invalid_ids)}.")
    if conflicts:
        warnings.append(f"Structured evidence conflicts on: {', '.join(conflicts)}.")

    today = date.today().isoformat()
    expired = [c["id"] for c in citations if c.get("effective_to") and c["effective_to"] < today]
    if expired:
        warnings.append(f"Sources outside their stated effective period: {', '.join(expired)}.")

    undated = [
        c["id"] for c in citations
        if not any((c.get("publication_date"), c.get("effective_from"), c.get("accessed_at")))
    ]
    if undated:
        warnings.append(f"No publication, effective, or access date is recorded for: {', '.join(undated)}.")

    if not citations or conflicts or invalid_ids:
        confidence = "low"
    elif warnings:
        confidence = "moderate"
    else:
        confidence = "high"

    origins: dict[str, int] = {}
    for citation in citations:
        origin = citation["evidence_type"]
        origins[origin] = origins.get(origin, 0) + 1

    return {
        "confidence": confidence,
        "warnings": warnings,
        "cited_ids": sorted(cited_ids & valid_ids),
        "uncited_ids": sorted(valid_ids - cited_ids),
        "invalid_ids": invalid_ids,
        "conflict_keys": conflicts,
        "origins": origins,
    }


def append_source_register(answer: str, citations: list[dict], assessment: dict) -> str:
    if not citations:
        return answer
    lines = [answer.rstrip(), "", "**Sources**"]
    for citation in citations:
        label = citation["title"]
        if citation["section"]:
            label += f" — {citation['section']}"
        if citation["url"]:
            lines.append(f"- [{citation['id']}] [{label}]({citation['url']}) ({citation['publisher']})")
        else:
            lines.append(f"- [{citation['id']}] {label} ({citation['publisher']})")
    if assessment["warnings"]:
        lines.extend(["", f"**Evidence confidence:** {assessment['confidence'].title()}. " + " ".join(assessment["warnings"])])
    return "\n".join(lines)


def calculation_citations(calculation: dict) -> list[dict]:
    url = calculation.get("source_url")
    if not url:
        return []
    return [{
        "id": "S1",
        "title": calculation.get("source", "Tax calculation rule"),
        "section": calculation.get("rule_version", ""),
        "publisher": "Uganda Revenue Authority",
        "url": url,
        "evidence_type": "versioned_tax_rule",
        "publication_date": "",
        "effective_from": calculation.get("effective_from", ""),
        "effective_to": calculation.get("effective_to", ""),
        "accessed_at": calculation.get("verified_on", ""),
        "relevance_score": None,
        "claim_key": None,
        "claim_value": None,
    }]
