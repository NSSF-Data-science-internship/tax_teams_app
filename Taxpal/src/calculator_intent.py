CALCULATION_KEYWORDS = (
    "calculate",
    "calculation",
    "compute",
    "work out",
    "workout",
    "how much",
    "what is the total",
)

TAX_CALCULATION_KEYWORDS = (
    "vat",
    "tax",
    "payable",
    "withholding",
    "payee",
    "paye",
    "rental income",
)


def is_calculation_request(question: str) -> bool:
    """
    Return True when the user's message appears to request
    a numerical calculation.
    """
    normalized = " ".join(
        question.lower().strip().split()
    )

    has_calculation_language = any(
        keyword in normalized
        for keyword in CALCULATION_KEYWORDS
    )

    has_tax_calculation_language = any(
        keyword in normalized
        for keyword in TAX_CALCULATION_KEYWORDS
    )

    return (
        has_calculation_language
        and has_tax_calculation_language
    )