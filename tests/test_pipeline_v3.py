import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import pipeline


class PipelineV3Tests(unittest.TestCase):
    def test_mock_pipeline_report(self):
        report = pipeline.run(
            topic="test topic",
            config={
                "GOOGLE_API_KEY": "test",
                "SCRAPECREATORS_API_KEY": "test",
                "XAI_API_KEY": "test",
                "LAST30DAYS_REASONING_PROVIDER": "gemini",
            },
            depth="quick",
            requested_sources=["reddit", "x", "grounding"],
            mock=True,
        )
        self.assertEqual("test topic", report.topic)
        self.assertTrue(report.ranked_candidates)
        self.assertTrue(report.clusters)
        self.assertIn("reddit", report.items_by_source)
        self.assertIn("x", report.items_by_source)
        self.assertEqual("gemini", report.provider_runtime.reasoning_provider)
        self.assertTrue(report.provider_runtime.grounding_model.startswith("gemini-3.1-"))


if __name__ == "__main__":
    unittest.main()
