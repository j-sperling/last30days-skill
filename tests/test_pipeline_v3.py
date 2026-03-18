import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import pipeline
from lib import http


class PipelineV3Tests(unittest.TestCase):
    def test_mock_pipeline_report_without_live_credentials(self):
        report = pipeline.run(
            topic="test topic",
            config={"LAST30DAYS_REASONING_PROVIDER": "gemini"},
            depth="quick",
            requested_sources=["reddit", "x", "grounding"],
            mock=True,
        )
        self.assertEqual("test topic", report.topic)
        self.assertTrue(report.ranked_candidates)
        self.assertTrue(report.clusters)
        self.assertIn("x", report.items_by_source)
        self.assertIn("grounding", report.items_by_source)
        self.assertEqual("gemini", report.provider_runtime.reasoning_provider)
        self.assertTrue(report.provider_runtime.grounding_model.startswith("gemini-3.1-"))


class TestSourceFetchCap(unittest.TestCase):
    """X source fetch count must be capped by MAX_SOURCE_FETCHES."""

    def test_x_capped_in_max_source_fetches(self):
        """MAX_SOURCE_FETCHES must cap X at 2 to prevent 429 cascades."""
        self.assertIn("x", pipeline.MAX_SOURCE_FETCHES)
        self.assertEqual(pipeline.MAX_SOURCE_FETCHES["x"], 2)

    def test_cap_logic_limits_source_submissions(self):
        """Verify the cap logic skips submissions beyond the limit."""
        cap = pipeline.MAX_SOURCE_FETCHES.get("x", float("inf"))
        subquery_sources = [
            ["x", "reddit", "youtube"],
            ["x", "reddit", "youtube"],
            ["x", "reddit", "youtube"],
            ["x", "reddit", "youtube"],
        ]
        source_fetch_count: dict[str, int] = {}
        submitted: list[str] = []
        for sources in subquery_sources:
            for source in sources:
                source_cap = pipeline.MAX_SOURCE_FETCHES.get(source)
                if source_cap is not None:
                    current = source_fetch_count.get(source, 0)
                    if current >= source_cap:
                        continue
                    source_fetch_count[source] = current + 1
                submitted.append(source)

        x_count = submitted.count("x")
        reddit_count = submitted.count("reddit")
        self.assertEqual(x_count, 2, f"X should be capped at 2, got {x_count}")
        self.assertEqual(reddit_count, 4, f"Reddit should be uncapped, got {reddit_count}")

    @patch("lib.pipeline._retrieve_stream")
    def test_mock_run_caps_x_fetches(self, mock_retrieve):
        """Pipeline.run in mock mode should call _retrieve_stream for X at most 2 times."""
        mock_retrieve.side_effect = lambda **kwargs: pipeline._mock_stream_results(
            kwargs["source"], kwargs["subquery"]
        )
        report = pipeline.run(
            topic="compare iPhone vs Android vs Pixel vs Samsung",
            config={"LAST30DAYS_REASONING_PROVIDER": "gemini"},
            depth="quick",
            requested_sources=["reddit", "x"],
            mock=True,
        )
        x_calls = [
            call for call in mock_retrieve.call_args_list
            if call.kwargs.get("source") == "x"
        ]
        self.assertLessEqual(
            len(x_calls), 2,
            f"X should be fetched at most 2 times, got {len(x_calls)}",
        )


class TestRateLimitSharing(unittest.TestCase):
    """429 signals should be shared across subqueries."""

    def test_is_rate_limit_error_detects_429_status(self):
        exc = http.HTTPError("HTTP 429: Too Many Requests", status_code=429)
        self.assertTrue(pipeline._is_rate_limit_error(exc))

    def test_is_rate_limit_error_ignores_non_429(self):
        exc = http.HTTPError("HTTP 400: Bad Request", status_code=400)
        self.assertFalse(pipeline._is_rate_limit_error(exc))

    def test_is_rate_limit_error_detects_429_in_string(self):
        exc = RuntimeError("xAI returned 429 rate limit")
        self.assertTrue(pipeline._is_rate_limit_error(exc))

    def test_is_rate_limit_error_rejects_unrelated_error(self):
        exc = RuntimeError("Connection refused")
        self.assertFalse(pipeline._is_rate_limit_error(exc))

    def test_retrieve_stream_skips_rate_limited_source(self):
        """_retrieve_stream should return empty when source is rate-limited."""
        from lib import schema
        rate_limited = {"x"}
        lock = threading.Lock()
        subquery = schema.SubQuery(
            label="test",
            search_query="test query",
            ranking_query="test query",
            sources=["x"],
        )
        items, artifact = pipeline._retrieve_stream(
            topic="test",
            subquery=subquery,
            source="x",
            config={},
            depth="quick",
            date_range=("2026-02-15", "2026-03-17"),
            runtime=schema.ProviderRuntime(
                reasoning_provider="mock",
                planner_model="mock",
                rerank_model="mock",
                grounding_model="mock",
            ),
            grounding_provider=None,
            mock=True,
            rate_limited_sources=rate_limited,
            rate_limit_lock=lock,
        )
        self.assertEqual(items, [])
        self.assertEqual(artifact, {})


if __name__ == "__main__":
    unittest.main()
