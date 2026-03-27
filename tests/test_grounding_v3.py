import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import grounding


class BraveSearchTests(unittest.TestCase):
    def test_brave_search_applies_freshness_and_filters_to_in_range_dated_items(self):
        mock_response = {
            "web": {
                "results": [
                    {
                        "title": "Test Article",
                        "url": "https://example.com/article",
                        "description": "A test snippet",
                        "page_age": "2026-03-10T00:00:00",
                    },
                    {
                        "title": "Old Article",
                        "url": "https://example.com/old",
                        "description": "Should be filtered",
                        "page_age": "2025-12-10T00:00:00",
                    },
                    {
                        "title": "Undated Article",
                        "url": "https://example.com/undated",
                        "description": "Should also be filtered",
                    }
                ]
            }
        }
        with patch("lib.grounding.urllib.request.urlopen") as mock_urlopen:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_ctx.read.return_value = json.dumps(mock_response).encode()
            mock_urlopen.return_value = mock_ctx

            items, artifact = grounding.brave_search("test", ("2026-02-25", "2026-03-27"), "fake-key")
            self.assertEqual(1, len(items))
            self.assertEqual("Test Article", items[0]["title"])
            self.assertEqual("https://example.com/article", items[0]["url"])
            self.assertEqual("2026-03-10", items[0]["date"])
            self.assertEqual("brave", artifact["label"])
            request = mock_urlopen.call_args.args[0]
            self.assertIn("freshness=2026-02-25to2026-03-27", request.full_url)


class SerperSearchTests(unittest.TestCase):
    def test_serper_search_filters_to_in_range_dated_items(self):
        mock_response = {
            "organic": [
                {
                    "title": "Serper Result",
                    "link": "https://example.com/serper",
                    "snippet": "A serper snippet",
                    "date": "Mar 15, 2026",
                },
                {
                    "title": "Old Result",
                    "link": "https://example.com/old",
                    "snippet": "Should be filtered",
                    "date": "Jan 15, 2026",
                },
                {
                    "title": "Undated Result",
                    "link": "https://example.com/undated",
                    "snippet": "Should also be filtered",
                }
            ]
        }
        with patch("lib.grounding.urllib.request.urlopen") as mock_urlopen:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_ctx.read.return_value = json.dumps(mock_response).encode()
            mock_urlopen.return_value = mock_ctx

            items, artifact = grounding.serper_search("test", ("2026-02-25", "2026-03-27"), "fake-key")
            self.assertEqual(1, len(items))
            self.assertEqual("Serper Result", items[0]["title"])
            self.assertEqual("2026-03-15", items[0]["date"])
            self.assertEqual("serper", artifact["label"])


class WebSearchDispatchTests(unittest.TestCase):
    def test_auto_selects_brave_when_key_present(self):
        config = {"BRAVE_API_KEY": "test-key"}
        with patch("lib.grounding.brave_search", return_value=([], {})) as mock:
            grounding.web_search("test", ("2026-02-25", "2026-03-27"), config, backend="auto")
            mock.assert_called_once()

    def test_auto_selects_serper_when_only_serper_key(self):
        config = {"SERPER_API_KEY": "test-key"}
        with patch("lib.grounding.serper_search", return_value=([], {})) as mock:
            grounding.web_search("test", ("2026-02-25", "2026-03-27"), config, backend="auto")
            mock.assert_called_once()

    def test_auto_returns_empty_when_no_keys(self):
        items, artifact = grounding.web_search("test", ("2026-02-25", "2026-03-27"), {}, backend="auto")
        self.assertEqual([], items)
        self.assertEqual({}, artifact)

    def test_none_returns_empty(self):
        config = {"BRAVE_API_KEY": "test-key"}
        items, artifact = grounding.web_search("test", ("2026-02-25", "2026-03-27"), config, backend="none")
        self.assertEqual([], items)


if __name__ == "__main__":
    unittest.main()
