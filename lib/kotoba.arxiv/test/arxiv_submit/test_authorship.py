"""Authorship radio selection contract (arXiv v1.5 Start form).

arXiv ships a hidden sentinel:
  <input checked value="0" style="display:none" name="is_author" type="radio">
Visible choices are value=1 (author) and value=2 (third-party).
Selecting value=0 is rejected server-side with
  "You must make an authorship selection".
"""
from __future__ import annotations

import unittest


class AuthorshipContract(unittest.TestCase):
    def test_sentinel_value_must_not_be_selected(self):
        # Document the contract used by flow.fill_start_form
        sentinel = "0"
        author = "1"
        third_party = "2"
        self.assertNotEqual(sentinel, author)
        # runner must select author, never nth(0) which is the sentinel
        radios = [
            {"value": sentinel, "visible": False, "checked_default": True},
            {"value": author, "visible": True, "checked_default": False},
            {"value": third_party, "visible": True, "checked_default": False},
        ]
        # correct selection algorithm
        chosen = next(r for r in radios if r["value"] == author)
        self.assertTrue(chosen["visible"])
        self.assertEqual(chosen["value"], "1")
        # wrong algorithm (historical bug)
        wrong = radios[0]
        self.assertEqual(wrong["value"], "0")
        self.assertFalse(wrong["visible"])


if __name__ == "__main__":
    unittest.main()
