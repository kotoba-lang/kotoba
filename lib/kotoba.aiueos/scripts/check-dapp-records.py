#!/usr/bin/env python3
"""Check distributions/awai/dapps/*.json (itonami.dapp.v1) and update-policy.json.

Host-side check only: it reads JSON and refuses; it compiles and boots nothing.

Optional `ui` object (JUN-856, additive): {"document": "<id>"} names the record's UI
document, the module resources/aiueos/session/apps/<id>.kotoba. A record without `ui`
stays valid until every record carries it. `ui` may hold only `document`, whose value
is a lowercase id ([a-z0-9-], at most 40 characters).

Each named document is checked against its record (JUN-856): the module exists, its
`document-id` and `document-title` constants equal the record's id and title, no two
records name the same document, and no module in apps/ is named by no record.
scripts/session-page.py check-table separately checks that index.kotoba requires them.
scripts/check-dapp-documents-negative.py proves each of these checks refuses a mutation.

usage: check-dapp-records.py [ROOT]   ROOT defaults to the lib/kotoba.aiueos this script is in.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent
DAPPS = ROOT / "distributions" / "awai" / "dapps"
REQUIRED = ("id", "dock", "title", "install", "entry", "core", "localCore",
            "localState", "dns", "offline", "remoteOperations", "adr")
OP_REQUIRED = ("operation", "service", "endpoint", "data", "consent", "state")
WANT = {"murakumo", "itonami", "yataverse", "aozora", "browser", "yotei", "shakai",
        "saifu", "bunsho", "hyokeisan", "zuhyo", "tokei", "wifi", "bluetooth",
        "settei", "itonami-apps", "updates", "torihiki",
        "sound", "display", "soshiki", "otent"}


APPS = ROOT / "resources" / "aiueos" / "session" / "apps"
DOC_CONST = r'\(defn %s \[\] :string "((?:[^"\\]|\\.)*)"\)'
DOC_ID = re.compile(r"[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?")


def fail(msg):
    print("AIUEOS_DAPP_RECORDS_FAIL " + msg)
    sys.exit(1)


records = {}
for path in sorted(DAPPS.glob("*.json")):
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("schema") != "itonami.dapp.v1":
        fail(f"{path.name}: schema")
    for key in REQUIRED:
        if key not in rec:
            fail(f"{path.name}: missing {key}")
    if rec["id"] != path.stem:
        fail(f"{path.name}: id {rec['id']}")
    if rec["dns"] != "never" or rec["offline"] != "local-core":
        fail(f"{path.name}: a dapp never resolves a name and runs offline")
    # localOperations (JUN-813, additive): operations that need approval but send nothing over the network
    # (the Updates install). Same keys, same consent rule as remoteOperations.
    for o in rec["remoteOperations"] + rec.get("localOperations", []):
        for key in OP_REQUIRED:
            if key not in o:
                fail(f"{path.name}: operation lacks {key}")
        if o["consent"] != "each-operation":
            fail(f"{path.name}: {o['operation']} consent must be each-operation")
    if "ui" in rec:
        ui = rec["ui"]
        if not isinstance(ui, dict) or set(ui) != {"document"}:
            fail(f"{path.name}: ui must be an object with exactly the key document")
        if not isinstance(ui["document"], str) or not DOC_ID.fullmatch(ui["document"]):
            fail(f"{path.name}: ui.document must match [a-z0-9-]{{1,40}}")
    records[rec["id"]] = rec

docks = [r["dock"] for r in records.values()]
if len(set(docks)) != len(docks):
    fail("duplicate dock id")
if set(records) != WANT:
    fail(f"app set differs: missing {sorted(WANT - set(records))} extra {sorted(set(records) - WANT)}")
if sorted(docks) != list(range(1, len(docks) + 1)):
    fail("dock ids must be 1..N without gaps")

named = {}
for rec in records.values():
    if "ui" in rec:
        doc = rec["ui"]["document"]
        if doc in named:
            fail(f"records {named[doc]} and {rec['id']} both name document {doc}")
        named[doc] = rec["id"]
for doc, rid in sorted(named.items()):
    rec = records[rid]
    path = APPS / (doc + ".kotoba")
    if not path.is_file():
        fail(f"{rid}: document {doc} does not exist ({path.relative_to(ROOT)})")
    text = path.read_text(encoding="utf-8")
    for const, want in (("document-id", rec["id"]), ("document-title", rec["title"])):
        found = re.findall(DOC_CONST % const, text)
        if len(found) != 1:
            fail(f"{doc}.kotoba: want exactly one (defn {const} [] :string \"...\"), found {len(found)}")
        if found[0] != want:
            fail(f"{doc}.kotoba: {const} is {found[0]!r}, record {rid} says {want!r}")
for path in sorted(APPS.glob("*.kotoba")) if APPS.is_dir() else []:
    if path.stem not in named:
        fail(f"document {path.name} is named by no record")

policy = json.loads((ROOT / "distributions" / "awai" / "update-policy.json").read_text(encoding="utf-8"))
if policy.get("consent") != "each-operation" or policy.get("default") not in {m["id"] for m in policy["modes"]}:
    fail("update-policy: consent/default")
print(f"AIUEOS_DAPP_RECORDS_OK apps={len(records)} docks=1..{len(docks)} update-modes={len(policy['modes'])} documents={len(named)}")
