import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import providers


class ProvidersV3Tests(unittest.TestCase):
    def test_auto_prefers_gemini_with_google_key(self):
        runtime, client = providers.resolve_runtime(
            {"GOOGLE_API_KEY": "test", "LAST30DAYS_REASONING_PROVIDER": "auto"},
            depth="default",
        )
        self.assertEqual("gemini", runtime.reasoning_provider)
        self.assertEqual("gemini", client.name)
        self.assertTrue(runtime.planner_model.startswith("gemini-3.1-"))
        self.assertTrue(runtime.grounding_model.startswith("gemini-3.1-"))

    def test_non_preview_grounding_model_is_rejected(self):
        with self.assertRaises(RuntimeError):
            providers.resolve_runtime(
                {
                    "GOOGLE_API_KEY": "test",
                    "LAST30DAYS_REASONING_PROVIDER": "gemini",
                    "LAST30DAYS_GROUNDING_MODEL": "gemini-2.5-flash",
                },
                depth="default",
            )


if __name__ == "__main__":
    unittest.main()
