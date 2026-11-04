#!/usr/bin/env python3
"""Check distributions/awai/dapps/*.json (itonami.dapp.v1) and update-policy.json.

Host-side check only: it reads JSON and refuses; it compiles and boots nothing.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DAPPS = ROOT / "distributions" / "awai" / "dapps"
REQUIRED = ("id", "dock", "title", "install", "entry", "core", "localCore",
            "localState", "dns", "offline", "remoteOperations", "adr")
OP_REQUIRED = ("operation", "service", "endpoint", "data", "consent", "state")
WANT = {"murakumo", "itonami", "yataverse", "aozora", "browser", "yotei", "shakai",
        "saifu", "bunsho", "hyokeisan", "zuhyo", "tokei", "wifi", "bluetooth",
        "settei", "itonami-apps", "updates", "torihiki"}


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
    for o in rec["remoteOperations"]:
        for key in OP_REQUIRED:
            if key not in o:
                fail(f"{path.name}: operation lacks {key}")
        if o["consent"] != "each-operation":
            fail(f"{path.name}: {o['operation']} consent must be each-operation")
    records[rec["id"]] = rec

docks = [r["dock"] for r in records.values()]
if len(set(docks)) != len(docks):
    fail("duplicate dock id")
if set(records) != WANT:
    fail(f"app set differs: missing {sorted(WANT - set(records))} extra {sorted(set(records) - WANT)}")
if sorted(docks) != list(range(1, len(docks) + 1)):
    fail("dock ids must be 1..N without gaps")

policy = json.loads((ROOT / "distributions" / "awai" / "update-policy.json").read_text(encoding="utf-8"))
if policy.get("consent") != "each-operation" or policy.get("default") not in {m["id"] for m in policy["modes"]}:
    fail("update-policy: consent/default")
print(f"AIUEOS_DAPP_RECORDS_OK apps={len(records)} docks=1..{len(docks)} update-modes={len(policy['modes'])}")
