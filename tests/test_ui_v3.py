# ruff: noqa: E402
import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import ui


class UiV3Tests(unittest.TestCase):
    def test_show_diagnostic_banner_uses_v3_source_model(self):
        diag = {
            "available_sources": ["grounding", "youtube"],
            "providers": {"google": True, "openai": False, "xai": False},
            "x_backend": None,
            "bird_installed": True,
            "bird_authenticated": False,
            "bird_username": None,
            "native_web_backend": "brave",
        }
        with mock.patch.object(ui, "IS_TTY", False):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                ui.show_diagnostic_banner(diag)
        output = stderr.getvalue()
        self.assertIn("No SCRAPECREATORS_API_KEY", output)
        self.assertIn("Add AUTH_TOKEN/CT0 or XAI_API_KEY", output)
        self.assertIn("brave API available", output)

    def test_build_nux_message_mentions_v3_unlock_paths(self):
        text = ui._build_nux_message(
            {"available_sources": ["reddit", "youtube", "grounding"]}
        )
        self.assertIn("Reddit ✓, X ✗, YouTube ✓, Web ✓", text)
        self.assertIn("SCRAPECREATORS_API_KEY", text)
        self.assertIn("Brave or Serper", text)


if __name__ == "__main__":
    unittest.main()
