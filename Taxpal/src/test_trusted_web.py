import unittest

from trusted_web import is_trusted_domain, should_search_web


class TrustedWebTests(unittest.TestCase):
    def test_allowlist_accepts_only_configured_domains(self):
        self.assertTrue(is_trusted_domain("https://www.ura.go.ug/page"))
        self.assertTrue(is_trusted_domain("ulii.org"))
        self.assertFalse(is_trusted_domain("example.com"))
        self.assertFalse(is_trusted_domain("ura.go.ug.example.com"))

    def test_current_question_requests_web(self):
        documents = [{"text": "local", "metadata": {}}]
        self.assertTrue(
            should_search_web("What is the latest VAT change?", documents)
        )

    def test_low_relevance_requests_web(self):
        documents = [
            {"text": "weak", "metadata": {"relevance_score": 0.2}},
            {"text": "weak", "metadata": {"relevance_score": 0.3}},
        ]
        self.assertTrue(should_search_web("What is VAT?", documents))

    def test_strong_local_evidence_skips_web(self):
        documents = [
            {"text": "strong", "metadata": {"relevance_score": 0.8}},
        ]
        self.assertFalse(should_search_web("What is VAT?", documents))


if __name__ == "__main__":
    unittest.main()
