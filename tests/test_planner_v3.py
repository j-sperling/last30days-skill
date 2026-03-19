import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import planner


class PlannerV3Tests(unittest.TestCase):
    def test_default_how_to_expands_past_llm_narrow_source_weights(self):
        raw = {
            "intent": "how_to",
            "freshness_mode": "balanced_recent",
            "cluster_mode": "workflow",
            "source_weights": {"grounding": 0.7, "hackernews": 0.3},
            "subqueries": [
                {
                    "label": "primary",
                    "search_query": "deploy app to Fly.io guide",
                    "ranking_query": "How do I deploy an app to Fly.io?",
                    "sources": ["grounding", "hackernews"],
                    "weight": 1.0,
                }
            ],
        }
        plan = planner._sanitize_plan(
            raw,
            "how to deploy on Fly.io",
            ["reddit", "x", "grounding", "youtube", "hackernews"],
            None,
            "default",
        )
        sources = plan.subqueries[0].sources
        # how_to capability routing selects web + video + discussion
        self.assertIn("reddit", sources)
        self.assertIn("grounding", sources)
        self.assertIn("youtube", sources)
        self.assertIn("reddit", plan.source_weights)
        self.assertIn("youtube", plan.source_weights)
        self.assertEqual("evergreen_ok", plan.freshness_mode)

    def test_comparison_uses_deterministic_plan_and_preserves_entities(self):
        plan = planner.plan_query(
            topic="openclaw vs nanoclaw vs ironclaw",
            available_sources=["reddit", "x", "grounding", "youtube", "hackernews", "polymarket"],
            requested_sources=None,
            depth="default",
            provider=object(),
            model="ignored",
        )
        self.assertEqual("comparison", plan.intent)
        self.assertEqual(["deterministic-comparison-plan"], plan.notes)
        self.assertEqual(4, len(plan.subqueries))
        joined_queries = "\n".join(subquery.search_query for subquery in plan.subqueries).lower()
        self.assertIn("openclaw", joined_queries)
        self.assertIn("nanoclaw", joined_queries)
        self.assertIn("ironclaw", joined_queries)

    def test_fallback_plan_emits_dual_query_fields(self):
        plan = planner.plan_query(
            topic="codex vs claude code",
            available_sources=["reddit", "x", "grounding"],
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("comparison", plan.intent)
        self.assertGreaterEqual(len(plan.subqueries), 2)
        for subquery in plan.subqueries:
            self.assertTrue(subquery.search_query)
            self.assertTrue(subquery.ranking_query)

    def test_factual_topic_uses_no_cluster_mode(self):
        plan = planner.plan_query(
            topic="what is the parameter count of claude code",
            available_sources=["grounding", "reddit"],
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("factual", plan.intent)
        self.assertEqual("none", plan.cluster_mode)

    def test_quick_mode_collapses_fallback_to_single_subquery(self):
        plan = planner.plan_query(
            topic="codex vs claude code",
            available_sources=["reddit", "x", "grounding"],
            requested_sources=None,
            depth="quick",
            provider=None,
            model=None,
        )
        self.assertEqual("comparison", plan.intent)
        self.assertEqual(1, len(plan.subqueries))
        self.assertEqual(["reddit", "x"], plan.subqueries[0].sources)

    def test_default_comparison_uses_all_capable_sources(self):
        plan = planner.plan_query(
            topic="codex vs claude code",
            available_sources=["reddit", "x", "grounding", "youtube", "hackernews", "polymarket"],
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("comparison", plan.intent)
        for subquery in plan.subqueries:
            # Default depth should not artificially cap sources
            self.assertGreaterEqual(len(subquery.sources), 5)

    def test_default_how_to_keeps_youtube_in_source_mix(self):
        plan = planner.plan_query(
            topic="how to deploy remotion animations for claude code",
            available_sources=["reddit", "x", "grounding", "youtube", "hackernews"],
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("how_to", plan.intent)
        sources = plan.subqueries[0].sources
        self.assertIn("youtube", sources)
        self.assertIn("reddit", sources)
        self.assertIn("grounding", sources)

    def test_how_to_sources_includes_capability_matched_extras(self):
        """how_to routing should include additional sources beyond the core 3."""
        plan = planner.plan_query(
            topic="how to deploy on Fly.io",
            available_sources=["reddit", "tiktok", "instagram", "grounding", "youtube", "hackernews"],
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("how_to", plan.intent)
        sources = plan.subqueries[0].sources
        # Core sources must be present
        self.assertIn("grounding", sources)
        self.assertIn("youtube", sources)
        self.assertIn("reddit", sources)
        # Additional capability-matched sources should also be included
        self.assertGreater(len(sources), 3,
                           f"how_to should include >3 sources, got {len(sources)}: {sources}")

    def test_ncaa_tournament_is_breaking_news(self):
        intent = planner._infer_intent("NCAA tournament brackets")
        self.assertEqual("breaking_news", intent)

    def test_march_madness_is_breaking_news(self):
        intent = planner._infer_intent("2026 March Madness")
        self.assertEqual("breaking_news", intent)

    def test_factual_plan_has_at_most_2_subqueries(self):
        plan = planner.plan_query(
            topic="who acquired Wiz",
            available_sources=["grounding", "reddit", "x", "hackernews"],
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("factual", plan.intent)
        self.assertLessEqual(len(plan.subqueries), 2)

    def test_default_how_to_prefers_longform_video_over_shortform(self):
        plan = planner.plan_query(
            topic="how to deploy on Fly.io",
            available_sources=["reddit", "tiktok", "instagram", "grounding", "youtube", "hackernees"],
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("how_to", plan.intent)
        sources = plan.subqueries[0].sources
        # how_to routing should include youtube (longform) over tiktok/instagram
        self.assertIn("youtube", sources)
        self.assertIn("reddit", sources)
        self.assertIn("grounding", sources)

    # --- Intent-source exclusion tests ---

    def test_prediction_excludes_tiktok_and_instagram(self):
        all_sources = ["reddit", "x", "grounding", "youtube", "tiktok", "instagram", "hackernews", "polymarket"]
        plan = planner.plan_query(
            topic="will bitcoin reach 200k prediction odds",
            available_sources=all_sources,
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("prediction", plan.intent)
        for subquery in plan.subqueries:
            self.assertNotIn("tiktok", subquery.sources,
                             "tiktok should be excluded from prediction queries")
            self.assertNotIn("instagram", subquery.sources,
                             "instagram should be excluded from prediction queries")

    def test_opinion_excludes_tiktok_and_instagram(self):
        all_sources = ["reddit", "x", "grounding", "youtube", "tiktok", "instagram", "hackernews", "polymarket"]
        plan = planner.plan_query(
            topic="thoughts on the new MacBook Pro worth it",
            available_sources=all_sources,
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("opinion", plan.intent)
        for subquery in plan.subqueries:
            self.assertNotIn("tiktok", subquery.sources,
                             "tiktok should be excluded from opinion queries")
            self.assertNotIn("instagram", subquery.sources,
                             "instagram should be excluded from opinion queries")

    def test_breaking_news_still_includes_tiktok_and_instagram(self):
        all_sources = ["reddit", "x", "grounding", "youtube", "tiktok", "instagram", "hackernews", "polymarket"]
        plan = planner.plan_query(
            topic="latest earthquake news update",
            available_sources=all_sources,
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("breaking_news", plan.intent)
        # breaking_news has no exclusions, so tiktok/instagram should be available
        all_subquery_sources = set()
        for subquery in plan.subqueries:
            all_subquery_sources.update(subquery.sources)
        self.assertIn("tiktok", all_subquery_sources,
                       "tiktok should be included in breaking_news queries")
        self.assertIn("instagram", all_subquery_sources,
                       "instagram should be included in breaking_news queries")

    def test_how_to_still_includes_tiktok_and_instagram(self):
        all_sources = ["reddit", "x", "grounding", "youtube", "tiktok", "instagram", "hackernews"]
        plan = planner.plan_query(
            topic="how to deploy on Fly.io",
            available_sources=all_sources,
            requested_sources=None,
            depth="default",
            provider=None,
            model=None,
        )
        self.assertEqual("how_to", plan.intent)
        # how_to has no exclusions; tiktok/instagram have video capability
        all_subquery_sources = set()
        for subquery in plan.subqueries:
            all_subquery_sources.update(subquery.sources)
        self.assertIn("tiktok", all_subquery_sources,
                       "tiktok should be included in how_to queries")
        self.assertIn("instagram", all_subquery_sources,
                       "instagram should be included in how_to queries")

    def test_exclusion_fallback_if_all_sources_excluded(self):
        """If exclusion would remove all sources, fall back to unfiltered list."""
        sources = planner._default_sources_for_intent("prediction", ["tiktok", "instagram"])
        # Both would be excluded, so fallback returns unfiltered
        self.assertEqual(["tiktok", "instagram"], sources)


if __name__ == "__main__":
    unittest.main()
