import unittest
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from browser_page_extractor import extract_jobs_from_dom

FIXTURES_DIR = Path(__file__).parent / "fixtures"

class TestBrowserPageExtractor(unittest.TestCase):
    def read_fixture(self, name: str) -> str:
        with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
            return f.read()

    def test_extract_rendered_jobs(self):
        # We can reuse static_career_cards.html since the extraction logic for anchor elements is similar
        html = self.read_fixture("static_career_cards.html")
        result = extract_jobs_from_dom(html, "https://example.com", "Example")
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["jobs"]), 2)
        self.assertEqual(result["jobs"][0]["title"], "Product Manager")

    def test_captcha_detection(self):
        html = self.read_fixture("browser_captcha.html")
        result = extract_jobs_from_dom(html, "https://example.com", "Example")
        
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "captcha_detected")
        self.assertEqual(len(result["jobs"]), 0)

    def test_login_wall_detection(self):
        html = """
        <html><body>
        <h1>Employee Portal</h1>
        <p>You must sign in to view this page.</p>
        <input type="text" name="username">
        <input type="password" name="password">
        </body></html>
        """
        result = extract_jobs_from_dom(html, "https://example.com", "Example")
        
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "login_wall_detected")

if __name__ == "__main__":
    unittest.main()
