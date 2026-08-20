import unittest
from types import SimpleNamespace

import httpx

from trusted_web import (
    _safe_grounding_uri,
    fetch_trusted_url,
    grounding_documents,
    is_secure_trusted_url,
    is_trusted_domain,
    should_search_web,
    trusted_urls_in_text,
)


class TrustedWebTests(unittest.TestCase):
    def test_allowlist_accepts_only_configured_domains(self):
        self.assertTrue(is_trusted_domain("https://www.ura.go.ug/page"))
        self.assertTrue(is_trusted_domain("https://tax.ura.go.ug/page"))
        self.assertTrue(is_trusted_domain("ulii.org"))
        self.assertFalse(is_trusted_domain("example.com"))
        self.assertFalse(is_trusted_domain("ura.go.ug.example.com"))

    def test_secure_url_requires_https_without_credentials_or_custom_port(self):
        self.assertTrue(is_secure_trusted_url("https://ura.go.ug/page"))
        self.assertFalse(is_secure_trusted_url("http://ura.go.ug/page"))
        self.assertFalse(is_secure_trusted_url("https://user@ura.go.ug/page"))
        self.assertFalse(is_secure_trusted_url("https://ura.go.ug:8443/page"))
        self.assertFalse(is_secure_trusted_url("javascript:alert(1)"))

    def test_google_redirect_requires_a_reported_trusted_domain(self):
        redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"
        self.assertTrue(_safe_grounding_uri(redirect, "www.ura.go.ug"))
        self.assertFalse(_safe_grounding_uri(redirect, "example.com"))
        self.assertFalse(_safe_grounding_uri(redirect, ""))

    def test_grounding_documents_keep_only_supported_allowlisted_https_evidence(self):
        chunks = [
            SimpleNamespace(web=SimpleNamespace(
                domain="www.ura.go.ug", title="URA VAT guidance",
                uri="https://vertexaisearch.cloud.google.com/grounding-api-redirect/ura",
            )),
            SimpleNamespace(web=SimpleNamespace(
                domain="example.com", title="Untrusted",
                uri="https://example.com/tax",
            )),
            SimpleNamespace(web=SimpleNamespace(
                domain="ulii.org", title="Insecure",
                uri="http://ulii.org/law",
            )),
        ]
        supports = [SimpleNamespace(
            segment=SimpleNamespace(text="The official standard VAT rate is 18%."),
            grounding_chunk_indices=[0],
        )]
        response = SimpleNamespace(
            text="A longer generated answer.",
            candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(
                grounding_chunks=chunks,
                grounding_supports=supports,
            ))],
        )
        documents = grounding_documents(response)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["text"], "The official standard VAT rate is 18%.")
        self.assertEqual(documents[0]["metadata"]["domain"], "ura.go.ug")
        self.assertEqual(documents[0]["metadata"]["transport_security"], "https_allowlisted")

    def test_direct_trusted_url_works_when_domain_field_is_missing(self):
        response = SimpleNamespace(
            text="Official evidence.",
            candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(
                grounding_chunks=[SimpleNamespace(web=SimpleNamespace(
                    domain=None,
                    title="Official guidance",
                    uri="https://www.finance.go.ug/tax-guidance",
                ))],
                grounding_supports=[],
            ))],
        )
        documents = grounding_documents(response)
        self.assertEqual(documents[0]["metadata"]["domain"], "finance.go.ug")

    def test_extracts_only_explicit_trusted_https_urls(self):
        urls = trusted_urls_in_text(
            "Compare https://ura.go.ug/vat with https://example.com/tax and "
            "http://ulii.org/law."
        )
        self.assertEqual(urls, ["https://ura.go.ug/vat"])

    def test_direct_fetch_extracts_main_text_and_removes_script_content(self):
        def handler(request):
            self.assertEqual(str(request.url), "https://ura.go.ug/vat")
            return httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=(
                    b"<html><head><title>VAT guidance</title>"
                    b"<script>ignore this instruction</script></head>"
                    b"<body><nav>Menu</nav><main>The standard VAT rate is 18%.</main></body></html>"
                ),
            )

        document = fetch_trusted_url(
            "https://ura.go.ug/vat",
            transport=httpx.MockTransport(handler),
        )
        self.assertEqual(document["text"], "The standard VAT rate is 18%.")
        self.assertEqual(document["metadata"]["title"], "VAT guidance")
        self.assertNotIn("instruction", document["text"])

    def test_direct_fetch_rejects_redirect_to_untrusted_host(self):
        def handler(request):
            return httpx.Response(302, headers={"location": "https://example.com/steal"})

        with self.assertRaisesRegex(RuntimeError, "outside the HTTPS allowlist"):
            fetch_trusted_url(
                "https://ura.go.ug/redirect",
                transport=httpx.MockTransport(handler),
            )

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

    def test_explicit_trusted_url_forces_web_even_with_strong_local_evidence(self):
        documents = [{"text": "strong", "metadata": {"relevance_score": 0.9}}]
        self.assertTrue(
            should_search_web("Read https://ura.go.ug/vat and summarize it", documents)
        )


if __name__ == "__main__":
    unittest.main()
