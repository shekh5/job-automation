import unittest
import sys
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agentic_apply

class TestVisualAmbiguity(unittest.TestCase):
    def setUp(self):
        self.temp_logs_dir = Path("/Users/bhawanisingh/.openclaw/workspace/memory/ambiguity_logs")
        if self.temp_logs_dir.exists():
            shutil.rmtree(self.temp_logs_dir)

    def tearDown(self):
        if self.temp_logs_dir.exists():
            shutil.rmtree(self.temp_logs_dir)

    def test_query_llm_contains_get_current_screenshot_tool(self):
        # Inspect that tools array has our new visual inspector definition
        with patch("agentic_apply.post") as mock_post:
            mock_post.return_value = {"choices": [{"message": {"content": "ok"}}]}
            agentic_apply.query_llm([], "token")
            data_sent = mock_post.call_args[1]["data"]
            tools = data_sent["tools"]
            
            screenshot_tool = next((t for t in tools if t["function"]["name"] == "get_current_screenshot"), None)
            self.assertIsNotNone(screenshot_tool)
            self.assertEqual(screenshot_tool["type"], "function")
            self.assertIn("reason", screenshot_tool["function"]["parameters"]["required"])

if __name__ == "__main__":
    unittest.main()
