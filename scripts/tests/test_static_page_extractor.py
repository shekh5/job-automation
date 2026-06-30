import unittest
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from static_page_extractor import extract_jobs_from_html

FIXTURES_DIR = Path(__file__).parent / "fixtures"

class TestStaticPageExtractor(unittest.TestCase):
    def read_fixture(self, name: str) -> str:
        with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
            return f.read()

    def test_json_ld_extraction(self):
        html = self.read_fixture("static_career_jsonld.html")
        jobs = extract_jobs_from_html(html, "https://acmecorp.com/careers", "Acme Corp")
        
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Software Engineer, Frontend")
        self.assertEqual(jobs[0]["location"], "San Francisco, CA, US")
        self.assertEqual(jobs[0]["apply_url"], "https://acmecorp.com/careers") # Since json-ld didn't specify url, fallback to base_url

    def test_next_data_extraction(self):
        html = self.read_fixture("static_career_next_data.html")
        jobs = extract_jobs_from_html(html, "https://example.com/careers", "Example")
        
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Backend Engineer")
        self.assertEqual(jobs[0]["location"], "Remote, US")
        self.assertEqual(jobs[0]["apply_url"], "https://careers.example.com/jobs/job-567")

    def test_html_cards_extraction(self):
        html = self.read_fixture("static_career_cards.html")
        jobs = extract_jobs_from_html(html, "https://example.com", "Example")
        
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["title"], "Product Manager")
        self.assertEqual(jobs[0]["location"], "New York, NY")
        self.assertEqual(jobs[0]["apply_url"], "https://example.com/jobs/product-manager")
        
        self.assertEqual(jobs[1]["title"], "Data Scientist")
        self.assertEqual(jobs[1]["location"], "London, UK")
        self.assertEqual(jobs[1]["apply_url"], "https://example.com/jobs/data-scientist")

if __name__ == "__main__":
    unittest.main()
