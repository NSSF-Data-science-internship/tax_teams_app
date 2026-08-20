import unittest

from cards import CARD_CONTENT_TYPE, build_taxpal_card, build_taxpal_card_message


class TaxPalCardTests(unittest.TestCase):
    def test_rag_card_prioritizes_answer_and_collapses_source_details(self):
        result = {
            "answer": "VAT is **18%** [S1].\n\n**Sources**\n- [S1] VAT Act",
            "citations": [{
                "id": "S1",
                "title": "Value Added Tax Act",
                "section": "Section 51",
                "publisher": "URA",
                "url": "https://ura.go.ug/vat",
            }],
            "evidence_assessment": {"confidence": "high", "warnings": []},
            "calculation": None,
        }
        card = build_taxpal_card(result)
        rendered = "\n".join(str(item.get("text", "")) for item in card["body"])
        self.assertIn("VAT is **18%**.", rendered)
        self.assertNotIn("[S1]", rendered)
        self.assertNotIn("**Sources**", rendered)
        self.assertNotIn("High confidence", rendered)
        self.assertNotIn("Value Added Tax Act", rendered)

        source_action = card["actions"][0]
        self.assertEqual(source_action["type"], "Action.ShowCard")
        self.assertEqual(source_action["title"], "View sources (1)")
        details = "\n".join(
            str(item.get("text", "")) for item in source_action["card"]["body"]
        )
        self.assertIn("High confidence", details)
        self.assertIn("Value Added Tax Act", details)
        self.assertIn("https://ura.go.ug/vat", details)
        self.assertEqual(card["fallbackText"], "VAT is **18%**.")

    def test_calculation_card_contains_structured_facts(self):
        card = build_taxpal_card({
            "answer": "VAT is UGX 180,000.00.",
            "calculation": {
                "kind": "vat",
                "input_amount": "1000000.00",
                "net_amount": "1000000.00",
                "vat_amount": "180000.00",
                "gross_amount": "1180000.00",
                "rate": "18",
                "tax_year": "2026/27",
                "rule_version": "UG-2026-27-v1",
                "verified_on": "2026-08-16",
            },
            "citations": [],
            "evidence_assessment": {"confidence": "high", "warnings": []},
        })
        fact_sets = [item["facts"] for item in card["body"] if item["type"] == "FactSet"]
        facts = {item["title"]: item["value"] for item in fact_sets[0]}
        self.assertEqual(facts["VAT amount"], "UGX 180,000.00")
        self.assertEqual(facts["Total amount"], "UGX 1,180,000.00")
        self.assertEqual(facts["Tax year"], "2026/27")

    def test_message_uses_current_sdk_attachment_shape(self):
        message = build_taxpal_card_message({"answer": "Hello", "citations": []})
        payload = message.model_dump(by_alias=True, exclude_none=True)
        self.assertEqual(payload["attachments"][0]["contentType"], CARD_CONTENT_TYPE)
        self.assertEqual(payload["attachments"][0]["content"]["type"], "AdaptiveCard")


if __name__ == "__main__":
    unittest.main()
