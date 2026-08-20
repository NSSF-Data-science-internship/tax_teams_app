"""Adaptive Card responses for the Microsoft Teams TaxPal interface."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from microsoft_teams.api import Attachment, MessageActivityInput


CARD_CONTENT_TYPE = "application/vnd.microsoft.card.adaptive"
DISCLAIMER = (
    "TaxPal provides general tax information, not professional tax, legal, "
    "or financial advice. Confirm material decisions against current official guidance."
)


def _answer_body(answer: str) -> str:
    """Return a clean user-facing answer while retaining citations in card metadata."""
    body = re.split(r"\n\n\*\*(?:Sources|Based on)\*\*", answer, maxsplit=1)[0].strip()
    body = re.sub(r"\s*\[S\d+\]", "", body, flags=re.IGNORECASE)
    return re.sub(r"\s+([.,;:!?])", r"\1", body).strip()


def _money(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    return f"UGX {amount:,.2f}"


def _calculation_facts(calculation: dict[str, Any]) -> list[dict[str, str]]:
    kind = calculation.get("kind", "calculation")
    labels = {
        "vat": "VAT calculation",
        "vat_rate_fact": "Standard VAT rate",
        "paye": "PAYE calculation",
        "business_income": "Business income tax",
        "rental": "Rental income tax",
        "corporate": "Corporate income tax",
        "withholding": "Withholding tax",
        "percentage": calculation.get("label", "Percentage calculation"),
    }
    label = labels.get(kind, kind.replace("_", " ").title())
    facts = [{"title": "Calculation", "value": str(label)}]

    value_fields = (
        ("input_amount", "Input amount"),
        ("net_amount", "Net amount"),
        ("chargeable_income", "Chargeable income"),
        ("allowed_expenses", "Allowed expenses"),
        ("vat_amount", "VAT amount"),
        ("tax_amount", "Tax amount"),
        ("gross_amount", "Total amount"),
    )
    for key, title in value_fields:
        if calculation.get(key) is not None:
            facts.append({"title": title, "value": _money(calculation[key])})

    if calculation.get("rate") is not None:
        facts.append({"title": "Rate", "value": f"{calculation['rate']}%"})
    if calculation.get("tax_year"):
        facts.append({"title": "Tax year", "value": str(calculation["tax_year"])})
    if calculation.get("rule_version"):
        facts.append({"title": "Rule version", "value": str(calculation["rule_version"])})
    if calculation.get("verified_on"):
        facts.append({"title": "Verified", "value": str(calculation["verified_on"])})
    return facts


def _source_text(citation: dict[str, Any]) -> str:
    source_id = citation.get("id", "Source")
    title = citation.get("title") or "Untitled source"
    section = citation.get("section")
    publisher = citation.get("publisher")
    url = citation.get("url")
    label = f"[{source_id}] {title}"
    if section:
        label += f" — {section}"
    if url:
        label = f"[{label}]({url})"
    if publisher:
        label += f"  \n{publisher}"
    return label


def build_taxpal_card(result: dict[str, Any]) -> dict[str, Any]:
    """Build an Adaptive Card from a ``run_conversation_turn`` result."""
    answer = str(result.get("answer") or "I could not prepare an answer.").strip()
    calculation = result.get("calculation") or None
    citations = list(result.get("citations") or [])[:4]
    assessment = result.get("evidence_assessment") or {}
    confidence = str(assessment.get("confidence") or "not_applicable")
    confidence_labels = {
        "high": ("High confidence", "Good"),
        "moderate": ("Moderate confidence", "Warning"),
        "low": ("Low confidence", "Attention"),
        "not_applicable": ("Informational response", "Accent"),
    }
    confidence_text, confidence_color = confidence_labels.get(
        confidence, (confidence.replace("_", " ").title(), "Default")
    )

    body: list[dict[str, Any]] = [
        {
            "type": "Container",
            "style": "emphasis",
            "bleed": True,
            "items": [
                {
                    "type": "TextBlock",
                    "text": "TaxPal",
                    "weight": "Bolder",
                    "size": "Large",
                    "color": "Accent",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": "Uganda Tax Assistant",
                    "isSubtle": True,
                    "spacing": "None",
                    "wrap": True,
                },
            ],
        },
        {
            "type": "TextBlock",
            "text": _answer_body(answer),
            "wrap": True,
            "spacing": "Medium",
        },
    ]

    if calculation:
        body.extend(
            [
                {
                    "type": "TextBlock",
                    "text": "Calculation details",
                    "weight": "Bolder",
                    "separator": True,
                    "spacing": "Medium",
                    "wrap": True,
                },
                {"type": "FactSet", "facts": _calculation_facts(calculation)},
            ]
        )

    warnings = list(assessment.get("warnings") or [])
    detail_body: list[dict[str, Any]] = []
    if citations or warnings:
        detail_body.append(
            {
                "type": "TextBlock",
                "text": confidence_text,
                "weight": "Bolder",
                "color": confidence_color,
                "wrap": True,
                "size": "Small",
            }
        )
        for citation in citations:
            detail_body.append(
                {
                    "type": "TextBlock",
                    "text": _source_text(citation),
                    "wrap": True,
                    "size": "Small",
                    "spacing": "Small",
                }
            )
        if warnings:
            detail_body.append(
                {
                    "type": "TextBlock",
                    "text": "Note: " + " ".join(str(item) for item in warnings),
                    "wrap": True,
                    "size": "Small",
                    "color": "Warning",
                    "separator": True,
                }
            )
        detail_body.append(
            {
                "type": "TextBlock",
                "text": DISCLAIMER,
                "wrap": True,
                "size": "Small",
                "isSubtle": True,
                "separator": True,
            }
        )

    actions = []
    if detail_body:
        source_label = f"View sources ({len(citations)})" if citations else "Answer details"
        actions.append(
            {
                "type": "Action.ShowCard",
                "title": source_label,
                "card": {
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": detail_body,
                },
            }
        )

    card: dict[str, Any] = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "fallbackText": _answer_body(answer),
        "body": body,
    }
    if actions:
        card["actions"] = actions
    return card


def build_taxpal_card_message(result: dict[str, Any]) -> MessageActivityInput:
    card = build_taxpal_card(result)
    attachment = Attachment(contentType=CARD_CONTENT_TYPE, content=card)
    return MessageActivityInput(attachments=[attachment])


def build_citation_card(answer: str, sources: list[dict[str, Any]] | None = None) -> Attachment:
    """Compatibility helper for callers that still use the former card API."""
    citations = []
    for index, source in enumerate(sources or [], start=1):
        citation = dict(source) if isinstance(source, dict) else {"title": str(source)}
        citation.setdefault("id", f"S{index}")
        citations.append(citation)
    card = build_taxpal_card({"answer": answer, "citations": citations})
    return Attachment(contentType=CARD_CONTENT_TYPE, content=card)
