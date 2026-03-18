import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import fusion, schema


def make_item(item_id: str, source: str, url: str, title: str, rank_score: float) -> schema.SourceItem:
    return schema.SourceItem(
        item_id=item_id,
        source=source,
        title=title,
        body=title,
        url=url,
        relevance_hint=rank_score,
        snippet=title,
        metadata={
            "local_relevance": rank_score,
            "freshness": 80,
            "engagement_score": 5,
            "source_quality": 0.7,
        },
    )


class FusionV3Tests(unittest.TestCase):
    def test_weighted_rrf_merges_duplicate_urls(self):
        plan = schema.QueryPlan(
            intent="breaking_news",
            freshness_mode="strict_recent",
            cluster_mode="story",
            raw_topic="test",
            subqueries=[
                schema.SubQuery(label="primary", search_query="test", ranking_query="What happened in test?", sources=["reddit", "x"], weight=0.7),
                schema.SubQuery(label="reaction", search_query="test reaction", ranking_query="What are the reactions to test?", sources=["x"], weight=0.3),
            ],
            source_weights={"reddit": 0.4, "x": 0.6},
        )
        shared = "https://example.com/shared"
        streams = {
            ("primary", "reddit"): [make_item("r1", "reddit", shared, "Shared item", 0.8)],
            ("primary", "x"): [make_item("x1", "x", shared, "Shared item", 0.9)],
            ("reaction", "x"): [make_item("x2", "x", "https://example.com/unique", "Unique item", 0.7)],
        }
        candidates = fusion.weighted_rrf(streams, plan, pool_limit=10)
        self.assertEqual(2, len(candidates))
        merged = next(candidate for candidate in candidates if candidate.url == shared)
        self.assertEqual({"primary"}, set(merged.subquery_labels))
        self.assertEqual(2, len(merged.native_ranks))
        self.assertEqual({"reddit", "x"}, set(merged.sources))
        self.assertEqual(2, len(merged.source_items))


    def test_diversify_pool_guarantees_min_per_source(self):
        """Every active source gets at least 2 items in the fused pool.

        Dominant sources (x, tiktok) get high weights, so pure-RRF truncation
        would squeeze out low-weight sources entirely.  The diversity guarantee
        must reserve at least 2 slots per active source.
        """
        sources = ["reddit", "hackernews", "x", "tiktok", "bluesky", "youtube"]
        # Heavily skewed weights: x and tiktok dominate.
        weights = {
            "x": 3.0,
            "tiktok": 2.5,
            "reddit": 0.5,
            "hackernews": 0.4,
            "bluesky": 0.3,
            "youtube": 0.3,
        }
        plan = schema.QueryPlan(
            intent="concept",
            freshness_mode="relaxed",
            cluster_mode="concept",
            raw_topic="RAG",
            subqueries=[
                schema.SubQuery(
                    label="primary",
                    search_query="RAG",
                    ranking_query="What is RAG?",
                    sources=sources,
                    weight=1.0,
                ),
            ],
            source_weights=weights,
        )
        streams: dict[tuple[str, str], list[schema.SourceItem]] = {}
        for src in sources:
            items = []
            for rank in range(4):
                items.append(
                    make_item(
                        item_id=f"{src}_{rank}",
                        source=src,
                        url=f"https://{src}.example.com/{rank}",
                        title=f"{src} item {rank}",
                        rank_score=0.8,
                    )
                )
            streams[("primary", src)] = items

        candidates = fusion.weighted_rrf(streams, plan, pool_limit=12)
        self.assertEqual(12, len(candidates))

        source_counts: dict[str, int] = {}
        for c in candidates:
            source_counts[c.source] = source_counts.get(c.source, 0) + 1

        for src in sources:
            self.assertGreaterEqual(
                source_counts.get(src, 0),
                2,
                f"Source '{src}' has {source_counts.get(src, 0)} items, expected >= 2",
            )


if __name__ == "__main__":
    unittest.main()
