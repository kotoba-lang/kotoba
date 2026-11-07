#!/usr/bin/env python3
"""Tests for materialize.py. Run with `python3 oracle/cljc/test_materialize.py`.

The JVM cases need `java` and a Clojure jar in CLOJURE_CP. They skip without them.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from materialize import materialize, output_name, rewrite, source_root  # noqa: E402


LIBRARY = """(ns demo.core
  {:kotoba/export [greet safe]})

(defn greet [] :hello)

(defn safe [] (try (throw (ex-info "no" {})) (catch :default _ :caught)))
"""


class Rewrite(unittest.TestCase):
    def test_quotes_export_vector_and_conditional(self):
        text, counts = rewrite("{:kotoba/export [a]} {:kotoba/export #?(:kotoba [a] :default [b])}")
        self.assertEqual(text, "{:kotoba/export '[a]} {:kotoba/export '#?(:kotoba [a] :default [b])}")
        self.assertEqual(counts["export"], 2)

    def test_catch_default_is_conditional(self):
        text, counts = rewrite("(catch :default e)")
        self.assertEqual(text, "(catch #?(:clj Throwable :default :default) e)")
        self.assertEqual(counts["catch-default"], 1)

    def test_aliased_exception_info_becomes_a_class(self):
        text, counts = rewrite("(catch kerror/ExceptionInfo e)")
        self.assertEqual(text, "(catch #?(:clj clojure.lang.ExceptionInfo :default :default) e)")
        self.assertEqual(counts["catch-aliased"], 1)

    def test_aliased_exception_info_in_thrown(self):
        self.assertEqual(rewrite("(thrown? err/ExceptionInfo (f))")[0],
                         "(thrown? #?(:clj clojure.lang.ExceptionInfo :default :default) (f))")

    def test_other_keywords_are_unchanged(self):
        source = "(catch :default-thing e) :kotoba/exports [a]"
        self.assertEqual(rewrite(source)[0], source)


class Names(unittest.TestCase):
    def test_platform_extension_is_kept(self):
        self.assertEqual(output_name("a/b.cljs.cljk"), "a/b.cljs")
        self.assertEqual(output_name("a/b.cljk"), "a/b.cljc")

    def test_source_root_requires_a_matching_path(self):
        self.assertEqual(source_root("lib/x/src/a/b_c.cljk", "a.b-c"), "lib/x/src")
        self.assertEqual(source_root("a/b.cljk", "a.b"), "")
        self.assertIsNone(source_root("lib/x/src/other.cljk", "a.b"))


class Repository(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        source = self.repo / "lib" / "demo.lib" / "src" / "demo"
        source.mkdir(parents=True)
        (source / "core.cljk").write_text(LIBRARY)
        tests = self.repo / "lib" / "demo.lib" / "test" / "demo"
        tests.mkdir(parents=True)
        (tests / "core_test.cljk").write_text("(ns demo.core-test)\n")
        for command in (["init", "-q"], ["add", "."],
                        ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "x"]):
            subprocess.run(["git", "-C", str(self.repo), *command], check=True)

    def test_reads_git_objects_and_records_the_commit(self):
        (self.repo / "lib" / "demo.lib" / "src" / "demo" / "core.cljk").write_text("(ns demo.core) ;; WIP\n")
        manifest = materialize(self.repo, "HEAD", self.base / "out")
        output = (self.base / "out" / manifest["files"][0]["output"]).read_text()
        self.assertIn(":kotoba/export '[greet safe]", output)
        self.assertNotIn("WIP", output)
        self.assertEqual(len(manifest["source-commit"]), 40)
        self.assertEqual([row["namespace"] for row in manifest["files"]], ["demo.core"])
        self.assertEqual(manifest["rewrites"], {"export": 1, "catch-default": 1, "catch-aliased": 0})

    def test_excludes_by_root_and_not_by_namespace_segment(self):
        source = self.repo / "lib" / "demo.lib" / "src" / "kotoba" / "test"
        source.mkdir(parents=True)
        (source / "generator.cljk").write_text("(ns kotoba.test.generator)\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-qm", "y"], check=True)
        names = {row["namespace"] for row in materialize(self.repo, "HEAD", self.base / "out")["files"]}
        self.assertEqual(names, {"demo.core", "kotoba.test.generator"})

    def test_refuses_output_inside_the_repository(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            materialize(self.repo, "HEAD", self.repo / "out")

    def test_refuses_a_non_empty_output(self):
        out = self.base / "out"
        out.mkdir()
        (out / "keep").write_text("x")
        with self.assertRaisesRegex(ValueError, "not empty"):
            materialize(self.repo, "HEAD", out)

    def test_refuses_an_unknown_library(self):
        with self.assertRaisesRegex(ValueError, "unknown libraries"):
            materialize(self.repo, "HEAD", self.base / "out", ["nope"])

    @unittest.skipUnless(os.environ.get("CLOJURE_CP"), "CLOJURE_CP is not set")
    def test_jvm_loads_the_rewrite_and_rejects_the_control(self):
        expression = "(require 'demo.core) (println (demo.core/safe))"

        def load(out):
            classpath = (out / "classpath.txt").read_text().strip() + ":" + os.environ["CLOJURE_CP"]
            return subprocess.run(["java", "-cp", classpath, "clojure.main", "-e", expression],
                                  capture_output=True, text=True)

        materialize(self.repo, "HEAD", self.base / "good")
        good = load(self.base / "good")
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertIn(":caught", good.stdout)

        materialize(self.repo, "HEAD", self.base / "control", apply_rewrites=False)
        control = load(self.base / "control")
        self.assertNotEqual(control.returncode, 0)
        self.assertIn("Unable to resolve symbol: greet", control.stderr)


if __name__ == "__main__":
    unittest.main()
