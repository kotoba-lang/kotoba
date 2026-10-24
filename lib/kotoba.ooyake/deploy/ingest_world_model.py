#!/usr/bin/env python3
"""ooyake 公 — persist the ooyake↔tsumugi WORLD MODEL into a live kotoba node.

ADR-2606021600 §3 (+ ADR-2605262130 kotoba substrate / ADR-2605312345 Datom-first-
class). Sibling of ingest_records.py — same write path, same dry-run/operator gate.

Where ingest_records.py persists the STRUCTURAL atlas (`gov-atlas-v1`), this persists
the JOIN of structure (ooyake `:gov.unit`) and karma (tsumugi `:organism` 縁) into the
named graph `world-model-v1`. It projects ONLY the reconciled, factual world model:
  - one `world.gov` entity per reconciled gov-unit, carrying
      world/organism  → the tsumugi :organism it reconciles to (confirmed | derived)
      world/stewards  → each entity that gov body :tends/:custodies (the gov→entity path)
  - claims world/match (confirmed|derived) + world/sourcing (representative — the 縁
    are tsumugi :representative ties).
PROPOSED / latent links are NOT persisted as facts (they stay in the file artifact
as candidates until an operator applies them — G5/G9). No fabricated coverage.

Write path: POST {url}/xrpc/com.etzhayyim.apps.kotobase.kg.ingest_batch, Bearer token.
Without a token → DRY RUN (project + count, NO writes). NEVER runs `kotoba commit`
(WAL-durable; sealing is the operator's separate cadence). Outward writes operator-
gated (G4/G9).

Usage:
    python3 ingest_world_model.py [--url http://127.0.0.1:8077]          # dry run
    KOTOBA_TOKEN=<bearer> python3 ingest_world_model.py --url http://127.0.0.1:8077
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ACTOR = os.path.normpath(os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_ACTOR, "cells", "world_model"))
from cell import (  # noqa: E402
    load_edges,
    load_gov_units,
    load_organisms,
    reconcile_world_model,
)

# reuse the single-source kotoba write path from ingest_records.py
sys.path.insert(0, _HERE)
from ingest_records import post_batch  # noqa: E402

WORLD_GRAPH = "world-model-v1"


def project_world_model() -> tuple[list[dict], dict]:
    gov = load_gov_units()
    orgs = load_organisms()
    edges = load_edges()
    r = reconcile_world_model(gov, orgs, edges)

    match_of: dict[str, str] = {}
    for c in r["confirmed_links"]:
        match_of[c["unit"]] = "confirmed"
    for d in r["derived_links"]:
        match_of[d["unit"]] = "derived"
    organism_of = {c["unit"]: c["organism"] for c in (r["confirmed_links"] + r["derived_links"])}

    stewards_by_unit: dict[str, list[dict]] = {}
    for s in r["government_stewardship"]:
        stewards_by_unit.setdefault(s["gov_unit"], []).append(s)

    entities: list[dict] = []
    for unit, organism in sorted(organism_of.items()):
        u = gov.get(unit, {})
        relations = [{"pred": "world/organism", "dstId": organism}]
        for s in stewards_by_unit.get(unit, []):
            relations.append({"pred": "world/stewards", "dstId": s["entity"]})
        entities.append({
            "id": unit,
            "type": "world.gov",
            "labelEn": u.get(":gov.unit/name-en") or unit,
            "labelJa": u.get(":gov.unit/name-local") or "",
            "claims": [
                {"pred": "world/match", "value": match_of.get(unit, "confirmed")},
                {"pred": "world/sourcing", "value": "representative"},
            ],
            "relations": relations,
            "extractor": "deploy/ingest_world_model.py",
            "license": "Apache-2.0 + etzhayyim Charter Rider v2.0",
        })
    return entities, r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("KOTOBA_URL", "http://127.0.0.1:8077"))
    args = ap.parse_args()

    entities, r = project_world_model()
    datoms = sum(len(e["claims"]) + len(e["relations"]) + 1 for e in entities)
    paths = len(r["government_stewardship"])
    print(f"ooyake world-model ingest → graph '{WORLD_GRAPH}'")
    print(f"  reconciled gov nodes : {len(entities)} (~{datoms} datoms)")
    print(f"  stewardship paths    : {paths} (world/stewards relations)")
    print(f"  proposed (NOT persisted as facts, file-only): {len(r['proposed_links'])}")

    token = os.environ.get("KOTOBA_TOKEN") or os.environ.get("KOTOBA_SESSION_POP")
    if not token:
        print("DRY RUN — no KOTOBA_TOKEN. Set it (operator bearer) to ingest. No writes performed.")
        for e in entities[:6]:
            print(f"  - {e['id']:<22} → {e['labelEn']}  rels={len(e['relations'])}")
        if len(entities) > 6:
            print(f"  … ({len(entities)} total)")
        return 0

    st, body = post_batch(args.url, WORLD_GRAPH, entities, token)
    ok = st == 200 and body.get("ok")
    print(f"--> {len(entities)} world.gov entities → {WORLD_GRAPH}: {st} ok={body.get('ok')} "
          f"entityCount={body.get('entityCount')} quadCount={body.get('quadCount')}")
    print("==> ingest complete. NOT sealing (WAL-durable; `kotoba commit` is the operator's cadence).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
