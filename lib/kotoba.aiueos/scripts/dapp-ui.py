#!/usr/bin/env python3
"""Splice and check the generated dapp UI in the hosted session page (JUN-809).

  dapp-ui.py splice   copy distributions/awai/dapps/ui/generated/* into
                      resources/aiueos/session/index.html and stamp the source hash
  dapp-ui.py check    refuse if the page differs from generated/, or generated/ was
                      not made from the current sources

The generated files come from ui.cljk (kotoba-lang/html + css), run once locally
with kbb; this script only copies bytes and hashes. Host-side, no compiler.
"""
import hashlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
UI = ROOT / "distributions" / "awai" / "dapps" / "ui"
GEN = UI / "generated"
PAGE = ROOT / "resources" / "aiueos" / "session" / "index.html"
REGIONS = {  # name -> (generated file, begin marker, end marker)
    "tiles": ("tiles.html", "<!-- dapp-ui:tiles:begin -->", "<!-- dapp-ui:tiles:end -->"),
    "dock": ("dock.html", "<!-- dapp-ui:dock:begin -->", "<!-- dapp-ui:dock:end -->"),
    "windows": ("windows.html", "<!-- dapp-ui:windows:begin -->", "<!-- dapp-ui:windows:end -->"),
    "css": ("dapp-ui.css", "/* dapp-ui:css:begin */", "/* dapp-ui:css:end */"),
}
STAMP = re.compile(r"<!-- dapp-ui:source-sha256 ([0-9a-f]{64}) -->")


def source_hash():
    h = hashlib.sha256()
    files = [UI / "ui.cljk", ROOT / "distributions" / "awai" / "update-policy.json"]
    files += sorted((ROOT / "distributions" / "awai" / "dapps").glob("*.json"))
    for f in files:
        h.update(f.relative_to(ROOT).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def region(text, begin, end):
    i, j = text.find(begin), text.find(end)
    if i < 0 or j < 0 or j < i:
        sys.exit(f"AIUEOS_DAPP_UI_FAIL marker missing: {begin}")
    return i + len(begin), j


def main(mode):
    page = PAGE.read_text(encoding="utf-8")
    if mode == "splice":
        for name, (fn, b, e) in REGIONS.items():
            body = (GEN / fn).read_text(encoding="utf-8").rstrip("\n")
            s, t = region(page, b, e)
            page = page[:s] + "\n" + body + "\n" + page[t:]
        stamp = f"<!-- dapp-ui:source-sha256 {source_hash()} -->"
        page = STAMP.sub(stamp, page) if STAMP.search(page) else page.replace("</body>", stamp + "\n</body>", 1)
        PAGE.write_text(page, encoding="utf-8")
        print("AIUEOS_DAPP_UI_SPLICED")
        return
    for name, (fn, b, e) in REGIONS.items():
        s, t = region(page, b, e)
        if page[s:t].strip("\n") != (GEN / fn).read_text(encoding="utf-8").rstrip("\n"):
            sys.exit(f"AIUEOS_DAPP_UI_FAIL page region {name} differs from generated/{fn}")
    m = STAMP.search(page)
    if not m or m.group(1) != source_hash():
        sys.exit("AIUEOS_DAPP_UI_FAIL generated UI is stale: rerun ui.cljk and `dapp-ui.py splice`")
    if "__itonamiBuildApps" in page:
        sys.exit("AIUEOS_DAPP_UI_FAIL hand-written JS DOM builder is still present")
    print(f"AIUEOS_DAPP_UI_OK regions={len(REGIONS)} source={m.group(1)[:12]}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("splice", "check"):
        sys.exit(__doc__)
    main(sys.argv[1])
