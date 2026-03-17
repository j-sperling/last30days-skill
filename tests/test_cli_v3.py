import json
import tempfile
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import last30days as cli
from lib import schema


class CliV3Tests(unittest.TestCase):
    def make_report(self) -> schema.Report:
        return schema.Report(
            topic="OpenClaw vs NanoClaw",
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
                intent="comparison",
                freshness_mode="balanced_recent",
                cluster_mode="debate",
                raw_topic="OpenClaw vs NanoClaw",
                subqueries=[
                    schema.SubQuery(
                        label="primary",
                        search_query="openclaw vs nanoclaw",
                        ranking_query="How does OpenClaw compare to NanoClaw?",
                        sources=["grounding"],
                    )
                ],
                source_weights={"grounding": 1.0},
            ),
            clusters=[],
            ranked_candidates=[],
            items_by_source={"grounding": []},
            errors_by_source={},
        )

    def test_mock_json_cli(self):
        result = subprocess.run(
            [sys.executable, "scripts/last30days.py", "test topic", "--mock", "--emit=json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("query_plan", payload)
        self.assertIn("ranked_candidates", payload)
        self.assertIn("clusters", payload)

    def test_parse_search_flag_normalizes_aliases_and_dedupes(self):
        self.assertEqual(
            ["grounding", "reddit", "hackernews"],
            cli.parse_search_flag("web, reddit, hn, web"),
        )

    def test_parse_search_flag_rejects_invalid_or_empty_inputs(self):
        with self.assertRaises(SystemExit):
            cli.parse_search_flag("unknown")
        with self.assertRaises(SystemExit):
            cli.parse_search_flag(" , ")

    def test_slugify_and_emit_output_cover_supported_modes(self):
        report = self.make_report()
        self.assertEqual("openclaw-vs-nanoclaw", cli.slugify(report.topic))

        compact = cli.emit_output(report, "compact")
        json_output = cli.emit_output(report, "json")
        context = cli.emit_output(report, "context")

        self.assertIn("# last30days v3.0.0", compact)
        self.assertIn('"topic": "OpenClaw vs NanoClaw"', json_output)
        self.assertIsInstance(context, str)

        with self.assertRaises(SystemExit):
            cli.emit_output(report, "bad-mode")

    def test_save_output_writes_expected_extension(self):
        report = self.make_report()
        with tempfile.TemporaryDirectory() as tmp:
            path = cli.save_output(report, "json", tmp)
            self.assertEqual(".json", path.suffix)
            payload = json.loads(path.read_text())
            self.assertEqual("OpenClaw vs NanoClaw", payload["topic"])

    def test_persist_report_updates_run_status_on_success_and_failure(self):
        report = self.make_report()

        success_store = types.SimpleNamespace(
            init_db=mock.Mock(),
            add_topic=mock.Mock(return_value={"id": 7}),
            record_run=mock.Mock(return_value=11),
            findings_from_report=mock.Mock(return_value=[{"title": "x"}]),
            store_findings=mock.Mock(return_value={"new": 2, "updated": 1}),
            update_run=mock.Mock(),
        )
        with mock.patch.dict(sys.modules, {"store": success_store}):
            counts = cli.persist_report(report)
        self.assertEqual({"new": 2, "updated": 1}, counts)
        success_store.update_run.assert_called_once_with(
            11,
            status="completed",
            findings_new=2,
            findings_updated=1,
        )

        failure_store = types.SimpleNamespace(
            init_db=mock.Mock(),
            add_topic=mock.Mock(return_value={"id": 7}),
            record_run=mock.Mock(return_value=12),
            findings_from_report=mock.Mock(side_effect=RuntimeError("boom")),
            store_findings=mock.Mock(),
            update_run=mock.Mock(),
        )
        with mock.patch.dict(sys.modules, {"store": failure_store}):
            with self.assertRaises(RuntimeError):
                cli.persist_report(report)
        failure_store.update_run.assert_called_once()
        _, kwargs = failure_store.update_run.call_args
        self.assertEqual("failed", kwargs["status"])
        self.assertIn("boom", kwargs["error_message"])


if __name__ == "__main__":
    unittest.main()
