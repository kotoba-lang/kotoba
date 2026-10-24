#!/usr/bin/env python3
"""ooyake 公 — ingest the gov-atlas graph + actor profile into a live kotoba node.

ADR-2606021600 (+ ADR-2606013800 for the actor-profile entity, ADR-2606015000 for
the kotoba-server write path). Sibling of 20-actors/himawari/deploy/ingest_records.py.

Reads:
  - registry/gov-units.seed.edn + registry/gov-units.jp-central.seed.edn  → the
    :gov.unit / :gov.address / :gov.window / :gov.form / :gov.procedure / :gov.bpmn
    entities, projected into kotoba KG entities (id + claims + relations) and written
    into the named graph `gov-atlas-v1`.
  - 00-contracts/schemas/actor-profile-seed.kotoba.edn (the `ooyake` seed) → the
    `actor.ooyake` actor-profile entity, written into the default actor graph so the
    node knows ooyake alongside the other registered actors.

Write path: POST {url}/xrpc/com.etzhayyim.apps.kotobase.kg.ingest_batch with a Bearer
token. The operator-local node (127.0.0.1) authorizes on token PRESENCE at this R0
tier (no signature verification — operator-local boundary). Without a token the run
is a DRY RUN (parse + project + count, NO writes) — outward/durable writes are
operator-gated (G4/G9). This script NEVER runs `kotoba commit` (sealing the hot
arrangement is the operator's separate cadence; ingested datoms are WAL-durable
across a normal restart — avoids the partial-ingest+commit head-overwrite hazard).

Usage:
    # dry run (no token): parse + project + count only
    python3 ingest_records.py [--url http://127.0.0.1:8077]

    # live ingest (operator token present)
    KOTOBA_TOKEN=<bearer> python3 ingest_records.py --url http://127.0.0.1:8077
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ACTOR = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_ACTOR, "..", ".."))


# ── minimal EDN reader (maps / vectors / strings / keywords / numbers / comments)
def parse_edn(src: str):
    i, n = 0, len(src)

    def skip():
        nonlocal i
        while i < n:
            c = src[i]
            if c in " \t\r\n,":
                i += 1
                continue
            if c == ";":
                while i < n and src[i] != "\n":
                    i += 1
                continue
            break

    def read():
        nonlocal i
        skip()
        c = src[i]
        if c == '"':
            return read_str()
        if c == "{":
            return read_map()
        if c == "[":
            return read_vec()
        return read_atom()

    def read_str():
        nonlocal i
        i += 1
        out = []
        while i < n:
            c = src[i]
            i += 1
            if c == "\\":
                e = src[i]
                i += 1
                out.append({"n": "\n", "t": "\t", "r": "\r"}.get(e, e))
            elif c == '"':
                return "".join(out)
            else:
                out.append(c)
        raise ValueError("unterminated string")

    def read_vec():
        nonlocal i
        i += 1
        arr = []
        while True:
            skip()
            if src[i] == "]":
                i += 1
                return arr
            arr.append(read())

    def read_map():
        nonlocal i
        i += 1
        d = {}
        while True:
            skip()
            if src[i] == "}":
                i += 1
                return d
            k = read()
            v = read()
            d[k] = v

    def read_atom():
        nonlocal i
        start = i
        while i < n and src[i] not in " \t\r\n,;{}[]\"":
            i += 1
        tok = src[start:i]
        if tok == "true":
            return True
        if tok == "false":
            return False
        if tok == "nil":
            return None
        if tok.startswith(":"):
            return tok
        try:
            return int(tok)
        except ValueError:
            try:
                return float(tok)
            except ValueError:
                return tok

    skip()
    return read()


GOV_GRAPH = "gov-atlas-v1"
ACTOR_GRAPH = "actors-v1"
NSID_INGEST = "com.etzhayyim.apps.kotobase.kg.ingest_batch"

# The FULL committed atlas — every gov-units*.edn (the 3 seeds + g20 / world-* /
# oversight-* / adm1-* / intergov / capitals / hq-locations / …), so an operator
# ingest projects the whole ~7,100-unit atlas into kotoba, not just the seed core.
GOV_SEEDS = sorted(glob.glob(os.path.join(_ACTOR, "registry", "gov-units*.edn")))
ACTOR_SEED = os.path.join(_REPO, "00-contracts", "schemas", "actor-profile-seed.kotoba.edn")

# ref-typed predicates (schema :db.type/ref) — emitted as kg relations (dstId).
_REF_PREDS = {
    "gov.unit/parent",
    "gov.unit/organism",
    "gov.address/unit",
    "gov.window/unit",
    "gov.window/address",
    "gov.window/handles",
    "gov.procedure/owner-unit",
    "gov.procedure/form",
    "gov.procedure/window",
    "gov.procedure/bpmn",
    "gov.form/unit",
    "gov.bpmn/procedure",
}
# section key in the seed map → (namespace, friendly type)
_SECTIONS = [
    (":units", "gov.unit"),
    (":addresses", "gov.address"),
    (":windows", "gov.window"),
    (":forms", "gov.form"),
    (":procedures", "gov.procedure"),
    (":bpmn", "gov.bpmn"),
]


def _strip_kw(v):
    """EDN keyword value (':active') → bare string ('active'); leave others."""
    return v[1:] if isinstance(v, str) and v.startswith(":") else v


def project_gov_entity(ns: str, ent: dict) -> dict | None:
    # parse_edn keeps keyword keys colon-prefixed (':gov.unit/id'); preds are
    # emitted colon-stripped ('gov.unit/id') to match the graph vocabulary.
    id_key = f":{ns}/id"
    ent_id = ent.get(id_key)
    if ent_id is None:
        return None
    name_local = ent.get(f":{ns}/name-local") or ent.get(f":{ns}/title-local")
    name_en = ent.get(f":{ns}/name-en") or ent.get(f":{ns}/title-en") or str(ent_id)
    claims, relations = [], []
    for attr_key, val in ent.items():
        if attr_key == id_key:
            continue
        pred = attr_key[1:] if attr_key.startswith(":") else attr_key
        if pred in _REF_PREDS:
            for v in (val if isinstance(val, list) else [val]):
                relations.append({"pred": pred, "dstId": str(_strip_kw(v))})
        elif isinstance(val, list):
            for v in val:
                claims.append({"pred": pred, "value": str(_strip_kw(v))})
        else:
            claims.append({"pred": pred, "value": str(_strip_kw(val))})
    out = {
        "id": str(ent_id),
        "type": ns,
        "labelEn": str(name_en),
        "claims": claims,
        "relations": relations,
        "extractor": "deploy/ingest_records.py",
        "license": "Apache-2.0 + etzhayyim Charter Rider v2.0",
    }
    if name_local:
        out["labelJa"] = str(name_local)
    return out


def project_actor_entity(seed_map: dict) -> dict | None:
    for rec in seed_map.get(":seed", []):
        if rec.get(":actor/handle") == "ooyake":
            claims = []
            for attr, val in rec.items():
                if attr in (":actor/service", ":actor/vm"):
                    claims.append({"pred": f"actor/{attr.split('/')[1]}-json",
                                   "value": json.dumps(val, ensure_ascii=False)})
                elif isinstance(val, list):
                    for v in val:
                        claims.append({"pred": f"actor/{attr.split('/')[1]}", "value": str(_strip_kw(v))})
                else:
                    claims.append({"pred": f"actor/{attr.split('/')[1]}", "value": str(_strip_kw(val))})
            return {
                "id": "actor.ooyake",
                "type": "actor-profile",
                "labelEn": "Ooyake — World Government Atlas (civic wayfinding map)",
                "labelJa": "公 — 全世界政府アトラス (市民導線マップ)",
                "claims": claims,
                "relations": [],
                "extractor": "deploy/ingest_records.py",
                "license": "Apache-2.0 + etzhayyim Charter Rider v2.0",
            }
    return None


def load_gov_entities() -> list[dict]:
    ents: list[dict] = []
    seen: set[str] = set()
    for f in GOV_SEEDS:
        doc = parse_edn(open(f, encoding="utf-8").read())
        for sect, ns in _SECTIONS:
            for ent in doc.get(sect, []):
                proj = project_gov_entity(ns, ent)
                if proj and proj["id"] not in seen:
                    seen.add(proj["id"])
                    ents.append(proj)
    return ents


def post_batch(url: str, graph: str | None, entities: list[dict], token: str) -> tuple[int, dict]:
    body: dict = {"entities": entities}
    if graph:
        body["graph"] = graph
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{url}/xrpc/{NSID_INGEST}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            payload = {"error": str(e)}
        return e.code, payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("KOTOBA_URL", "http://127.0.0.1:8077"))
    args = ap.parse_args()

    gov = load_gov_entities()
    actor = project_actor_entity(parse_edn(open(ACTOR_SEED, encoding="utf-8").read()))
    by_type: dict[str, int] = {}
    for e in gov:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    gov_datoms = sum(len(e["claims"]) + len(e["relations"]) + 1 for e in gov)
    print(f"ooyake ingest — gov-atlas: {len(gov)} entities (~{gov_datoms} datoms) {by_type}")
    print(f"               actor-profile: {'actor.ooyake' if actor else 'MISSING'}")

    token = os.environ.get("KOTOBA_TOKEN") or os.environ.get("KOTOBA_SESSION_POP")
    if not token:
        print("DRY RUN — no KOTOBA_TOKEN. Set it (operator bearer) to ingest. No writes performed.")
        for e in gov[:5]:
            print(f"  - {e['type']:<14} {e['id']:<32} claims={len(e['claims'])} rels={len(e['relations'])}")
        print(f"  … ({len(gov)} total)")
        return 0

    rc = 0
    if actor:
        st, body = post_batch(args.url, ACTOR_GRAPH, [actor], token)
        ok = st == 200 and body.get("ok")
        print(f"--> actor.ooyake → {ACTOR_GRAPH}: {st} ok={body.get('ok')} quads={body.get('quadCount')}")
        rc |= 0 if ok else 1
    st, body = post_batch(args.url, GOV_GRAPH, gov, token)
    ok = st == 200 and body.get("ok")
    print(f"--> {len(gov)} gov entities → {GOV_GRAPH}: {st} ok={body.get('ok')} "
          f"entityCount={body.get('entityCount')} quadCount={body.get('quadCount')}")
    rc |= 0 if ok else 1
    print("==> ingest complete. NOT sealing (no `kotoba commit`): datoms are WAL-durable; "
          "sealing to IPFS cold tier is the operator's separate cadence (avoids iter-8 partial-commit hazard).")
    return rc


if __name__ == "__main__":
    sys.exit(main())
