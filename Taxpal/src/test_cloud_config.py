import os
import unittest
from unittest.mock import patch

from tax_search_client import resolve_tax_search_url


class CloudConfigurationTests(unittest.TestCase):
    def test_explicit_tax_search_url_wins(self):
        with patch.dict(
            os.environ,
            {"TAX_SEARCH_URL": "https://search.example.test/"},
            clear=False,
        ):
            self.assertEqual(
                resolve_tax_search_url(),
                "https://search.example.test",
            )

    def test_internal_service_host_and_port(self):
        with patch.dict(
            os.environ,
            {
                "TAX_SEARCH_URL": "",
                "TAX_SEARCH_HOST": "taxpal-search",
                "TAX_SEARCH_PORT": "8001",
            },
            clear=False,
        ):
            self.assertEqual(
                resolve_tax_search_url(),
                "http://taxpal-search:8001",
            )

    def test_url_without_scheme_gets_http(self):
        with patch.dict(
            os.environ,
            {"TAX_SEARCH_URL": "taxpal-search"},
            clear=False,
        ):
            self.assertEqual(resolve_tax_search_url(), "http://taxpal-search")


if __name__ == "__main__":
    unittest.main()
