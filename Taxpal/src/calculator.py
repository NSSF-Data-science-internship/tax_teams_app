from decimal import Decimal, InvalidOperation


def calculate_percentage(amount: float, percentage: float) -> float:
    """
    Calculate a percentage of an amount.

    Example:
        calculate_percentage(1_000_000, 18)
        -> 180_000
    """
    try:
        amount_decimal = Decimal(str(amount))
        percentage_decimal = Decimal(str(percentage))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Amount and percentage must be valid numbers.") from exc

    if amount_decimal < 0:
        raise ValueError("Amount cannot be negative.")

    if percentage_decimal < 0:
        raise ValueError("Percentage cannot be negative.")

    result = amount_decimal * percentage_decimal / Decimal("100")

    return float(result)


def calculate_total_with_percentage(
    amount: float,
    percentage: float,
) -> tuple[float, float]:
    """
    Calculate both the percentage amount and the total including it.

    Example:
        amount = 1,000,000
        percentage = 18

        percentage amount = 180,000
        total = 1,180,000
    """
    percentage_amount = calculate_percentage(
        amount,
        percentage,
    )

    total = float(
        Decimal(str(amount)) + Decimal(str(percentage_amount))
    )

    return percentage_amount, total