#!/usr/bin/env python3 -I
"""Build and check the hosted session page from its Kotoba source (JUN-821).

  session-page.py build          run index.kotoba with Amu and write index.html
  session-page.py check          refuse if index.html is not what index.kotoba prints
                                 (needs Amu), and if the app table differs from the records
  session-page.py check-table    only the table-versus-records check (no Amu)

index.kotoba is the source of the page; index.html is its generated output and is
committed because the host serves that path. Amu is found through $AMU_HOME/bin/amu
or `amu` on PATH. Host-side only: it compiles nothing but the one source and boots
nothing. `amu run` prints main's value ("0") after the page; it is stripped only when
the output ends exactly with "</html>\\n0\\n".
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SESSION = ROOT / "resources" / "aiueos" / "session"
SRC = SESSION / "index.kotoba"
PAGE = SESSION / "index.html"
DAPPS = ROOT / "distributions" / "awai" / "dapps"


def fail(msg, code=1):
    print("AIUEOS_SESSION_PAGE_FAIL " + msg)
    sys.exit(code)


def amu():
    home = os.environ.get("AMU_HOME")
    path = pathlib.Path(home) / "bin" / "amu" if home else None
    if path and path.is_file():
        return str(path)
    found = shutil.which("amu")
    if found:
        return found
    fail("Amu not found (set AMU_HOME or put amu on PATH); the page cannot be built or checked", 2)


def render():
    r = subprocess.run([amu(), "run", str(SRC)], capture_output=True, timeout=300)
    if r.returncode != 0:
        fail("amu run exited %d: %s" % (r.returncode, r.stderr.decode("utf-8", "replace")[:300]))
    out = r.stdout
    if not out.endswith(b"</html>\n0\n"):
        fail("unexpected end of output (want </html>, newline, main's 0)")
    return out[:-2]


def table_rows(text, name):
    m = re.search(r"\(defn %s \[d :i64\] :string \(case d (.*?) \"\"\)\)\n" % re.escape(name), text)
    if not m:
        fail("table function %s not found" % name)
    pairs = re.findall(r"(\d+) \"((?:[^\"\\]|\\.)*)\"", m.group(1))
    return {int(k): v for k, v in pairs}


def check_table():
    text = SRC.read_text(encoding="utf-8")
    count = int(re.search(r"\(defn app-count \[\] :i64 (\d+)\)", text).group(1))
    recs = {}
    for p in sorted(DAPPS.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        recs[r["dock"]] = r
    if count != len(recs) or sorted(recs) != list(range(1, count + 1)):
        fail("app-count %d differs from %d records with docks 1..N" % (count, len(recs)))
    want = {
        "rec-id": lambda r: r["id"],
        "rec-title": lambda r: r["title"],
        "rec-cat": lambda r: r.get("category", ""),
        "rec-ops": lambda r: ", ".join(o["operation"] for o in r["remoteOperations"]),
    }
    for fn, get in want.items():
        rows = table_rows(text, fn)
        for dock, r in recs.items():
            if rows.get(dock) != get(r):
                fail("%s row %d is %r, record %s says %r" % (fn, dock, rows.get(dock), r["id"], get(r)))
        if set(rows) != set(recs):
            fail("%s has rows %s, records have %s" % (fn, sorted(rows), sorted(recs)))
    print("AIUEOS_SESSION_TABLE_OK apps=%d" % count)


def main(mode):
    if mode == "build":
        check_table()
        PAGE.write_bytes(render())
        print("AIUEOS_SESSION_PAGE_BUILT bytes=%d" % PAGE.stat().st_size)
    elif mode == "check-table":
        check_table()
    elif mode == "check":
        check_table()
        if render() != PAGE.read_bytes():
            fail("index.html is stale: run `session-page.py build`")
        print("AIUEOS_SESSION_PAGE_OK")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
