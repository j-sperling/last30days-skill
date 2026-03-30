import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib.instagram import _parse_items


class TestInstagramOwnerTypeSafety(unittest.TestCase):
    def _make_raw(self, **overrides):
        base = {
            "id": "1",
            "code": "ABC123",
            "caption": "test caption",
            "owner": {"username": "testuser"},
        }
        base.update(overrides)
        return base

    def test_owner_as_dict(self):
        items = _parse_items([self._make_raw()], "test")
        self.assertEqual("testuser", items[0]["author_name"])

    def test_owner_as_string(self):
        items = _parse_items([self._make_raw(owner="stringuser")], "test")
        self.assertEqual("stringuser", items[0]["author_name"])

    def test_owner_missing(self):
        raw = self._make_raw()
        del raw["owner"]
        items = _parse_items([raw], "test")
        self.assertEqual("", items[0]["author_name"])

    def test_owner_none(self):
        items = _parse_items([self._make_raw(owner=None)], "test")
        self.assertEqual("", items[0]["author_name"])

    def test_user_field_fallback(self):
        raw = self._make_raw()
        del raw["owner"]
        raw["user"] = {"username": "fallbackuser"}
        items = _parse_items([raw], "test")
        self.assertEqual("fallbackuser", items[0]["author_name"])


if __name__ == "__main__":
    unittest.main()
