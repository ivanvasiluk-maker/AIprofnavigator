import unittest
from unittest.mock import patch

from handlers.career import (
    _download_linkedin_profile_text,
    _linkedin_html_to_text,
    _linkedin_profile_url,
)


class LinkedInResumeTests(unittest.TestCase):
    def test_accepts_only_https_public_profile_links(self):
        self.assertEqual(
            _linkedin_profile_url("Моё CV: https://www.linkedin.com/in/anna-smith-123/?trk=share"),
            "https://www.linkedin.com/in/anna-smith-123/",
        )
        self.assertEqual(_linkedin_profile_url("http://linkedin.com/in/anna"), "")
        self.assertEqual(_linkedin_profile_url("https://evil.example/in/anna"), "")
        self.assertEqual(_linkedin_profile_url("https://linkedin.com/company/openai"), "")
        self.assertEqual(
            _linkedin_profile_url("https://pl.linkedin.com/in/anna-smith"),
            "https://pl.linkedin.com/in/anna-smith",
        )

    def test_extracts_public_profile_metadata(self):
        html = """
        <html><head>
          <meta property="og:title" content="Anna Smith — Product Manager">
          <meta property="og:description" content="Product manager with ten years of experience in fintech and B2B platforms.">
        </head></html>
        """
        result = _linkedin_html_to_text(html, "https://linkedin.com/in/anna")
        self.assertIn("Anna Smith", result)
        self.assertIn("ten years", result)


class LinkedInDownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_network_errors_are_a_safe_empty_result(self):
        with patch("handlers.career.aiohttp.ClientSession", side_effect=OSError("offline")):
            self.assertEqual(await _download_linkedin_profile_text("https://linkedin.com/in/anna"), "")


if __name__ == "__main__":
    unittest.main()
