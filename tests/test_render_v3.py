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
        published_at="2099-03-15",
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
        published_at="2099-03-14",
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
        range_from="2099-02-14",
        range_to="2099-03-16",
        generated_at="2099-03-16T00:00:00+00:00",
        provider_runtime=schema.ProviderRuntime(
            reasoning_provider="gemini",
            planner_model="gemini-3.1-flash-lite-preview",
            rerank_model="gemini-3.1-flash-lite-preview",
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
    def test_render_compact_reads_like_briefing_not_ranking_dump(self):
        text = render.render_compact(sample_report())
        self.assertIn("# last30days: test topic", text)
        self.assertIn("## What I learned", text)
        self.assertIn("## Stats", text)
        self.assertIn("### Grounded result", text)
        self.assertIn("Top voices:", text)
        self.assertIn("Web: 1 page; domains: example.com", text)
        self.assertIn("Reddit: 1 thread; 344pts, 119cmt; communities: r/LocalLLaMA", text)
        self.assertIn("344pts", text)
        self.assertIn("Also seen in: Web", text)
        self.assertIn("Top comment: This is the strongest user reaction.", text)
        self.assertIn("Insight: Users corroborate the main claim.", text)
        self.assertNotIn("## Ranked Evidence Clusters", text)
        self.assertNotIn("score 90", text)
        self.assertNotIn("score:90", text)
        self.assertNotIn("Uncertainty:", text)
        self.assertNotIn("## Source Status", text)
        self.assertNotIn("## Metadata", text)

    def test_render_context_includes_top_clusters(self):
        text = render.render_context(sample_report())
        self.assertIn("Top clusters:", text)
        self.assertIn("Grounded result", text)

    def test_render_compact_includes_source_errors_in_coverage_notes(self):
        report = sample_report()
        report.errors_by_source = {"x": "HTTP 400: Bad Request"}
        text = render.render_compact(report)
        self.assertIn("## Coverage notes", text)
        self.assertIn("X had an error: HTTP 400: Bad Request", text)

    def test_render_compact_includes_quality_nudge_in_coverage_notes(self):
        quality = {
            "score_pct": 60,
            "core_active": ["hn", "polymarket", "x"],
            "core_missing": ["youtube", "reddit_comments"],
            "core_errored": [],
            "nudge_text": "Research quality: 3/5 core sources.\nMissing: YouTube, Reddit with comments.",
        }
        text = render.render_compact(sample_report(), quality=quality)
        self.assertIn("## Coverage notes", text)
        self.assertIn("Research quality: 3/5 core sources.", text)
        self.assertIn("Missing: YouTube, Reddit with comments.", text)
        self.assertNotIn("## Research Coverage", text)

    def test_render_compact_has_no_coverage_notes_when_clean(self):
        report = sample_report()
        report.items_by_source["grounding"].append(
            schema.SourceItem(
                item_id="i3",
                source="grounding",
                title="Another grounded result",
                body="Second grounded body.",
                url="https://example.org",
                container="example.org",
                published_at="2099-03-13",
                date_confidence="high",
                metadata={},
            )
        )
        text = render.render_compact(report, quality=None)
        self.assertNotIn("## Coverage notes", text)

    def test_render_compact_has_no_coverage_notes_when_quality_is_perfect(self):
        report = sample_report()
        report.items_by_source["grounding"].append(
            schema.SourceItem(
                item_id="i3",
                source="grounding",
                title="Another grounded result",
                body="Second grounded body.",
                url="https://example.org",
                container="example.org",
                published_at="2099-03-13",
                date_confidence="high",
                metadata={},
            )
        )
        quality = {
            "score_pct": 100,
            "core_active": ["hn", "polymarket", "x", "youtube", "reddit_comments"],
            "core_missing": [],
            "core_errored": [],
            "nudge_text": None,
        }
        text = render.render_compact(report, quality=quality)
        self.assertNotIn("## Coverage notes", text)

    def test_render_compact_handles_empty_reports(self):
        report = sample_report()
        report.clusters = []
        report.ranked_candidates = []
        report.items_by_source = {}
        text = render.render_compact(report)
        self.assertIn("I did not find enough usable recent evidence to support a confident answer yet.", text)
        self.assertIn("No usable source metrics were available for this run.", text)
        self.assertIn("## Coverage notes", text)

    def test_render_compact_keeps_transcript_highlights(self):
        report = sample_report()
        youtube_item = schema.SourceItem(
            item_id="yt1",
            source="youtube",
            title="Video result",
            body="Video discussion",
            url="https://youtube.com/watch?v=123",
            author="AI Channel",
            published_at="2099-03-13",
            date_confidence="high",
            metadata={"transcript_highlights": ["This workflow is winning because it stays grounded in user examples."]},
        )
        youtube_candidate = schema.Candidate(
            candidate_id="c2",
            item_id="yt1",
            source="youtube",
            title="Video result",
            url="https://youtube.com/watch?v=123",
            snippet="Video snippet",
            subquery_labels=["primary"],
            native_ranks={"primary:youtube": 1},
            local_relevance=0.8,
            freshness=85,
            engagement=40,
            source_quality=1.0,
            rrf_score=0.01,
            rerank_score=88,
            final_score=84,
            explanation="useful walkthrough",
            sources=["youtube"],
            source_items=[youtube_item],
        )
        report.clusters.append(
            schema.Cluster(
                cluster_id="cluster-2",
                title="Video walkthroughs",
                candidate_ids=["c2"],
                representative_ids=["c2"],
                sources=["youtube"],
                score=84,
            )
        )
        report.ranked_candidates.append(youtube_candidate)
        report.items_by_source["youtube"] = [youtube_item]
        text = render.render_compact(report)
        self.assertIn('Transcript highlight: "This workflow is winning because it stays grounded in user examples."', text)


if __name__ == "__main__":
    unittest.main()
