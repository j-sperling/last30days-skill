import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib.tiktok import _parse_items


class TestTikTokAuthorTypeSafety(unittest.TestCase):
    def _make_raw(self, **overrides):
        base = {
            "aweme_id": "1",
            "desc": "test video",
            "share_url": "https://www.tiktok.com/@u/video/1",
            "author": {"unique_id": "testuser"},
            "statistics": {"play_count": 100, "digg_count": 50, "comment_count": 10, "share_count": 5},
        }
        base.update(overrides)
        return base

    def test_author_as_dict(self):
        items = _parse_items([self._make_raw()], "test")
        self.assertEqual("testuser", items[0]["author_name"])

    def test_author_as_string(self):
        items = _parse_items([self._make_raw(author="stringuser")], "test")
        self.assertEqual("stringuser", items[0]["author_name"])

    def test_author_missing(self):
        raw = self._make_raw()
        del raw["author"]
        items = _parse_items([raw], "test")
        self.assertEqual("", items[0]["author_name"])

    def test_author_none(self):
        items = _parse_items([self._make_raw(author=None)], "test")
        self.assertEqual("", items[0]["author_name"])


class TestTikTokStatsZeroPreserved(unittest.TestCase):
    def test_zero_play_count(self):
        raw = {
            "aweme_id": "1",
            "desc": "test",
            "share_url": "https://www.tiktok.com/@u/video/1",
            "author": {"unique_id": "u"},
            "statistics": {"play_count": 0, "digg_count": 0, "comment_count": 0, "share_count": 0},
        }
        items = _parse_items([raw], "test")
        self.assertEqual(0, items[0]["engagement"]["views"])
        self.assertEqual(0, items[0]["engagement"]["likes"])
        self.assertEqual(0, items[0]["engagement"]["comments"])
        self.assertEqual(0, items[0]["engagement"]["shares"])

    def test_stats_missing(self):
        raw = {
            "aweme_id": "1",
            "desc": "test",
            "share_url": "https://www.tiktok.com/@u/video/1",
            "author": {"unique_id": "u"},
        }
        items = _parse_items([raw], "test")
        self.assertEqual(0, items[0]["engagement"]["views"])

    def test_stats_as_non_dict(self):
        raw = {
            "aweme_id": "1",
            "desc": "test",
            "share_url": "https://www.tiktok.com/@u/video/1",
            "author": {"unique_id": "u"},
            "statistics": "invalid",
        }
        items = _parse_items([raw], "test")
        self.assertEqual(0, items[0]["engagement"]["views"])


if __name__ == "__main__":
    unittest.main()
