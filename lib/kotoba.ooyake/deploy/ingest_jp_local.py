#!/usr/bin/env python3
"""ooyake 公 — ingest Japanese local government units (都道府県 + 市区町村).

ADR-2606021600. Breadth move for the gov-atlas: ingest the bundled, official-code
Japanese local-government dataset (47 prefectures + designated cities + Tokyo 23
special wards + capitals) into the `gov-atlas-v1` graph as :gov.unit entities.

SOURCE (no fabrication, no network — G4/G5): the committed authoritative dataset at
    60-apps/etzhayyim-project-states/data/gov/jpn/{prefecture,municipality}.ndjson
which carries official 全国地方公共団体コード (JIS X 0401/0402, in `adminCode`) +
地方自治法 legal basis. Each row's adminCode is preserved as :gov.unit/external-code
(jp-jichitai:<code>) and the official website as :gov.unit/provenance. Rows ship
:sourcing :representative + :verification-status :unverified-seed (G5): they are a
curated bundle, NOT an ooyake-reconcile live-verified fetch — the `reconcile` cell
(live mode, gated) promotes them to :authoritative against the official source.

Write path: kg.ingest_batch with a Bearer token (operator-local). DRY RUN without a
token. Never runs `kotoba commit`.

Usage:
    python3 ingest_jp_local.py                         # dry run
    KOTOBA_TOKEN=<bearer> python3 ingest_jp_local.py   # live ingest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
DATASET_DIR = os.path.join(_REPO, "60-apps", "etzhayyim-project-states", "data", "gov", "jpn")
PREF_NDJSON = os.path.join(DATASET_DIR, "prefecture.ndjson")
MUNI_NDJSON = os.path.join(DATASET_DIR, "municipality.ndjson")

GOV_GRAPH = "gov-atlas-v1"
NSID_INGEST = "com.etzhayyim.apps.kotobase.kg.ingest_batch"
LAST_VERIFIED = "2026-06-02"
PROVENANCE_DATASET = "60-apps/etzhayyim-project-states/data/gov/jpn (官公庁公開データ / 地方自治法)"

_WARD_TYPES = {"special-ward", "ward"}


def _ndjson(path: str):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _cofog(tags) -> list[str]:
    return [t.split(":", 1)[1] for t in (tags or []) if t.startswith("cofog:")]


def _entity(uid, type_ns, label_en, label_local, claims, relations):
    out = {
        "id": uid,
        "type": type_ns,
        "labelEn": label_en,
        "claims": claims,
        "relations": relations,
        "extractor": "deploy/ingest_jp_local.py",
        "license": "Apache-2.0 + etzhayyim Charter Rider v2.0",
    }
    if label_local:
        out["labelJa"] = label_local
    return out


def project_prefecture(row: dict) -> dict:
    code = row["adminCode"]  # 2-digit
    uid = f"gov.jpn.pref.{code}"
    claims = [
        {"pred": "gov.unit/atlas-did", "value": f"did:web:etzhayyim.com:gov:jpn:pref:{code}"},
        {"pred": "gov.unit/level", "value": "prefecture"},
        {"pred": "gov.unit/branch", "value": "local"},
        {"pred": "gov.unit/jurisdiction", "value": f"jpn-{code}"},
        {"pred": "gov.unit/name-local", "value": row["name"]},
        {"pred": "gov.unit/name-en", "value": row.get("nameEn", "")},
        {"pred": "gov.unit/official-url", "value": row.get("website", "")},
        {"pred": "gov.unit/external-code", "value": f"jp-jichitai:{code}"},
        {"pred": "gov.unit/external-code", "value": f"iso3166-2:JP-{code}"},
        {"pred": "gov.unit/status", "value": "active"},
        {"pred": "gov.unit/sourcing", "value": "representative"},
        {"pred": "gov.unit/provenance", "value": row.get("website") or PROVENANCE_DATASET},
        {"pred": "gov.unit/last-verified", "value": LAST_VERIFIED},
        {"pred": "gov.unit/verification-status", "value": "unverified-seed"},
    ]
    claims += [{"pred": "gov.unit/cofog", "value": c} for c in _cofog(row.get("tags"))]
    relations = [{"pred": "gov.unit/parent", "dstId": "gov.jpn"}]
    return _entity(uid, "gov.unit", row.get("nameEn", uid), row["name"], claims, relations)


def project_municipality(row: dict) -> dict:
    code = row["adminCode"]  # 6-digit
    pref2 = code[:2]
    uid = f"gov.jpn.city.{code}"
    level = "ward" if row.get("municipalType") in _WARD_TYPES else "municipality"
    claims = [
        {"pred": "gov.unit/atlas-did", "value": f"did:web:etzhayyim.com:gov:jpn:city:{code}"},
        {"pred": "gov.unit/level", "value": level},
        {"pred": "gov.unit/branch", "value": "local"},
        {"pred": "gov.unit/jurisdiction", "value": f"jpn-{pref2}"},
        {"pred": "gov.unit/name-local", "value": row["name"]},
        {"pred": "gov.unit/name-en", "value": row.get("nameEn", "")},
        {"pred": "gov.unit/official-url", "value": row.get("website", "")},
        {"pred": "gov.unit/external-code", "value": f"jp-jichitai:{code}"},
        {"pred": "gov.unit/status", "value": "active"},
        {"pred": "gov.unit/sourcing", "value": "representative"},
        {"pred": "gov.unit/provenance", "value": row.get("website") or PROVENANCE_DATASET},
        {"pred": "gov.unit/last-verified", "value": LAST_VERIFIED},
        {"pred": "gov.unit/verification-status", "value": "unverified-seed"},
    ]
    if row.get("municipalType"):
        claims.append({"pred": "gov.unit/municipal-type", "value": row["municipalType"]})
    claims += [{"pred": "gov.unit/cofog", "value": c} for c in _cofog(row.get("tags"))]
    relations = [{"pred": "gov.unit/parent", "dstId": f"gov.jpn.pref.{pref2}"}]
    return _entity(uid, "gov.unit", row.get("nameEn", uid), row["name"], claims, relations)


def post_batch(url: str, graph: str, entities: list[dict], token: str) -> tuple[int, dict]:
    data = json.dumps({"graph": graph, "entities": entities}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{url}/xrpc/{NSID_INGEST}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return e.code, {"error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("KOTOBA_URL", "http://127.0.0.1:8077"))
    args = ap.parse_args()

    prefs = [project_prefecture(r) for r in _ndjson(PREF_NDJSON)]
    munis = [project_municipality(r) for r in _ndjson(MUNI_NDJSON)]
    entities = prefs + munis
    wards = sum(1 for m in munis if any(c["pred"] == "gov.unit/level" and c["value"] == "ward" for c in m["claims"]))
    datoms = sum(len(e["claims"]) + len(e["relations"]) + 1 for e in entities)
    print(f"ooyake JP-local ingest — {len(prefs)} prefectures + {len(munis)} municipalities "
          f"({wards} special-wards) = {len(entities)} units (~{datoms} datoms) → {GOV_GRAPH}")

    token = os.environ.get("KOTOBA_TOKEN") or os.environ.get("KOTOBA_SESSION_POP")
    if not token:
        print("DRY RUN — no KOTOBA_TOKEN. Set it to ingest. No writes performed.")
        for e in entities[:4]:
            print(f"  - {e['id']:<24} {e.get('labelJa','')}  rels={len(e['relations'])}")
        print(f"  … ({len(entities)} total)")
        return 0

    # ingest in chunks (keep request bodies modest)
    rc, written = 0, 0
    CHUNK = 60
    for i in range(0, len(entities), CHUNK):
        chunk = entities[i:i + CHUNK]
        st, body = post_batch(args.url, GOV_GRAPH, chunk, token)
        ok = st == 200 and body.get("ok")
        written += body.get("entityCount", 0) if ok else 0
        print(f"  batch {i//CHUNK+1}: {st} ok={body.get('ok')} entityCount={body.get('entityCount')} quadCount={body.get('quadCount')}")
        rc |= 0 if ok else 1
    print(f"==> ingested {written}/{len(entities)} JP-local units into {GOV_GRAPH}. "
          "All :sourcing :representative / :unverified-seed (G5; reconcile-live promotes). NOT sealing.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
