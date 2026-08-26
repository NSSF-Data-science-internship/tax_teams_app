# User Guide

## Questions and follow-ups

Ask questions in ordinary language:

```text
What is the standard VAT rate in Uganda?
Who must register for VAT?
Explain that in simpler language.
How did the 2026 amendment affect this rule?
```

TaxPal uses recent history to interpret follow-ups. Requests to simplify,
summarize, or give an example can reuse the previous evidence.

## Tax calculations

The dashboard provides forms, while chat accepts typed requests. Supported
categories include VAT, PAYE, rental income, withholding tax, corporate income,
individual business income, and custom percentages.

```text
Calculate VAT on UGX 1,000,000.
Find the VAT component of UGX 590,000 inclusive.
Calculate PAYE on monthly chargeable income of UGX 4,000,000.
Calculate 6% withholding tax on UGX 500,000.
```

Calculations use deterministic decimal arithmetic and identify the financial
year and rule version. Unsupported years are rejected rather than calculated
with the wrong rules.

## Sources and confidence

Evidence-based answers include a readable `Based on` list. The dashboard also
shows evidence metadata, relevance, timing, and confidence diagnostics.
Confidence describes evidence quality; it is not a guarantee of legal accuracy.

Current-information searches are restricted to approved official domains,
including URA, ULII, the Ministry of Finance, Parliament of Uganda, and Bank of
Uganda.

## History and memory

PostgreSQL stores conversation history by owner, channel, and conversation.
Remembered preferences are separate and require explicit opt-in.

Example Teams commands:

```text
Remember my tax profile.
I am a non-resident.
My taxpayer type is company.
My preferred tax year is 2025/26.
Show my profile.
Forget my profile.
```

Preferences personalize explanations only. Facts affecting liability,
residency, exemptions, or calculation inputs should be reconfirmed.

## Voice input

Direct transcription is not part of this prototype. Users can use Teams or
Windows dictation, which converts speech to text before sending it. Voice-note
and live-meeting transcription remain possible future enhancements subject to
privacy, consent, storage, and infrastructure review.

## Responsible use

- Do not enter passwords, API keys, bank credentials, or unnecessary personal
  information.
- Verify important rates, thresholds, and deadlines against current sources.
- Seek professional advice for filings, disputes, or high-impact decisions.
- Report outdated or conflicting sources for knowledge-base review.
