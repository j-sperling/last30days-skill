import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import schema, signals
from lib.hackernews import parse_hackernews_response


class SignalsV3Tests(unittest.TestCase):
    def test_reddit_engagement_uses_source_specific_formula(self):
        item = schema.SourceItem(
            item_id="r1",
            source="reddit",
            title="Title",
            body="Body",
            url="https://example.com",
            engagement={"score": 99, "num_comments": 20, "upvote_ratio": 0.8},
            metadata={"top_comments": [{"score": 10}]},
        )
        expected = (
            0.50 * math.log1p(99)
            + 0.35 * math.log1p(20)
            + 0.05 * (0.8 * 10.0)
            + 0.10 * math.log1p(10)
        )
        self.assertAlmostEqual(expected, signals.engagement_raw(item))

    def test_polymarket_engagement_uses_market_fields(self):
        item = schema.SourceItem(
            item_id="pm1",
            source="polymarket",
            title="Title",
            body="Body",
            url="https://example.com",
            engagement={"volume": 1000, "liquidity": 250},
        )
        expected = (0.60 * math.log1p(1000)) + (0.40 * math.log1p(250))
        self.assertAlmostEqual(expected, signals.engagement_raw(item))

    def test_grounding_uses_generic_fallback(self):
        item = schema.SourceItem(
            item_id="g1",
            source="grounding",
            title="Title",
            body="Body",
            url="https://example.com",
            engagement={"shares": 10, "reads": 100},
        )
        expected = (math.log1p(10) + math.log1p(100)) / 2
        self.assertAlmostEqual(expected, signals.engagement_raw(item))

    def test_annotate_stream_sorts_by_source_specific_reddit_engagement(self):
        higher = schema.SourceItem(
            item_id="r-high",
            source="reddit",
            title="High signal",
            body="claude code skill",
            url="https://example.com/high",
            published_at="2026-03-15",
            engagement={"score": 120, "num_comments": 40, "upvote_ratio": 0.9},
            metadata={"top_comments": [{"score": 15}]},
        )
        lower = schema.SourceItem(
            item_id="r-low",
            source="reddit",
            title="Lower signal",
            body="claude code skill",
            url="https://example.com/low",
            published_at="2026-03-15",
            engagement={"score": 4, "num_comments": 1, "upvote_ratio": 0.5},
            metadata={"top_comments": [{"score": 1}]},
        )
        ranked = signals.annotate_stream(
            [lower, higher],
            ranking_query="What recent evidence matters for claude code skill?",
            freshness_mode="balanced_recent",
        )
        self.assertEqual(["r-high", "r-low"], [item.item_id for item in ranked])

    def test_local_relevance_dominates_over_high_engagement_noise(self):
        relevant = schema.SourceItem(
            item_id="relevant",
            source="reddit",
            title="Deploy to Fly.io with MCP in 60 seconds",
            body="Deploy to Fly.io guide with concrete steps.",
            url="https://example.com/relevant",
            published_at="2026-03-15",
            engagement={"score": 2, "num_comments": 0, "upvote_ratio": 0.8},
            metadata={"top_comments": []},
        )
        noisy = schema.SourceItem(
            item_id="noisy",
            source="reddit",
            title="BATTLEFIELD 6 GAME UPDATE 1.2.2.0",
            body="Patch notes and gameplay discussion.",
            url="https://example.com/noisy",
            published_at="2026-03-15",
            engagement={"score": 5000, "num_comments": 1200, "upvote_ratio": 0.95},
            metadata={"top_comments": [{"score": 400}]},
        )
        ranked = signals.annotate_stream(
            [noisy, relevant],
            ranking_query="How do I deploy on Fly.io?",
            freshness_mode="evergreen_ok",
        )
        self.assertEqual("relevant", ranked[0].item_id)

    def test_prune_low_relevance_keeps_stronger_matches(self):
        strong = schema.SourceItem(
            item_id="strong",
            source="reddit",
            title="Deploy to Fly.io",
            body="Step-by-step Fly.io deploy guide.",
            url="https://example.com/strong",
            metadata={"local_relevance": 0.3},
        )
        weak = schema.SourceItem(
            item_id="weak",
            source="reddit",
            title="Battlefield update",
            body="Patch notes.",
            url="https://example.com/weak",
            metadata={"local_relevance": 0.0},
        )
        pruned = signals.prune_low_relevance([strong, weak], minimum=0.1)
        self.assertEqual(["strong"], [item.item_id for item in pruned])

    def test_prune_low_relevance_falls_back_when_all_are_weak(self):
        weak = schema.SourceItem(
            item_id="weak",
            source="reddit",
            title="Generic post",
            body="Generic body.",
            url="https://example.com/weak",
            metadata={"local_relevance": 0.02},
        )
        pruned = signals.prune_low_relevance([weak], minimum=0.1)
        self.assertEqual(["weak"], [item.item_id for item in pruned])


    # -- Iteration 1: HN engagement bug --

    def test_hackernews_parse_emits_comments_key(self):
        """parse_hackernews_response must emit 'comments' (not 'num_comments')."""
        response = {
            "hits": [
                {
                    "objectID": "123",
                    "title": "Show HN: Something Cool",
                    "url": "https://example.com",
                    "author": "pg",
                    "points": 150,
                    "num_comments": 45,
                    "created_at_i": 1710720000,
                },
            ],
        }
        items = parse_hackernews_response(response, query="something cool")
        self.assertIn("comments", items[0]["engagement"])
        self.assertNotIn("num_comments", items[0]["engagement"])
        self.assertEqual(items[0]["engagement"]["comments"], 45)

    def test_hackernews_engagement_raw_uses_both_fields(self):
        """engagement_raw for HN must weight both points and comments."""
        item = schema.SourceItem(
            item_id="hn1",
            source="hackernews",
            title="Show HN: Something",
            body="Description",
            url="https://example.com",
            engagement={"points": 150, "comments": 45},
        )
        expected = 0.55 * math.log1p(150) + 0.45 * math.log1p(45)
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(expected, result)
        # Verify comments actually contributed (not just points)
        points_only = 0.55 * math.log1p(150)
        self.assertGreater(result, points_only)

    # -- Iteration 4: Missing engagement formula tests --

    def test_x_engagement_dominant_weight(self):
        """X: likes at 0.55 should dominate over quotes at 0.05."""
        item = schema.SourceItem(
            item_id="x1", source="x", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 100, "reposts": 100, "replies": 100, "quotes": 100},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = (
            0.55 * math.log1p(100)
            + 0.25 * math.log1p(100)
            + 0.15 * math.log1p(100)
            + 0.05 * math.log1p(100)
        )
        self.assertAlmostEqual(expected, result)

    def test_x_engagement_all_zero_returns_none(self):
        item = schema.SourceItem(
            item_id="x2", source="x", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 0, "reposts": 0, "replies": 0, "quotes": 0},
        )
        self.assertIsNone(signals.engagement_raw(item))

    def test_x_engagement_missing_fields(self):
        """Missing fields default to 0, no crash."""
        item = schema.SourceItem(
            item_id="x3", source="x", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 50},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = 0.55 * math.log1p(50)
        self.assertAlmostEqual(expected, result)

    def test_youtube_engagement_dominant_weight(self):
        """YouTube: views at 0.50 should dominate over comments at 0.15."""
        item = schema.SourceItem(
            item_id="yt1", source="youtube", title="T", body="B",
            url="https://example.com",
            engagement={"views": 10000, "likes": 500, "comments": 80},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = (
            0.50 * math.log1p(10000)
            + 0.35 * math.log1p(500)
            + 0.15 * math.log1p(80)
        )
        self.assertAlmostEqual(expected, result)

    def test_youtube_engagement_all_zero_returns_none(self):
        item = schema.SourceItem(
            item_id="yt2", source="youtube", title="T", body="B",
            url="https://example.com",
            engagement={"views": 0, "likes": 0, "comments": 0},
        )
        self.assertIsNone(signals.engagement_raw(item))

    def test_youtube_engagement_missing_fields(self):
        item = schema.SourceItem(
            item_id="yt3", source="youtube", title="T", body="B",
            url="https://example.com",
            engagement={"views": 5000},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = 0.50 * math.log1p(5000)
        self.assertAlmostEqual(expected, result)

    def test_tiktok_engagement_dominant_weight(self):
        item = schema.SourceItem(
            item_id="tt1", source="tiktok", title="T", body="B",
            url="https://example.com",
            engagement={"views": 50000, "likes": 3000, "comments": 200},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = (
            0.50 * math.log1p(50000)
            + 0.30 * math.log1p(3000)
            + 0.20 * math.log1p(200)
        )
        self.assertAlmostEqual(expected, result)

    def test_tiktok_engagement_all_zero_returns_none(self):
        item = schema.SourceItem(
            item_id="tt2", source="tiktok", title="T", body="B",
            url="https://example.com",
            engagement={"views": 0, "likes": 0, "comments": 0},
        )
        self.assertIsNone(signals.engagement_raw(item))

    def test_tiktok_engagement_missing_fields(self):
        item = schema.SourceItem(
            item_id="tt3", source="tiktok", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 1000},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = 0.30 * math.log1p(1000)
        self.assertAlmostEqual(expected, result)

    def test_instagram_engagement_dominant_weight(self):
        item = schema.SourceItem(
            item_id="ig1", source="instagram", title="T", body="B",
            url="https://example.com",
            engagement={"views": 8000, "likes": 1500, "comments": 100},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = (
            0.50 * math.log1p(8000)
            + 0.30 * math.log1p(1500)
            + 0.20 * math.log1p(100)
        )
        self.assertAlmostEqual(expected, result)

    def test_instagram_engagement_all_zero_returns_none(self):
        item = schema.SourceItem(
            item_id="ig2", source="instagram", title="T", body="B",
            url="https://example.com",
            engagement={"views": 0, "likes": 0, "comments": 0},
        )
        self.assertIsNone(signals.engagement_raw(item))

    def test_instagram_engagement_missing_fields(self):
        item = schema.SourceItem(
            item_id="ig3", source="instagram", title="T", body="B",
            url="https://example.com",
            engagement={"comments": 50},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = 0.20 * math.log1p(50)
        self.assertAlmostEqual(expected, result)

    def test_hackernews_engagement_all_zero_returns_none(self):
        item = schema.SourceItem(
            item_id="hn2", source="hackernews", title="T", body="B",
            url="https://example.com",
            engagement={"points": 0, "comments": 0},
        )
        self.assertIsNone(signals.engagement_raw(item))

    def test_hackernews_engagement_missing_fields(self):
        item = schema.SourceItem(
            item_id="hn3", source="hackernews", title="T", body="B",
            url="https://example.com",
            engagement={"points": 75},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = 0.55 * math.log1p(75)
        self.assertAlmostEqual(expected, result)

    def test_bluesky_engagement_dominant_weight(self):
        """Bluesky: likes at 0.40 should dominate over quotes at 0.10."""
        item = schema.SourceItem(
            item_id="bs1", source="bluesky", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 200, "reposts": 50, "replies": 30, "quotes": 10},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = (
            0.40 * math.log1p(200)
            + 0.30 * math.log1p(50)
            + 0.20 * math.log1p(30)
            + 0.10 * math.log1p(10)
        )
        self.assertAlmostEqual(expected, result)

    def test_bluesky_engagement_all_zero_returns_none(self):
        item = schema.SourceItem(
            item_id="bs2", source="bluesky", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 0, "reposts": 0, "replies": 0, "quotes": 0},
        )
        self.assertIsNone(signals.engagement_raw(item))

    def test_bluesky_engagement_missing_fields(self):
        item = schema.SourceItem(
            item_id="bs3", source="bluesky", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 100, "replies": 20},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = 0.40 * math.log1p(100) + 0.20 * math.log1p(20)
        self.assertAlmostEqual(expected, result)

    def test_truthsocial_engagement_dominant_weight(self):
        """Truth Social: likes at 0.45 should dominate over replies at 0.25."""
        item = schema.SourceItem(
            item_id="ts1", source="truthsocial", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 500, "reposts": 100, "replies": 50},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = (
            0.45 * math.log1p(500)
            + 0.30 * math.log1p(100)
            + 0.25 * math.log1p(50)
        )
        self.assertAlmostEqual(expected, result)

    def test_truthsocial_engagement_all_zero_returns_none(self):
        item = schema.SourceItem(
            item_id="ts2", source="truthsocial", title="T", body="B",
            url="https://example.com",
            engagement={"likes": 0, "reposts": 0, "replies": 0},
        )
        self.assertIsNone(signals.engagement_raw(item))

    def test_truthsocial_engagement_missing_fields(self):
        item = schema.SourceItem(
            item_id="ts3", source="truthsocial", title="T", body="B",
            url="https://example.com",
            engagement={"reposts": 80},
        )
        result = signals.engagement_raw(item)
        self.assertIsNotNone(result)
        expected = 0.30 * math.log1p(80)
        self.assertAlmostEqual(expected, result)


if __name__ == "__main__":
    unittest.main()
