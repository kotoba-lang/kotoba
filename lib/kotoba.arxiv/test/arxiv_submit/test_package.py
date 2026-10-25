"""Unit tests for browser/arxiv_submit/package.py (no network)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "browser"))

from arxiv_submit.package import (  # noqa: E402
    load_package,
    load_status,
    resolve_abstract,
    write_status,
)


PKG = """
{:submission/id :sqrt-space-kv
 :submission/title "Hello World Title"
 :submission/primary-category "cs.LG"
 :submission/cross-lists ["cs.CL" "cs.CC"]
 :submission/source-dir "submissions/sqrt-space-kv/source"
 :submission/source-archive "submissions/sqrt-space-kv/build/x.tar.gz"
 :submission/abstract-file "abstract.txt"
 :submission/final-submit-requires :human-approval
 :submission/comments "hi"}
"""


class PackageTests(unittest.TestCase):
    def test_load_package(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "package.edn"
            p.write_text(PKG)
            pkg = load_package(p)
            self.assertEqual(pkg["title"], "Hello World Title")
            self.assertEqual(pkg["primary"], "cs.LG")
            self.assertEqual(pkg["cross_lists"], ["cs.CL", "cs.CC"])
            self.assertIn("human-approval", str(pkg["final_requires"]))

    def test_abstract_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "package.edn").write_text(PKG)
            (root / "abstract.txt").write_text("ABS BODY")
            pkg = load_package(root / "package.edn")
            self.assertEqual(resolve_abstract(pkg), "ABS BODY")

    def test_write_status(self):
        with tempfile.TemporaryDirectory() as d:
            sp = Path(d) / "status.edn"
            write_status(
                sp,
                {
                    "id": "sqrt-space-kv",
                    "state": "pending-human-final-submit",
                    "draft_id": "7807366",
                    "account": "junkawasaki-n24y",
                    "url": "https://arxiv.org/submit/7807366/start",
                    "notes": ["a", "b"],
                },
            )
            text = sp.read_text()
            self.assertIn(":pending-human-final-submit", text)
            self.assertIn("7807366", text)
            st = load_status(sp)
            self.assertEqual(st["draft_id"], "7807366")


if __name__ == "__main__":
    unittest.main()
