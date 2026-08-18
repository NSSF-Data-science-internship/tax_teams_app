import re


ENABLE_PHRASES = (
    "remember my tax profile", "remember my details", "you can remember my details",
    "enable memory", "turn on memory",
)
DELETE_PHRASES = (
    "forget my profile", "forget my details", "delete my profile",
    "clear my profile", "disable memory", "turn off memory", "do not remember me",
)
VIEW_PHRASES = (
    "what do you remember about me", "show my profile", "view my profile",
    "show my remembered details",
)
ALLOWED_TAXES = (
    "paye", "vat", "rental income", "withholding tax",
    "corporate income", "individual business income",
)


def validate_preferences(preferences: dict) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, raw_value in preferences.items():
        value = str(raw_value).strip().lower()
        if not value:
            continue
        if key == "residency" and value in {"resident", "non-resident"}:
            clean[key] = value
        elif key == "taxpayer_type" and value in {"individual", "company"}:
            clean[key] = value
        elif key == "preferred_tax_year" and re.fullmatch(r"20\d{2}/\d{2}", value):
            clean[key] = value
        elif key == "frequent_tax" and value in ALLOWED_TAXES:
            clean[key] = value
        elif key == "business_sector" and re.fullmatch(r"[a-z][a-z &\-/]{1,119}", value):
            clean[key] = value
        else:
            raise ValueError(f"Unsupported remembered profile value for '{key}'.")
    return clean


def memory_command(message: str) -> str | None:
    normalized = " ".join(message.lower().strip().rstrip(".!?").split())
    if any(phrase in normalized for phrase in DELETE_PHRASES):
        return "delete"
    if any(phrase in normalized for phrase in VIEW_PHRASES):
        return "view"
    if any(phrase in normalized for phrase in ENABLE_PHRASES):
        return "enable"
    return None


def extract_explicit_preferences(message: str) -> dict[str, str]:
    """Extract only profile facts stated through narrow, explicit phrases."""
    normalized = " ".join(message.lower().split())
    preferences: dict[str, str] = {}

    residency = re.search(r"\b(?:i am|i'm|my residency is)\s+(?:a\s+)?(non-resident|resident)\b", normalized)
    if residency:
        preferences["residency"] = residency.group(1)

    taxpayer = re.search(r"\bmy taxpayer type is\s+(individual|company)\b", normalized)
    if taxpayer:
        preferences["taxpayer_type"] = taxpayer.group(1)

    tax_year = re.search(r"\bmy preferred tax year is\s+(20\d{2})\s*[/\-]\s*(\d{2,4})\b", normalized)
    if tax_year:
        end = tax_year.group(2)[-2:]
        preferences["preferred_tax_year"] = f"{tax_year.group(1)}/{end}"

    for tax_name in ALLOWED_TAXES:
        if f"i usually calculate {tax_name}" in normalized or f"my frequent tax is {tax_name}" in normalized:
            preferences["frequent_tax"] = tax_name
            break

    sector = re.search(r"\bmy business sector is\s+([a-z][a-z &\-/]{1,60})(?:[.!?]|$)", normalized)
    if sector:
        preferences["business_sector"] = sector.group(1).strip()
    return preferences


def format_profile(preferences: dict[str, str]) -> str:
    if not preferences:
        return "No profile details are currently remembered."
    labels = {
        "residency": "Residency",
        "taxpayer_type": "Taxpayer type",
        "preferred_tax_year": "Preferred tax year",
        "frequent_tax": "Frequent tax",
        "business_sector": "Business sector",
    }
    lines = ["Here is what TaxPal remembers with your consent:"]
    for key in labels:
        if preferences.get(key):
            lines.append(f"- **{labels[key]}:** {preferences[key]}")
    return "\n".join(lines)


def profile_context(preferences: dict[str, str] | None) -> str:
    if not preferences:
        return "No consented user profile is available."
    pairs = ", ".join(f"{key}={value}" for key, value in preferences.items())
    return (
        "User-provided remembered preferences: " + pairs + ". "
        "Use these only to personalize explanations. Do not silently use them to decide "
        "residency, liability, exemptions, or calculator inputs; confirm material facts."
    )
