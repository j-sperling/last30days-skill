import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluate_search_quality as evaluator


class EvaluatorV3Tests(unittest.TestCase):
    def test_build_ranked_items_uses_multi_source_provenance_and_best_date(self):
        report = {
            "ranked_candidates": [
                {
                    "candidate_id": "c1",
                    "item_id": "i1",
                    "source": "grounding",
                    "sources": ["grounding", "reddit"],
                    "title": "Title",
                    "url": "https://example.com",
                    "snippet": "Snippet",
                    "subquery_labels": ["primary"],
                    "native_ranks": {"primary:grounding": 1},
                    "local_relevance": 0.8,
                    "freshness": 90,
                    "engagement": None,
                    "source_quality": 1.0,
                    "rrf_score": 0.02,
                    "final_score": 88.0,
                    "source_items": [
                        {"item_id": "i1", "source": "grounding", "title": "Title", "body": "Body", "url": "https://example.com", "published_at": "2026-03-10"},
                        {"item_id": "i2", "source": "reddit", "title": "Title", "body": "Body", "url": "https://example.com", "published_at": "2026-03-12"},
                    ],
                }
            ]
        }
        items = evaluator.build_ranked_items(report, 10)
        self.assertEqual(["grounding", "reddit"], items[0]["sources"])
        self.assertEqual("grounding, reddit", items[0]["source"])
        self.assertEqual("2026-03-12", items[0]["date"])

        grouped = evaluator.source_sets(report, 10)
        self.assertEqual({"c1"}, grouped["grounding"])
        self.assertEqual({"c1"}, grouped["reddit"])

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
