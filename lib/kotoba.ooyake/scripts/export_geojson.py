#!/usr/bin/env python3
"""export_geojson.py — derive a world-government GeoJSON from the ooyake atlas.

Reads every `registry/gov-units*.edn`, joins each `:gov.address` that carries lat/lon
to its `:gov.unit`, and writes a GeoJSON FeatureCollection (one Point per geolocated
body) to `wire/viz/gov-atlas.geojson`. Drop it into any map tool / the kami-engine viewer.

Properties per feature: id, name, level, branch, jurisdiction, wikidata, kind, city,
official_url. READ-ONLY over the registry (writes only the viz artifact).

Usage:
    python3 export_geojson.py            # write wire/viz/gov-atlas.geojson
    python3 export_geojson.py --check    # validate only, write to a temp path (CI gate)
"""
from __future__ import annotations

import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "cells", "reconcile")))
from cell import parse_edn  # noqa: E402

_REG = os.path.normpath(os.path.join(_HERE, "..", "registry"))
_OUT = os.path.normpath(os.path.join(_HERE, "..", "viz", "gov-atlas.geojson"))


def build() -> dict:
    units, addrs = {}, []
    for f in sorted(glob.glob(os.path.join(_REG, "gov-units*.edn"))):
        doc = parse_edn(open(f, encoding="utf-8").read())
        for u in doc.get(":units", []):
            if u.get(":gov.unit/id"):
                units[u[":gov.unit/id"]] = u
        addrs.extend(doc.get(":addresses", []))
    feats = []
    for a in addrs:
        lat, lon = a.get(":gov.address/lat"), a.get(":gov.address/lon")
        if lat is None or lon is None:
            continue
        u = units.get(a.get(":gov.address/unit"), {})
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": a.get(":gov.address/unit"),
                "name": u.get(":gov.unit/name-en") or u.get(":gov.unit/name-local"),
                "level": u.get(":gov.unit/level"),
                "branch": u.get(":gov.unit/branch"),
                "jurisdiction": u.get(":gov.unit/jurisdiction"),
                "wikidata": u.get(":gov.unit/wikidata"),
                "kind": a.get(":gov.address/kind"),
                "city": a.get(":gov.address/line-en"),
                "official_url": u.get(":gov.unit/official-url"),
            },
        })
    feats.sort(key=lambda f: (f["properties"]["jurisdiction"] or "", f["properties"]["id"] or ""))
    return {"type": "FeatureCollection",
            "name": "ooyake-gov-atlas",
            "features": feats}


def main() -> int:
    fc = build()
    n = len(fc["features"])
    if "--check" in sys.argv:
        # validate round-trips as JSON; do not touch the committed artifact
        json.loads(json.dumps(fc))
        FLOOR = 4000
        if n < FLOOR:
            print(f"export_geojson: FAIL — only {n} geolocated features (< {FLOOR} floor)")
            return 1
        print(f"export_geojson: OK — {n} geolocated features (valid GeoJSON)")
        return 0
    os.makedirs(os.path.dirname(_OUT), exist_ok=True)
    with open(_OUT, "w", encoding="utf-8") as fh:
        json.dump(fc, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {_OUT} — {n} features")
    return 0


if __name__ == "__main__":
    sys.exit(main())
