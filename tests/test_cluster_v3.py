import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import cluster, schema


def make_candidate(candidate_id: str, source: str, title: str, snippet: str, score: float) -> schema.Candidate:
    return schema.Candidate(
        candidate_id=candidate_id,
        item_id=candidate_id,
        source=source,
        title=title,
        url=f"https://example.com/{candidate_id}",
        snippet=snippet,
        subquery_labels=["primary"],
        native_ranks={"primary:reddit": 1},
        local_relevance=0.8,
        freshness=80,
        engagement=10,
        source_quality=0.7,
        rrf_score=0.02,
        rerank_score=score,
        final_score=score,
    )


class ClusterV3Tests(unittest.TestCase):
    def test_singleton_clusters_for_non_clustered_plan(self):
        plan = schema.QueryPlan(
            intent="how_to",
            freshness_mode="balanced_recent",
            cluster_mode="none",
            raw_topic="docker setup",
            subqueries=[schema.SubQuery(label="primary", search_query="docker setup", ranking_query="How do I set up Docker?", sources=["reddit"])],
            source_weights={"reddit": 1.0},
        )
        candidates = [
            make_candidate("c1", "reddit", "Docker setup guide", "Step by step setup", 80),
            make_candidate("c2", "youtube", "Docker install video", "Video walkthrough", 75),
        ]
        clusters = cluster.cluster_candidates(candidates, plan)
        self.assertEqual(2, len(clusters))
        self.assertEqual(["c1"], clusters[0].representative_ids)
        self.assertEqual(["c2"], clusters[1].representative_ids)

    def test_breaking_news_clusters_related_items(self):
        plan = schema.QueryPlan(
            intent="breaking_news",
            freshness_mode="strict_recent",
            cluster_mode="story",
            raw_topic="model launch",
            subqueries=[schema.SubQuery(label="primary", search_query="model launch", ranking_query="What happened in the model launch?", sources=["reddit", "x"])],
            source_weights={"reddit": 0.5, "x": 0.5},
        )
        candidates = [
            make_candidate("c1", "reddit", "Open model launch reactions", "People are reacting to the open model launch today.", 88),
            make_candidate("c2", "x", "Open model launch update", "People are reacting to the open model launch today on X.", 84),
            make_candidate("c3", "youtube", "Different topic", "A separate discussion about hardware benchmarks.", 70),
        ]
        clusters = cluster.cluster_candidates(candidates, plan)
        self.assertEqual(2, len(clusters))
        self.assertEqual(2, len(clusters[0].candidate_ids))
        self.assertIn("c1", clusters[0].candidate_ids)
        self.assertIn("c2", clusters[0].candidate_ids)


if __name__ == "__main__":
    unittest.main()
