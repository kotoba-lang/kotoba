#!/usr/bin/env python3
"""ooyake 公 — promote official-code units to :authoritative (bootstrap-attested).

ADR-2606021600 + BOOTSTRAP-ATTESTATION-reconcile-live.md. Under the Founder's
provisional bootstrap authorization (Council < quorum), re-asserts the official-code
tiers in gov-atlas-v1 with :sourcing :authoritative + :verification-status
:maintainer-verified + :gov.unit/attestation = the attestation record. Datomic
upsert: the latest cardinality-one value wins; the prior :representative datom stays
in as-of history (full promotion trail).

SCOPE (G5 — only official-code-register provenance, no live fetch):
  - 47 都道府県 (ISO 3166-2:JP + 全国地方公共団体コード)
  - JP 市区町村 in the bundled dataset (全国地方公共団体コード, 地方自治法 / e-Gov)
Everything else (global name-only municipalities, country stubs, the 1,718 long tail)
stays :representative — NOT promoted here.

Source of truth: 60-apps/etzhayyim-project-states/data/gov/jpn/{prefecture,municipality}.ndjson.
Write path: kg.ingest_batch + Bearer token (operator-local). DRY RUN without a token.
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
JP = os.path.join(_REPO, "60-apps", "etzhayyim-project-states", "data", "gov", "jpn")
GOV_GRAPH = "gov-atlas-v1"
NSID_INGEST = "com.etzhayyim.apps.kotobase.kg.ingest_batch"
LAST_VERIFIED = "2026-06-02"
ATTESTATION = "BOOTSTRAP-ATTESTATION-reconcile-live.md (Seat 1 Lv7, 2026-06-02; re-ratify at Council 3-of-5)"
WARD_TYPES = {"special-ward", "ward"}


def _ndjson(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _promotion_claims(extra):
    # cardinality-one re-assertions that flip the current value to authoritative
    return [
        {"pred": "gov.unit/sourcing", "value": "authoritative"},
        {"pred": "gov.unit/verification-status", "value": "maintainer-verified"},
        {"pred": "gov.unit/attestation", "value": ATTESTATION},
        {"pred": "gov.unit/last-verified", "value": LAST_VERIFIED},
    ] + extra


def _entity(uid, label_en, label_local, claims):
    out = {"id": uid, "type": "gov.unit", "labelEn": label_en, "claims": claims, "relations": [],
           "extractor": "deploy/promote_authoritative.py",
           "license": "Apache-2.0 + etzhayyim Charter Rider v2.0"}
    if label_local:
        out["labelJa"] = label_local
    return out


def build_promotions():
    ents = []
    for r in _ndjson(os.path.join(JP, "prefecture.ndjson")):
        c = r["adminCode"]
        ents.append(_entity(f"gov.jpn.pref.{c}", r.get("nameEn", c), r["name"], _promotion_claims(
            [{"pred": "gov.unit/provenance", "value": "全国地方公共団体コード (JIS X 0401) + ISO 3166-2:JP — " + (r.get("website") or "総務省")}])))
    for r in _ndjson(os.path.join(JP, "municipality.ndjson")):
        c = r["adminCode"]
        ents.append(_entity(f"gov.jpn.city.{c}", r.get("nameEn", c), r["name"], _promotion_claims(
            [{"pred": "gov.unit/provenance", "value": "全国地方公共団体コード (JIS X 0402) / 地方自治法 — " + (r.get("website") or "総務省 e-Gov")}])))
    return ents


def post_batch(url, entities, token):
    data = json.dumps({"graph": GOV_GRAPH, "entities": entities}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{url}/xrpc/{NSID_INGEST}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            return e.code, {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("KOTOBA_URL", "http://127.0.0.1:8077"))
    args = ap.parse_args()
    ents = build_promotions()
    print(f"ooyake authoritative promotion (bootstrap-attested) — {len(ents)} official-code JP units "
          f"(47 prefectures + {len(ents)-47} municipalities) → :authoritative in {GOV_GRAPH}")
    token = os.environ.get("KOTOBA_TOKEN") or os.environ.get("KOTOBA_SESSION_POP")
    if not token:
        print("DRY RUN — no KOTOBA_TOKEN. No writes.")
        print(f"  attestation: {ATTESTATION}")
        return 0
    rc, CHUNK = 0, 80
    for i in range(0, len(ents), CHUNK):
        st, body = post_batch(args.url, ents[i:i + CHUNK], token)
        ok = st == 200 and body.get("ok")
        print(f"  batch {i//CHUNK+1}: {st} ok={body.get('ok')} entityCount={body.get('entityCount')} quadCount={body.get('quadCount')}")
        rc |= 0 if ok else 1
    print("==> promoted official-code JP backbone to :authoritative / :maintainer-verified "
          "(prior :representative preserved in as-of history). Re-ratify at Council 3-of-5. NOT sealing.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
