#!/usr/bin/env python3
"""ooyake 公 — global breadth ingest of REAL municipalities (177 countries).

ADR-2606021600. Ingests the verifiably-REAL subset of the bundled multi-country
government dataset (60-apps/etzhayyim-project-states/data/gov/<cc>/municipality.ndjson)
into the gov-atlas-v1 kotoba graph.

G5 NON-FABRICATION DISCIPLINE — this script ingests ONLY the real-named municipality
tier (527 rows, all real city names + official websites + legal basis: Stuttgart,
Paris, London, 서울특별시, 札幌市 …). It DELIBERATELY SKIPS the synthetic / placeholder
tiers in the same dataset, and LOGS the skip (no silent truncation):
  - district.ndjson   (1,507 rows) — 100% nanoid placeholders ("Dst 17698898 …")
  - ministry.ndjson / office.ndjson — generic placeholders ("Executive", "Cabinet")
  - lea.ndjson        (INTERPOL NCBs) — out of scope (G10 never-a-target-list)
  - country "0/"      — synthetic template
These remain a future real-authoritative bundle; they are NOT counted as coverage.

Country parent units (gov.<cc>) are created ISO3-identified (name-en = the official
ISO3 code, a fact — real localized names pending a real source); the 5 countries
already carrying real names in the seed (jpn/usa/gbr/deu/kor) are NEVER overwritten.
jpn municipalities are skipped here (already ingested with full 全国地方公共団体コード
by ingest_jp_local.py).

All rows ship :sourcing :representative / :verification-status :unverified-seed (G5).
Write path: kg.ingest_batch + Bearer token (operator-local). DRY RUN without token.
Never runs `kotoba commit`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
GOV_DIR = os.path.join(_REPO, "60-apps", "etzhayyim-project-states", "data", "gov")
GOV_GRAPH = "gov-atlas-v1"
NSID_INGEST = "com.etzhayyim.apps.kotobase.kg.ingest_batch"
LAST_VERIFIED = "2026-06-02"

# countries already carrying REAL names in the ooyake seed — never overwrite with a stub.
REAL_COUNTRY_UNITS = {"jpn", "usa", "gbr", "deu", "kor"}
SKIP_COUNTRY_DIRS = {"0", "intl"}  # synthetic template / non-country
WARD_TYPES = {"special-ward", "ward"}


def _slug(path: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", path.strip().lower()).strip("-")
    return s or "x"


def _cofog(tags):
    return [t.split(":", 1)[1] for t in (tags or []) if t.startswith("cofog:")]


def _is_synthetic(row) -> bool:
    n = row.get("name", "")
    if not n or n.startswith("Dst ") or n in ("Executive", "Cabinet", "Ministry Of"):
        return True
    return any("nanoid" in t for t in row.get("tags", []))


def _entity(uid, label_en, label_local, claims, relations):
    out = {
        "id": uid, "type": "gov.unit", "labelEn": label_en,
        "claims": claims, "relations": relations,
        "extractor": "deploy/ingest_states_global.py",
        "license": "Apache-2.0 + etzhayyim Charter Rider v2.0",
    }
    if label_local and label_local != label_en:
        out["labelJa"] = label_local
    return out


def project_municipality(cc, row):
    if _is_synthetic(row):
        return None
    uid = f"gov.{cc}.muni.{_slug(row.get('path', row['name']))}"
    level = "ward" if row.get("municipalType") in WARD_TYPES else "municipality"
    claims = [
        {"pred": "gov.unit/atlas-did", "value": f"did:web:etzhayyim.com:gov:{cc}:muni:{_slug(row.get('path', row['name']))}"},
        {"pred": "gov.unit/level", "value": level},
        {"pred": "gov.unit/branch", "value": "local"},
        {"pred": "gov.unit/jurisdiction", "value": cc},
        {"pred": "gov.unit/name-local", "value": row["name"]},
        {"pred": "gov.unit/name-en", "value": row.get("nameEn", row["name"])},
        {"pred": "gov.unit/official-url", "value": row.get("website", "")},
        {"pred": "gov.unit/status", "value": "active"},
        {"pred": "gov.unit/sourcing", "value": "representative"},
        {"pred": "gov.unit/provenance", "value": row.get("website") or f"etzhayyim-project-states/data/gov/{cc}"},
        {"pred": "gov.unit/last-verified", "value": LAST_VERIFIED},
        {"pred": "gov.unit/verification-status", "value": "unverified-seed"},
    ]
    if row.get("municipalType"):
        claims.append({"pred": "gov.unit/municipal-type", "value": row["municipalType"]})
    if row.get("population"):
        claims.append({"pred": "gov.unit/population", "value": str(row["population"])})
    claims += [{"pred": "gov.unit/cofog", "value": c} for c in _cofog(row.get("tags"))]
    relations = [{"pred": "gov.unit/parent", "dstId": f"gov.{cc}"}]
    return _entity(uid, row.get("nameEn", row["name"]), row["name"], claims, relations)


_NCB_SUFFIX = " INTERPOL National Central Bureau"


def _country_names() -> dict:
    """cc -> real English country name, from the INTERPOL NCB row in each country's
    lea.ndjson (real in-repo data, not fabricated, G5; ~169/195 carry it)."""
    m = {}
    for cc in os.listdir(GOV_DIR):
        f = os.path.join(GOV_DIR, cc, "lea.ndjson")
        if not os.path.isfile(f):
            continue
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            ne = json.loads(line).get("nameEn") or ""
            if ne.endswith(_NCB_SUFFIX):
                m[cc] = ne[:-len(_NCB_SUFFIX)].strip()
                break
    return m


_CC_NAMES = _country_names()


def country_unit(cc):
    """ISO3-identified country unit; real English name from the lea NCB record when
    available (G5 - real in-repo source), else the factual ISO3 code (no fabrication)."""
    nm = _CC_NAMES.get(cc, cc.upper())
    prov = ("country name from lea.ndjson INTERPOL NCB record" if cc in _CC_NAMES
            else "iso-3166-1 alpha-3 (code-stub; localized name pending real source)")
    return _entity(
        f"gov.{cc}", nm, None,
        [
            {"pred": "gov.unit/atlas-did", "value": f"did:web:etzhayyim.com:gov:{cc}"},
            {"pred": "gov.unit/level", "value": "country"},
            {"pred": "gov.unit/branch", "value": "executive"},
            {"pred": "gov.unit/jurisdiction", "value": cc},
            {"pred": "gov.unit/name-en", "value": nm},
            {"pred": "gov.unit/external-code", "value": f"iso3166-1-alpha3:{cc.upper()}"},
            {"pred": "gov.unit/status", "value": "active"},
            {"pred": "gov.unit/sourcing", "value": "representative"},
            {"pred": "gov.unit/provenance", "value": prov},
            {"pred": "gov.unit/last-verified", "value": LAST_VERIFIED},
            {"pred": "gov.unit/verification-status", "value": "unverified-seed"},
        ],
        [],
    )


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

    munis, countries, skipped_synth = [], set(), 0
    for cc in sorted(os.listdir(GOV_DIR)):
        if cc in SKIP_COUNTRY_DIRS or cc == "jpn":
            continue
        f = os.path.join(GOV_DIR, cc, "municipality.ndjson")
        if not os.path.isfile(f):
            continue
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            row = json.loads(line)
            e = project_municipality(cc, row)
            if e is None:
                skipped_synth += 1
                continue
            munis.append(e)
            countries.add(cc)
    country_units = [country_unit(cc) for cc in sorted(countries) if cc not in REAL_COUNTRY_UNITS]
    entities = country_units + munis

    # explicit skip accounting (G5: no silent truncation)
    def _count(tier):
        n = 0
        for cc in os.listdir(GOV_DIR):
            p = os.path.join(GOV_DIR, cc, f"{tier}.ndjson")
            if os.path.isfile(p):
                n += sum(1 for ln in open(p, encoding="utf-8") if ln.strip())
        return n
    print(f"ooyake global ingest — {len(munis)} REAL municipalities across {len(countries)} countries "
          f"+ {len(country_units)} ISO3 country stubs = {len(entities)} units → {GOV_GRAPH}")
    print(f"  SKIPPED (G5, synthetic/out-of-scope, NOT coverage): "
          f"district={_count('district')} ministry={_count('ministry')} office={_count('office')} "
          f"lea={_count('lea')} synthetic-municipality-rows={skipped_synth}; country dirs 0/,intl/ skipped; jpn handled separately")

    token = os.environ.get("KOTOBA_TOKEN") or os.environ.get("KOTOBA_SESSION_POP")
    if not token:
        print("DRY RUN — no KOTOBA_TOKEN. No writes.")
        for e in entities[:5]:
            print(f"  - {e['id']:<40} {e.get('labelJa', e['labelEn'])}")
        print(f"  … ({len(entities)} total)")
        return 0

    rc, written, CHUNK = 0, 0, 80
    for i in range(0, len(entities), CHUNK):
        st, body = post_batch(args.url, entities[i:i + CHUNK], token)
        ok = st == 200 and body.get("ok")
        written += body.get("entityCount", 0) if ok else 0
        print(f"  batch {i//CHUNK+1}/{(len(entities)+CHUNK-1)//CHUNK}: {st} ok={body.get('ok')} "
              f"entityCount={body.get('entityCount')} quadCount={body.get('quadCount')}")
        rc |= 0 if ok else 1
    print(f"==> ingested {written}/{len(entities)} units into {GOV_GRAPH} (all :representative/:unverified-seed). NOT sealing.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
