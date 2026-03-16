import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliV3Tests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
