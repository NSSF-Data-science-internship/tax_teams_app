import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CalculationRequest:
    amount: float
    percentage: float | None
    tax_type: str | None


AMOUNT_PATTERN = re.compile(
    r"""
    (?:
        ugx\s*
    )?
    (
        \d[\d,]*(?:\.\d+)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

PERCENTAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*%",
)


def parse_calculation_request(question: str) -> CalculationRequest:
    percentage_match = PERCENTAGE_PATTERN.search(question)

    amount_matches = AMOUNT_PATTERN.findall(question)

    if not amount_matches:
        raise ValueError("Could not find an amount in the calculation request.")

    # Use the largest numeric-looking amount as the main amount.
    # This avoids treating a tax rate like 18 as the amount.
    amounts = [
        float(value.replace(",", ""))
        for value in amount_matches
    ]

    amount = max(amounts)

    percentage = (
        float(percentage_match.group(1))
        if percentage_match
        else None
    )

    normalized = question.lower()

    tax_type = None

    if "vat" in normalized:
        tax_type = "vat"
    elif "withholding" in normalized:
        tax_type = "withholding"
    elif "payee" in normalized or "paye" in normalized:
        tax_type = "paye"
    elif "rental" in normalized:
        tax_type = "rental_income"
    elif "income tax" in normalized:
        tax_type = "income_tax"

    return CalculationRequest(
        amount=amount,
        percentage=percentage,
        tax_type=tax_type,
    )