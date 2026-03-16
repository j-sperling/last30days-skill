import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import pipeline


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


if __name__ == "__main__":
    unittest.main()
