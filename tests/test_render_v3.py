import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import render, schema


def sample_report() -> schema.Report:
    primary_item = schema.SourceItem(
        item_id="i1",
        source="grounding",
        title="Grounded result",
        body="A grounded body with useful detail.",
        url="https://example.com",
        container="example.com",
        published_at="2026-03-15",
        date_confidence="high",
        snippet="A grounded snippet about the topic.",
        metadata={},
    )
    reddit_item = schema.SourceItem(
        item_id="i2",
        source="reddit",
        title="Grounded result",
        body="Reddit discussion body.",
        url="https://example.com",
        container="LocalLLaMA",
        published_at="2026-03-14",
        date_confidence="high",
        engagement={"score": 344, "num_comments": 119, "upvote_ratio": 0.92},
        metadata={
            "top_comments": [{"excerpt": "This is the strongest user reaction.", "score": 22}],
            "comment_insights": ["Users corroborate the main claim."],
        },
    )
    candidate = schema.Candidate(
        candidate_id="c1",
        item_id="i2",
        source="reddit",
        title="Grounded result",
        url="https://example.com",
        snippet="A grounded snippet about the topic.",
        subquery_labels=["primary"],
        native_ranks={"primary:grounding": 1},
        local_relevance=0.9,
        freshness=90,
        engagement=88,
        source_quality=1.0,
        rrf_score=0.02,
        rerank_score=92,
        final_score=90,
        explanation="high-signal result",
        sources=["reddit", "grounding"],
        source_items=[reddit_item, primary_item],
    )
    cluster = schema.Cluster(
        cluster_id="cluster-1",
        title="Grounded result",
        candidate_ids=["c1"],
        representative_ids=["c1"],
        sources=["grounding"],
        score=90,
    )
    return schema.Report(
        topic="test topic",
        range_from="2026-02-14",
        range_to="2026-03-16",
        generated_at="2026-03-16T00:00:00+00:00",
        provider_runtime=schema.ProviderRuntime(
            reasoning_provider="gemini",
            planner_model="gemini-3.1-flash-lite-preview",
            rerank_model="gemini-3.1-flash-lite-preview",
            grounding_model="gemini-3.1-flash-lite-preview",
        ),
        query_plan=schema.QueryPlan(
            intent="breaking_news",
            freshness_mode="strict_recent",
            cluster_mode="story",
            raw_topic="test topic",
            subqueries=[schema.SubQuery(label="primary", search_query="test topic", ranking_query="What happened with test topic?", sources=["grounding"])],
            source_weights={"grounding": 1.0},
        ),
        clusters=[cluster],
        ranked_candidates=[candidate],
        items_by_source={"grounding": [primary_item], "reddit": [reddit_item]},
        errors_by_source={},
    )


class RenderV3Tests(unittest.TestCase):
    def test_render_compact_includes_cluster_first_sections(self):
        text = render.render_compact(sample_report())
        self.assertIn("# last30days v3.0.0: test topic", text)
        self.assertIn("## Ranked Evidence Clusters", text)
        self.assertIn("[reddit, grounding] Grounded result", text)
        self.assertIn("[344pts, 119cmt]", text)
        self.assertIn("Also on: Grounded Web", text)
        self.assertIn("Top comment: This is the strongest user reaction.", text)
        self.assertIn("Insight: Users corroborate the main claim.", text)
        self.assertIn("## Source Coverage", text)

    def test_render_context_includes_top_clusters(self):
        text = render.render_context(sample_report())
        self.assertIn("Top clusters:", text)
        self.assertIn("Grounded result", text)


if __name__ == "__main__":
    unittest.main()
