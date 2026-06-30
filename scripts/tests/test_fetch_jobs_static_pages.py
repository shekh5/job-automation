import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fetch_jobs_static_pages import fetch_html, crawl_company, load_sources

class TestFetchJobsStaticPages(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_fetch_html_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html>Success</html>"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        html = fetch_html("https://example.com/careers")
        self.assertEqual(html, "<html>Success</html>")

    @patch("urllib.request.urlopen")
    def test_fetch_html_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Network Error")
        
        html = fetch_html("https://example.com/careers")
        self.assertEqual(html, "")

    @patch("fetch_jobs_static_pages.fetch_html")
    def test_crawl_company(self, mock_fetch):
        mock_fetch.return_value = '''
        <!DOCTYPE html>
        <script type="application/ld+json">
        {"@type": "JobPosting", "title": "Developer", "url": "/job/1"}
        </script>
        '''
        
        jobs_count, errs, payload = crawl_company({"company": "Acme", "career_url": "https://acme.com"}, dry_run=False)
        self.assertEqual(jobs_count, 1)
        self.assertEqual(errs, 0)
        self.assertEqual(len(payload["jobs"]), 1)
        
    def test_load_sources(self):
        sources = load_sources()
        self.assertTrue(len(sources) > 0)
        self.assertTrue("company" in sources[0])

if __name__ == "__main__":
    unittest.main()
