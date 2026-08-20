import unittest

from evidence import assess_evidence, append_source_register, build_citations


class EvidenceTests(unittest.TestCase):
    def test_builds_stable_structured_citations(self):
        citations = build_citations([
            {"text": "Evidence", "metadata": {
                "title": "Income Tax Act", "section": "Section 5",
                "source": "ULII", "url": "https://ulii.org/example",
                "evidence_type": "local_document", "publication_date": "2025-07-01",
            }}
        ])
        self.assertEqual(citations[0]["id"], "S1")
        self.assertEqual(citations[0]["title"], "Income Tax Act")
        self.assertEqual(citations[0]["publication_date"], "2025-07-01")

    def test_detects_invalid_citation_and_structured_conflict(self):
        citations = [
            {"id": "S1", "evidence_type": "local_document", "publication_date": "2026-01-01", "effective_from": "", "effective_to": "", "accessed_at": "", "claim_key": "vat_rate", "claim_value": "18"},
            {"id": "S2", "evidence_type": "trusted_web", "publication_date": "", "effective_from": "", "effective_to": "", "accessed_at": "2026-08-16", "claim_key": "vat_rate", "claim_value": "16"},
        ]
        result = assess_evidence("VAT is stated as 18% [S1] [S9].", citations)
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["invalid_ids"], ["S9"])
        self.assertEqual(result["conflict_keys"], ["vat_rate"])

    def test_appends_source_register(self):
        citations = [{
            "id": "S1", "title": "URA guide", "section": "PAYE", "publisher": "URA",
            "url": "https://ura.go.ug/guide", "evidence_type": "trusted_web",
            "publication_date": "", "effective_from": "", "effective_to": "",
            "accessed_at": "2026-08-16", "relevance_score": None,
            "claim_key": None, "claim_value": None,
        }]
        assessment = assess_evidence("PAYE applies [S1].", citations)
        answer = append_source_register("PAYE applies [S1].", citations, assessment)
        self.assertIn("**Based on**", answer)
        self.assertNotIn("[S1]", answer)
        self.assertNotIn("PAYE", answer.split("**Based on**", 1)[1])
        self.assertIn("https://ura.go.ug/guide", answer)


if __name__ == "__main__":
    unittest.main()
