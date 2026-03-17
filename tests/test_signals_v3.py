import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import schema, signals


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


if __name__ == "__main__":
    unittest.main()
