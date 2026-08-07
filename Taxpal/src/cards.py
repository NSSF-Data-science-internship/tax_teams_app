from botbuilder.schema import Attachment


def build_citation_card(
    answer: str,
    sources: list | None = None
) -> Attachment:

    sources = sources or []

    body = [
        {
            "type": "TextBlock",
            "text": "Clause — Uganda Tax Assistant",
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True
        },
        {
            "type": "TextBlock",
            "text": answer,
            "wrap": True
        }
    ]

    # Add sources when available
    if sources:

        body.append({
            "type": "TextBlock",
            "text": "Sources",
            "weight": "Bolder",
            "spacing": "Medium",
            "wrap": True
        })

        for index, source in enumerate(sources[:3], start=1):

            source_text = format_source(source, index)

            body.append({
                "type": "TextBlock",
                "text": source_text,
                "wrap": True,
                "size": "Small"
            })

    # Legal/informational disclaimer
    body.append({
        "type": "TextBlock",
        "text": (
            "Clause provides tax information for informational "
            "purposes only. It does not constitute legal, tax, "
            "or financial advice."
        ),
        "wrap": True,
        "size": "Small",
        "isSubtle": True,
        "spacing": "Medium"
    })

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card
    )


def format_source(source, index: int) -> str:
    """
    Convert source metadata returned by Langflow/Qdrant
    into readable citation text.
    """

    if isinstance(source, str):
        return f"{index}. {source}"

    if not isinstance(source, dict):
        return f"{index}. Source"

    title = (
        source.get("title")
        or source.get("document")
        or source.get("source")
        or "Tax document"
    )

    act = source.get("act")
    section = (
        source.get("section")
        or source.get("section_number")
    )

    parts = [title]

    if act:
        parts.append(act)

    if section:
        parts.append(f"Section {section}")

    return f"{index}. " + " — ".join(parts)