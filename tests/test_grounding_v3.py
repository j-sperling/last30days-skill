import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import grounding, normalize


class GroundingV3Tests(unittest.TestCase):
    def test_grounding_artifact_preserves_answer_text(self):
        payload = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Grounded summary text."}]},
                    "groundingMetadata": {
                        "webSearchQueries": ["test topic"],
                        "groundingChunks": [],
                        "groundingSupports": [],
                    },
                }
            ]
        }
        artifact = grounding._artifact_from_payload(payload, "primary")
        self.assertEqual("Grounded summary text.", artifact["answerText"])

    def test_grounding_keeps_dated_and_undated_items(self):
        """Grounding items pass through regardless of date presence, since the
        Gemini API rarely returns dates in grounding chunks."""
        payload = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Grounded summary text."}]},
                    "groundingMetadata": {
                        "groundingChunks": [
                            {"web": {"uri": "https://example.com/2026/03/10/story", "title": "Recent story"}},
                            {"web": {"uri": "https://example.com/no-date", "title": "Undated story"}},
                        ],
                        "groundingSupports": [
                            {"segment": {"text": "Support text"}, "groundingChunkIndices": [0, 1]}
                        ],
                    },
                }
            ]
        }
        items = grounding._items_from_grounding_payload(payload, "primary", ("2026-02-14", "2026-03-16"))
        normalized = normalize.normalize_source_items("grounding", items, "2026-02-14", "2026-03-16")
        self.assertEqual(2, len(normalized))
        self.assertEqual("2026-03-10", normalized[0].published_at)
        self.assertIsNone(normalized[1].published_at)

    def test_grounding_undated_items_pass_through(self):
        """Undated grounding items are kept since Gemini grounding chunks
        rarely carry dates and the API already scopes to recent content."""
        payload = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Published: 2026-03-10. Summary."}]},
                    "groundingMetadata": {
                        "groundingChunks": [
                            {"web": {"uri": "https://example.com/no-date", "title": "Undated story"}},
                        ],
                        "groundingSupports": [],
                    },
                }
            ]
        }
        items = grounding._items_from_grounding_payload(payload, "primary", ("2026-02-14", "2026-03-16"))
        normalized = normalize.normalize_source_items("grounding", items, "2026-02-14", "2026-03-16")
        self.assertEqual(1, len(normalized))
        self.assertIsNone(normalized[0].published_at)


if __name__ == "__main__":
    unittest.main()
