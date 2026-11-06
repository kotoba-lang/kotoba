#!/usr/bin/env python3
"""Negative controls for the dapp UI document checks (JUN-856).

Copies the files the checks read into a temporary directory, applies one deliberate
mutation at a time, and requires the named check to refuse it with the expected
message. The unmutated copy must pass first. Nothing in the repository is changed.
Host-side only: it runs check-dapp-records.py and `session-page.py check-table`.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS = ROOT / "scripts" / "check-dapp-records.py"
TABLE = ROOT / "scripts" / "session-page.py"
SESSION = "resources/aiueos/session"


def run(tree, script, *args):
    r = subprocess.run([sys.executable, "-I", str(tree / "scripts" / script), *args], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def copy_tree(dst):
    for rel in ("scripts", "distributions/awai", SESSION):
        shutil.copytree(ROOT / rel, dst / rel)


def edit(path, old, new):
    t = path.read_text(encoding="utf-8")
    assert old in t, (path, old)
    path.write_text(t.replace(old, new, 1), encoding="utf-8")


def set_ui(tree, rid, ui):
    p = tree / "distributions/awai/dapps" / (rid + ".json")
    r = json.loads(p.read_text(encoding="utf-8"))
    r["ui"] = ui
    p.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")


def add_document(tree, doc, did, title):
    (tree / SESSION / "apps" / (doc + ".kotoba")).write_text(
        '(ns app-%s (:require [html-hiccup :as h]))\n(defn document-id [] :string "%s")\n(defn document-title [] :string "%s")\n' % (doc, did, title),
        encoding="utf-8")


def c_missing(t): set_ui(t, "itonami", {"document": "nonexistent"})
def c_id(t): edit(t / SESSION / "apps/murakumo.kotoba", '(defn document-id [] :string "murakumo")', '(defn document-id [] :string "murakumx")')
def c_title(t): edit(t / SESSION / "apps/murakumo.kotoba", '(defn document-title [] :string "Murakumo")', '(defn document-title [] :string "Murakumo!")')
def c_dup(t): set_ui(t, "yataverse", {"document": "murakumo"})
def c_orphan(t): add_document(t, "extra", "extra", "Extra")
def c_shape(t): set_ui(t, "yataverse", {"document": "yataverse", "extra": 1})
def c_badid(t): set_ui(t, "yataverse", {"document": "Not An Id"})
def c_const_gone(t): edit(t / SESSION / "apps/itonami.kotoba", "(defn document-title [] :string", "(defn document-name [] :string")


def c_unnamed_require(t): edit(t / SESSION / "index.kotoba", "[app-itonami :as ai]", "[app-itonami :as ai] [app-extra :as ax]")


def c_require_dropped(t): edit(t / SESSION / "index.kotoba", " [app-itonami :as ai]", "")


CONTROLS = [
    ("record names a document that does not exist", RECORDS, c_missing, "does not exist"),
    ("document id differs from the record's", RECORDS, c_id, "document-id is 'murakumx'"),
    ("document title differs from the record's", RECORDS, c_title, "document-title is 'Murakumo!'"),
    ("two records name the same document", RECORDS, c_dup, "both name document murakumo"),
    ("a document is named by no record", RECORDS, c_orphan, "named by no record"),
    ("ui has a key besides document", RECORDS, c_shape, "ui must be an object"),
    ("ui.document is not an id", RECORDS, c_badid, "must match"),
    ("document lacks its title constant", RECORDS, c_const_gone, "found 0"),
    ("index.kotoba requires a document no record names", TABLE, c_unnamed_require, "index.kotoba requires"),
    ("index.kotoba drops a require the records name", TABLE, c_require_dropped, "index.kotoba requires"),
]


def check_for(script):
    return ("check-dapp-records.py", ()) if script == RECORDS else ("session-page.py", ("check-table",))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp) / "base"
        copy_tree(base)
        for script in (RECORDS, TABLE):
            name, args = check_for(script)
            code, out = run(base, name, *args)
            if code != 0:
                sys.exit("NEGATIVE_CONTROL_FAIL unmutated tree is refused by %s: %s" % (name, out))
        bad = 0
        for i, (label, script, mutate, want) in enumerate(CONTROLS):
            tree = pathlib.Path(tmp) / ("c%d" % i)
            shutil.copytree(base, tree)
            mutate(tree)
            name, args = check_for(script)
            code, out = run(tree, name, *args)
            ok = code != 0 and want in out
            bad += not ok
            print("%s %s: %s" % ("REFUSED" if ok else "NOT_REFUSED", label, out.splitlines()[-1] if out else "(no output)"))
        if bad:
            sys.exit("NEGATIVE_CONTROL_FAIL %d of %d not refused" % (bad, len(CONTROLS)))
        print("AIUEOS_DAPP_DOCUMENT_NEGATIVE_OK controls=%d" % len(CONTROLS))


main()
