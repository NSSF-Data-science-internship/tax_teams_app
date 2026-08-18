import json
from functools import lru_cache
from pathlib import Path


RULES_DIR = Path(__file__).resolve().parent / "tax_rules"
DEFAULT_TAX_YEAR = "2026/27"


def available_tax_years() -> list[str]:
    years = []
    for path in RULES_DIR.glob("uganda_*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        years.append(data["tax_year"])
    return sorted(years, reverse=True)


@lru_cache(maxsize=8)
def load_tax_rules(tax_year: str = DEFAULT_TAX_YEAR) -> dict:
    normalized = tax_year.strip().replace("-", "/")
    path = RULES_DIR / f"uganda_{normalized.replace('/', '_')}.json"
    if not path.is_file():
        supported = ", ".join(available_tax_years())
        raise ValueError(f"Unsupported tax year '{tax_year}'. Supported years: {supported}.")
    rules = json.loads(path.read_text(encoding="utf-8"))
    required = {"tax_year", "version", "effective_from", "effective_to", "verified_on", "sources", "vat", "individual_income_monthly", "rental", "corporate", "withholding"}
    missing = required.difference(rules)
    if missing:
        raise ValueError(f"Tax rule file {path.name} is missing: {', '.join(sorted(missing))}.")
    if rules["tax_year"] != normalized:
        raise ValueError(f"Tax rule file {path.name} declares the wrong tax year.")
    return rules


def rule_metadata(rules: dict, source_key: str) -> dict:
    source = rules["sources"][source_key]
    return {
        "tax_year": rules["tax_year"],
        "rule_version": rules["version"],
        "effective_from": rules["effective_from"],
        "effective_to": rules["effective_to"],
        "verified_on": rules["verified_on"],
        "source": source["label"],
        "source_url": source["url"],
    }
