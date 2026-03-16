import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluate_search_quality as evaluator


class EvaluatorV3Tests(unittest.TestCase):
    def test_write_failure_summary_persists_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            evaluator.write_failure_summary(
                output_dir,
                "HEAD~1",
                "HEAD",
                summaries=[{
                    "topic": "test topic",
                    "baseline": {"precision_at_5": 0.5, "ndcg_at_5": 0.6, "source_coverage_recall": 1.0},
                    "candidate": {"precision_at_5": 0.7, "ndcg_at_5": 0.8, "source_coverage_recall": 1.0},
                    "stability": {"overall_jaccard": 0.4, "overall_retention_vs_baseline": 0.9},
                }],
                failures=[{"topic": "broken topic", "error": "timeout"}],
            )
            metrics = json.loads((output_dir / "metrics.json").read_text())
            summary = (output_dir / "summary.md").read_text()
            self.assertEqual(1, len(metrics["failures"]))
            self.assertIn("broken topic", summary)
            self.assertIn("## Failures", summary)


if __name__ == "__main__":
    unittest.main()
