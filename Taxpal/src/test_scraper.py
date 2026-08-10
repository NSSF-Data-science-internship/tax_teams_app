import unittest

from scraper import _mark_dead_site, _should_skip_url


class ScraperDeadSiteTests(unittest.TestCase):
    def test_mark_dead_site_skips_host(self):
        _mark_dead_site("https://example.com/blocked-page")
        self.assertTrue(_should_skip_url("https://example.com/anything"))
        self.assertFalse(_should_skip_url("https://other-site.example/ok"))


if __name__ == "__main__":
    unittest.main()
