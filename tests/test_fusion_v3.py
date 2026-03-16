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


if __name__ == "__main__":
    unittest.main()
