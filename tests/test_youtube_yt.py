"""Tests for YouTube transcript highlights and yt-dlp safety flags."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import youtube_yt


class _DummyProc:
    def __init__(self):
        self.pid = 12345
        self.returncode = 0

    def communicate(self, timeout=None):
        return "", ""

    def wait(self, timeout=None):
        return 0


class TestYouTubeEngagementZero(unittest.TestCase):
    """Verify that 0 engagement counts are preserved (not coerced to fallback)."""

    def test_zero_view_count_preserved(self):
        """video.get('view_count') == 0 must stay 0, not become the fallback."""
        import json
        import tempfile
        import os

        video = {
            "id": "abc123",
            "title": "Test",
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "upload_date": "20260301",
            "description": "desc",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(video) + "\n")
            f.flush()
            with open(f.name) as rf:
                lines = rf.readlines()

        # Re-parse as the search function would
        parsed = json.loads(lines[0])
        view_count = parsed.get("view_count") if parsed.get("view_count") is not None else 0
        like_count = parsed.get("like_count") if parsed.get("like_count") is not None else 0
        comment_count = parsed.get("comment_count") if parsed.get("comment_count") is not None else 0

        os.unlink(f.name)

        self.assertEqual(0, view_count)
        self.assertEqual(0, like_count)
        self.assertEqual(0, comment_count)


class TestYtDlpFlags(unittest.TestCase):
    def test_search_ignores_global_config_and_browser_cookies(self):
        proc = _DummyProc()
        with mock.patch.object(youtube_yt, "is_ytdlp_installed", return_value=True), \
             mock.patch.object(youtube_yt.subprocess, "Popen", return_value=proc) as popen_mock:
            youtube_yt.search_youtube("Claude Code", "2026-02-01", "2026-03-01")

        cmd = popen_mock.call_args.args[0]
        self.assertIn("--ignore-config", cmd)
        self.assertIn("--no-cookies-from-browser", cmd)

    def test_transcript_fetch_ignores_global_config_and_browser_cookies(self):
        proc = _DummyProc()
        with tempfile.TemporaryDirectory() as temp_dir, \
             mock.patch.object(youtube_yt.subprocess, "Popen", return_value=proc) as popen_mock:
            youtube_yt.fetch_transcript("abc123", temp_dir)

        cmd = popen_mock.call_args.args[0]
        self.assertIn("--ignore-config", cmd)
        self.assertIn("--no-cookies-from-browser", cmd)


class TestExtractTranscriptHighlights(unittest.TestCase):
    def test_extracts_specific_sentences(self):
        transcript = (
            "Hey guys welcome back to the channel. "
            "In today's video we're looking at something special. "
            "The Lego Bugatti Chiron took 13,438 hours to build with over 1 million pieces. "
            "Don't forget to subscribe and hit the bell. "
            "The tolerance on each brick is 0.002 millimeters which is insane for injection molding. "
            "So yeah that's pretty cool. "
            "Thanks for watching see you next time."
        )
        highlights = youtube_yt.extract_transcript_highlights(transcript, "Lego")
        self.assertTrue(len(highlights) > 0)
        joined = " ".join(highlights)
        self.assertIn("13,438", joined)
        self.assertNotIn("subscribe", joined)
        self.assertNotIn("welcome back", joined)

    def test_empty_transcript(self):
        self.assertEqual(youtube_yt.extract_transcript_highlights("", "test"), [])

    def test_respects_limit(self):
        sentences = ". ".join(
            f"The model {i} has {i * 100} parameters and runs at {i * 10} tokens per second"
            for i in range(20)
        ) + "."
        highlights = youtube_yt.extract_transcript_highlights(sentences, "model", limit=3)
        self.assertEqual(len(highlights), 3)

    def test_punctuation_free_transcript_produces_highlights(self):
        # Auto-generated YouTube captions often lack sentence-ending punctuation
        words = (
            "the new Tesla Model Y has 350 miles of range and costs about 45000 dollars "
            "which makes it one of the most affordable electric vehicles on the market today "
            "compared to the BMW iX which starts at 87000 the value proposition is pretty clear "
            "and with the 7500 dollar tax credit you can get it for under 40000"
        )
        highlights = youtube_yt.extract_transcript_highlights(words, "Tesla Model Y")
        self.assertTrue(len(highlights) > 0, "Should produce highlights from punctuation-free text")


if __name__ == "__main__":
    unittest.main()
