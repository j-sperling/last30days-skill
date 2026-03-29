import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib.reddit import (
    _extract_date,
    _extract_score,
    _extract_subreddit_name,
    _normalize_reddit_id,
)


class TestExtractSubredditName(unittest.TestCase):
    def test_from_string(self):
        self.assertEqual("openclaw", _extract_subreddit_name("openclaw"))

    def test_from_dict_with_name(self):
        self.assertEqual(
            "openclaw",
            _extract_subreddit_name({"id": "t5_ghydwa", "name": "openclaw"}),
        )

    def test_from_dict_with_display_name(self):
        self.assertEqual(
            "LocalLLM",
            _extract_subreddit_name({"display_name": "LocalLLM"}),
        )

    def test_from_dict_name_preferred_over_display_name(self):
        self.assertEqual(
            "name_wins",
            _extract_subreddit_name({"name": "name_wins", "display_name": "display"}),
        )

    def test_empty_string(self):
        self.assertEqual("", _extract_subreddit_name(""))

    def test_empty_dict(self):
        self.assertEqual("", _extract_subreddit_name({}))

    def test_strips_whitespace(self):
        self.assertEqual("test", _extract_subreddit_name("  test  "))


class TestExtractScore(unittest.TestCase):
    def test_ups(self):
        self.assertEqual(42, _extract_score({"ups": 42}))

    def test_score_field(self):
        self.assertEqual(77, _extract_score({"score": 77}))

    def test_votes(self):
        self.assertEqual(99, _extract_score({"votes": 99}))

    def test_ups_preferred_over_votes(self):
        self.assertEqual(10, _extract_score({"ups": 10, "votes": 99}))

    def test_missing(self):
        self.assertEqual(0, _extract_score({}))


class TestExtractDate(unittest.TestCase):
    def test_unix_timestamp(self):
        self.assertEqual("2024-05-03", _extract_date({"created_utc": 1714694957}))

    def test_iso_string(self):
        result = _extract_date({"created_at": "2024-05-03T01:09:17.620000+0000"})
        self.assertEqual("2024-05-03", result)

    def test_iso_with_z_suffix(self):
        result = _extract_date({"created_at": "2024-05-03T01:09:17Z"})
        self.assertEqual("2024-05-03", result)

    def test_created_utc_preferred(self):
        result = _extract_date({"created_utc": 1714694957, "created_at": "2025-01-01T00:00:00Z"})
        self.assertEqual("2024-05-03", result)

    def test_missing(self):
        self.assertIsNone(_extract_date({}))


class TestNormalizeRedditId(unittest.TestCase):
    def test_strips_t3_prefix(self):
        self.assertEqual("abc123", _normalize_reddit_id("t3_abc123"))

    def test_no_prefix(self):
        self.assertEqual("abc123", _normalize_reddit_id("abc123"))

    def test_empty(self):
        self.assertEqual("", _normalize_reddit_id(""))

    def test_none(self):
        self.assertEqual("", _normalize_reddit_id(None))


if __name__ == "__main__":
    unittest.main()
