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


class TestClusterUncertainty(unittest.TestCase):
    def test_single_source_returns_single_source(self):
        candidates = [make_candidate("c1", "reddit", "Title", "Body", 80)]
        result = cluster._cluster_uncertainty(candidates)
        self.assertEqual("single-source", result)

    def test_multi_source_high_score_returns_none(self):
        candidates = [
            make_candidate("c1", "reddit", "Title", "Body", 80),
            make_candidate("c2", "x", "Title2", "Body2", 70),
        ]
        result = cluster._cluster_uncertainty(candidates)
        self.assertIsNone(result)

    def test_multi_source_low_score_returns_thin_evidence(self):
        candidates = [
            make_candidate("c1", "reddit", "Title", "Body", 30),
            make_candidate("c2", "x", "Title2", "Body2", 40),
        ]
        result = cluster._cluster_uncertainty(candidates)
        self.assertEqual("thin-evidence", result)


if __name__ == "__main__":
    unittest.main()
