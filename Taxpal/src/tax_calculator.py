import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from tax_rules import DEFAULT_TAX_YEAR, load_tax_rules, rule_metadata


MONEY_PLACES = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _format_ugx(value: Decimal) -> str:
    return f"UGX {value:,.2f}"


def _rule_context(calculation: dict[str, Any]) -> str:
    return (
        f"Tax year **{calculation['tax_year']}**, rule **{calculation['rule_version']}**, "
        f"effective {calculation['effective_from']} to {calculation['effective_to']}; "
        f"verified {calculation['verified_on']}"
    )


def calculate_vat(
    amount: Decimal | str | int | float,
    rate: Decimal | str | int | float | None = None,
    inclusive: bool = False,
    tax_year: str = DEFAULT_TAX_YEAR,
) -> dict[str, Any]:
    """Calculate Ugandan VAT using deterministic decimal arithmetic."""
    try:
        amount_value = Decimal(str(amount).replace(",", ""))
        rules = load_tax_rules(tax_year)
        standard_rate = Decimal(rules["vat"]["standard_rate"])
        rate_value = standard_rate if rate is None else Decimal(str(rate).replace("%", ""))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Amount and VAT rate must be valid numbers.") from exc

    if amount_value < 0:
        raise ValueError("Amount cannot be negative.")
    if rate_value < 0 or rate_value > 100:
        raise ValueError("VAT rate must be between 0% and 100%.")

    if inclusive:
        gross = amount_value
        net = gross * Decimal("100") / (Decimal("100") + rate_value)
        vat = gross - net
    else:
        net = amount_value
        vat = net * rate_value / Decimal("100")
        gross = net + vat

    net = _money(net)
    vat = _money(vat)
    gross = _money(gross)

    result = {
        "kind": "vat",
        "input_amount": str(_money(amount_value)),
        "rate": str(rate_value.normalize()),
        "inclusive": inclusive,
        "net_amount": str(net),
        "vat_amount": str(vat),
        "gross_amount": str(gross),
        "source": rules["sources"]["vat"]["label"] if rate_value == standard_rate else "User-specified rate",
    }
    if rate_value == standard_rate:
        result.update(rule_metadata(rules, "vat"))
    return result


def calculate_percentage_tax(
    amount: Decimal | str | int | float,
    rate: Decimal | str | int | float,
    label: str = "Custom percentage tax",
) -> dict[str, Any]:
    """Calculate a user-specified percentage without assuming how tax is settled."""
    result = calculate_vat(amount, rate=rate, inclusive=False)
    return {
        "kind": "percentage",
        "label": label.strip() or "Custom percentage tax",
        "input_amount": result["input_amount"],
        "rate": result["rate"],
        "tax_amount": result["vat_amount"],
        "source": "User-specified rate",
    }


def _decimal(value: Decimal | str | int | float, name: str) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a valid number.") from exc
    if result < 0:
        raise ValueError(f"{name} cannot be negative.")
    return result


def _individual_income_tax(income: Decimal, resident: bool, annual: bool, rules: dict) -> Decimal:
    scale = Decimal("12") if annual else Decimal("1")
    schedule = rules["individual_income_monthly"]["resident" if resident else "non_resident"]
    thresholds = [Decimal(value) * scale for value in schedule["thresholds"]]
    rates = [Decimal(value) / Decimal("100") for value in schedule["rates"]]
    bases = [Decimal(value) * scale for value in schedule["bases"]]
    low, middle, upper, surcharge = thresholds
    if resident and income <= low:
        tax = Decimal("0")
    elif income <= middle:
        tax = bases[1] + (income - low) * rates[1]
    elif income <= upper:
        tax = bases[2] + (income - middle) * rates[2]
    else:
        tax = bases[3] + (income - upper) * rates[3]
    if income > surcharge:
        tax += (income - surcharge) * Decimal(schedule["surcharge_rate"]) / Decimal("100")
    return _money(tax)


def calculate_paye(monthly_chargeable_income, resident: bool = True, tax_year: str = DEFAULT_TAX_YEAR) -> dict[str, Any]:
    rules = load_tax_rules(tax_year)
    income = _decimal(monthly_chargeable_income, "Monthly chargeable income")
    tax = _individual_income_tax(income, resident, annual=False, rules=rules)
    return {
        "kind": "paye", "input_amount": str(_money(income)),
        "tax_amount": str(tax), "net_amount": str(_money(income - tax)),
        "resident": resident, "period": "monthly", **rule_metadata(rules, "paye"),
    }


def calculate_individual_business_income(annual_chargeable_income, resident: bool = True, tax_year: str = DEFAULT_TAX_YEAR) -> dict[str, Any]:
    rules = load_tax_rules(tax_year)
    income = _decimal(annual_chargeable_income, "Annual chargeable income")
    tax = _individual_income_tax(income, resident, annual=True, rules=rules)
    return {
        "kind": "business_income", "input_amount": str(_money(income)),
        "tax_amount": str(tax), "net_amount": str(_money(income - tax)),
        "resident": resident, "period": "annual", **rule_metadata(rules, "income"),
    }


def calculate_rental_income(gross_rent, taxpayer_type: str = "resident individual", expenses=0, tax_year: str = DEFAULT_TAX_YEAR) -> dict[str, Any]:
    rules = load_tax_rules(tax_year)
    rental_rules = rules["rental"]
    gross = _decimal(gross_rent, "Annual gross rent")
    taxpayer = taxpayer_type.lower().strip()
    claimed = _decimal(expenses, "Allowable expenses")
    if taxpayer == "resident individual":
        chargeable = max(Decimal("0"), gross - Decimal(rental_rules["resident_individual_threshold"]))
        rate = Decimal(rental_rules["resident_individual_rate"])
        tax = chargeable * rate / Decimal("100")
        allowed = Decimal("0")
    elif taxpayer == "non-resident individual":
        chargeable = gross
        rate = Decimal(rental_rules["non_resident_individual_rate"])
        tax = gross * rate / Decimal("100")
        allowed = Decimal("0")
    elif taxpayer == "company":
        allowed = min(claimed, gross * Decimal(rental_rules["company_expense_cap_percent"]) / Decimal("100"))
        chargeable = gross - allowed
        rate = Decimal(rental_rules["company_rate"])
        tax = chargeable * rate / Decimal("100")
    else:
        raise ValueError("Taxpayer type must be resident individual, non-resident individual, or company.")
    return {
        "kind": "rental", "input_amount": str(_money(gross)),
        "tax_amount": str(_money(tax)), "chargeable_income": str(_money(chargeable)),
        "allowed_expenses": str(_money(allowed)), "rate": str(rate),
        "taxpayer_type": taxpayer, "period": "annual", **rule_metadata(rules, "rental"),
    }


def calculate_corporate_income_tax(annual_chargeable_income, tax_year: str = DEFAULT_TAX_YEAR) -> dict[str, Any]:
    rules = load_tax_rules(tax_year)
    income = _decimal(annual_chargeable_income, "Annual chargeable income")
    rate = Decimal(rules["corporate"]["rate"])
    tax = _money(income * rate / Decimal("100"))
    return {
        "kind": "corporate", "input_amount": str(_money(income)),
        "tax_amount": str(tax), "net_amount": str(_money(income - tax)),
        "rate": str(rate), "period": "annual", **rule_metadata(rules, "income"),
    }


def calculate_withholding_tax(gross_payment, category: str, tax_year: str = DEFAULT_TAX_YEAR) -> dict[str, Any]:
    rules = load_tax_rules(tax_year)
    amount = _decimal(gross_payment, "Gross payment")
    key = category.lower().strip()
    category_rules = rules["withholding"].get(key)
    if not category_rules:
        raise ValueError("Unsupported withholding category; choose one of the verified categories.")
    minimum = category_rules.get("minimum_exclusive")
    if minimum is not None and amount <= Decimal(minimum):
        raise ValueError("This selected 6% withholding category applies only when the payment exceeds UGX 1,000,000.")
    rate = Decimal(category_rules["rate"])
    tax = _money(amount * rate / Decimal("100"))
    return {
        "kind": "withholding", "input_amount": str(_money(amount)),
        "tax_amount": str(tax), "net_amount": str(_money(amount - tax)),
        "rate": str(rate), "category": key, **rule_metadata(rules, category_rules["source"]),
    }


def parse_vat_request(message: str) -> dict[str, Any] | None:
    """Parse common conversational VAT calculations; return None if unrelated."""
    normalized = " ".join(message.lower().split())
    if "vat" not in normalized:
        return None

    if any(phrase in normalized for phrase in ("standard vat rate", "what is the vat rate", "current vat rate")):
        rules = load_tax_rules(_tax_year_from_message(normalized))
        return {
            "kind": "vat_rate_fact",
            "rate": rules["vat"]["standard_rate"],
            **rule_metadata(rules, "vat"),
        }

    calculation_terms = (
        "calculate",
        "compute",
        "how much",
        "vat on",
        "vat component",
        "inclusive",
        "exclusive",
        "including vat",
        "excluding vat",
    )
    if not any(term in normalized for term in calculation_terms):
        return None

    rate_match = re.search(r"(?:at\s+)?(\d+(?:\.\d+)?)\s*%", normalized)
    rate = Decimal(rate_match.group(1)) if rate_match else None

    amount_candidates = []
    for match in re.finditer(
        r"(?:(?:ugx|shs?|ushs?)\s*)?(\d[\d,]*(?:\.\d+)?)",
        normalized,
    ):
        raw = match.group(1)
        if rate_match and match.start(1) == rate_match.start(1):
            continue
        try:
            value = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            continue
        amount_candidates.append(value)

    if not amount_candidates:
        raise ValueError(
            "I found a VAT calculation request but no amount. "
            "Try: 'Calculate VAT on UGX 1,000,000'."
        )

    inclusive = any(
        term in normalized
        for term in ("inclusive", "including vat", "includes vat", "vat included")
    )
    return calculate_vat(
        amount_candidates[0], rate=rate, inclusive=inclusive,
        tax_year=_tax_year_from_message(normalized),
    )


def parse_percentage_tax_request(message: str) -> dict[str, Any] | None:
    normalized = " ".join(message.lower().split())
    if "vat" in normalized:
        return None
    if "tax" not in normalized and "withholding" not in normalized:
        return None
    if not any(term in normalized for term in ("calculate", "compute", "how much")):
        return None

    rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%", normalized)
    if not rate_match:
        raise ValueError(
            "Please provide the flat percentage to use. TaxPal will not guess "
            "a statutory tax rate."
        )

    amount_matches = list(
        re.finditer(
            r"(?:(?:ugx|shs?|ushs?)\s*)?(\d[\d,]*(?:\.\d+)?)",
            normalized,
        )
    )
    amount = None
    for match in amount_matches:
        if match.start(1) == rate_match.start(1):
            continue
        amount = Decimal(match.group(1).replace(",", ""))
        break
    if amount is None:
        raise ValueError("Please provide the amount on which to apply the tax rate.")

    label_match = re.search(
        r"(?:calculate|compute)\s+(?:\d+(?:\.\d+)?%\s+)?(.+?)\s+(?:on|for)\s+",
        normalized,
    )
    label = label_match.group(1).strip().title() if label_match else "Custom tax"
    return calculate_percentage_tax(amount, rate_match.group(1), label=label)


def _ugx_values(message: str) -> list[Decimal]:
    return [
        Decimal(value.replace(",", ""))
        for value in re.findall(r"(?:ugx|shs?|ushs?)\s*(\d[\d,]*(?:\.\d+)?)", message.lower())
    ]


def _tax_year_from_message(message: str) -> str:
    match = re.search(r"(?:tax year|fy)\s*(20\d{2})\s*[/\-]\s*(\d{2,4})", message.lower())
    if not match:
        return DEFAULT_TAX_YEAR
    start, end = match.groups()
    if len(end) == 4:
        end = end[-2:]
    return f"{start}/{end}"


def parse_statutory_tax_request(message: str) -> dict[str, Any] | None:
    normalized = " ".join(message.lower().split())
    if not any(term in normalized for term in ("calculate", "compute", "how much")):
        return None
    amounts = _ugx_values(normalized)
    tax_year = _tax_year_from_message(normalized)

    if "paye" in normalized:
        if not amounts:
            raise ValueError("Please provide the monthly chargeable income for PAYE.")
        resident = "non-resident" not in normalized and "nonresident" not in normalized
        return calculate_paye(amounts[0], resident=resident, tax_year=tax_year)

    if "business income tax" in normalized and "individual" in normalized:
        if not amounts:
            raise ValueError("Please provide the annual chargeable business income.")
        resident = "non-resident" not in normalized and "nonresident" not in normalized
        return calculate_individual_business_income(amounts[0], resident=resident, tax_year=tax_year)

    if "rental income tax" in normalized:
        if not amounts:
            raise ValueError("Please provide the annual gross rental income.")
        if "non-resident" in normalized or "nonresident" in normalized:
            taxpayer = "non-resident individual"
        elif "company" in normalized:
            taxpayer = "company"
        else:
            taxpayer = "resident individual"
        expenses = amounts[1] if len(amounts) > 1 else Decimal("0")
        return calculate_rental_income(amounts[0], taxpayer, expenses, tax_year=tax_year)

    if "corporate income tax" in normalized:
        if not amounts:
            raise ValueError("Please provide the company's annual chargeable income.")
        return calculate_corporate_income_tax(amounts[0], tax_year=tax_year)

    if "withholding tax for" in normalized:
        if not amounts:
            raise ValueError("Please provide the gross payment for withholding tax.")
        category = normalized.split("withholding tax for", 1)[1].split(" on gross payment", 1)[0].strip()
        return calculate_withholding_tax(amounts[-1], category, tax_year=tax_year)
    return None


def parse_tax_request(message: str) -> dict[str, Any] | None:
    return (
        parse_vat_request(message)
        or parse_statutory_tax_request(message)
        or parse_percentage_tax_request(message)
    )


def format_vat_answer(calculation: dict[str, Any]) -> str:
    rate = calculation["rate"]
    net = _format_ugx(Decimal(calculation["net_amount"]))
    vat = _format_ugx(Decimal(calculation["vat_amount"]))
    gross = _format_ugx(Decimal(calculation["gross_amount"]))

    if calculation["inclusive"]:
        explanation = (
            f"The VAT-inclusive amount is **{gross}**. At **{rate}%**, "
            f"the VAT component is **{vat}**, leaving a net amount of **{net}**.\n\n"
            f"Calculation: `{gross} × {rate} ÷ (100 + {rate}) = {vat}`"
        )
    else:
        explanation = (
            f"For a VAT-exclusive amount of **{net}** at **{rate}%**, "
            f"VAT is **{vat}** and the VAT-inclusive total is **{gross}**.\n\n"
            f"Calculation: `{net} × {rate}% = {vat}`"
        )

    return (
        f"{explanation}\n\n"
        f"**Rate basis:** "
        + (f"[{calculation['source']}]({calculation['source_url']}).\n\n" if calculation.get("source_url") else f"{calculation['source']}.\n\n")
        + (f"**Rule set:** {_rule_context(calculation)}.\n\n" if calculation.get("rule_version") else "")
        +
        "This calculation is general information, not professional tax advice."
    )


def format_tax_answer(calculation: dict[str, Any]) -> str:
    if calculation["kind"] == "vat_rate_fact":
        return (
            f"The standard VAT rate in Uganda is **{calculation['rate']}%** for tax year "
            f"**{calculation['tax_year']}**.\n\n"
            f"**Rule basis:** [{calculation['source']}]({calculation['source_url']}); "
            f"{_rule_context(calculation)}.\n\n"
            "This states the standard rate only; a supply may be exempt, zero-rated, or subject to special treatment."
        )
    if calculation["kind"] == "vat":
        return format_vat_answer(calculation)

    kind = calculation["kind"]
    if kind in {"paye", "business_income"}:
        label = "monthly PAYE" if kind == "paye" else "annual individual business income tax"
        status = "resident" if calculation["resident"] else "non-resident"
        amount = _format_ugx(Decimal(calculation["input_amount"]))
        tax = _format_ugx(Decimal(calculation["tax_amount"]))
        net = _format_ugx(Decimal(calculation["net_amount"]))
        return (
            f"For a **{status}** taxpayer with chargeable income of **{amount}**, "
            f"the estimated {label} is **{tax}**, leaving **{net}** after this tax.\n\n"
            f"**Rule basis:** [{calculation['source']}]({calculation['source_url']}); {_rule_context(calculation)}. "
            "Confirm that the amount entered is "
            "chargeable income after any legally permitted treatment."
        )
    if kind == "rental":
        gross = _format_ugx(Decimal(calculation["input_amount"]))
        chargeable = _format_ugx(Decimal(calculation["chargeable_income"]))
        tax = _format_ugx(Decimal(calculation["tax_amount"]))
        return (
            f"For a **{calculation['taxpayer_type']}** with annual gross rent of **{gross}**, "
            f"chargeable rental income is **{chargeable}** and estimated rental tax at "
            f"**{calculation['rate']}%** is **{tax}**.\n\n"
            f"**Rule basis:** [{calculation['source']}]({calculation['source_url']}); {_rule_context(calculation)}. "
            "Company expenses are capped at 50% "
            "of gross rent and remain subject to URA verification."
        )
    if kind in {"corporate", "withholding"}:
        amount = _format_ugx(Decimal(calculation["input_amount"]))
        tax = _format_ugx(Decimal(calculation["tax_amount"]))
        net = _format_ugx(Decimal(calculation["net_amount"]))
        label = "corporate income tax" if kind == "corporate" else "withholding tax"
        qualifier = "" if kind == "corporate" else f" for **{calculation['category']}**"
        caveat = (
            "Confirm chargeable income and any applicable incentives with URA."
            if kind == "corporate"
            else "Withholding exemptions, tax treaties, and transaction-specific rules can change the final liability."
        )
        return (
            f"On **{amount}**, estimated {label}{qualifier} at **{calculation['rate']}%** "
            f"is **{tax}**, leaving **{net}** after tax.\n\n"
            f"**Rule basis:** [{calculation['source']}]({calculation['source_url']}); "
            f"{_rule_context(calculation)}. {caveat}"
        )

    amount = _format_ugx(Decimal(calculation["input_amount"]))
    tax = _format_ugx(Decimal(calculation["tax_amount"]))
    rate = calculation["rate"]
    return (
        f"Using your supplied **{rate}%** rate for **{calculation['label']}**, "
        f"the calculated tax on **{amount}** is **{tax}**.\n\n"
        f"Calculation: `{amount} x {rate}% = {tax}`\n\n"
        "**Rate basis:** User-specified. TaxPal has not verified that this rate "
        "applies to your transaction. It also does not assume whether the tax is added, "
        "withheld, or deducted. This is general information, not professional tax advice."
    )
