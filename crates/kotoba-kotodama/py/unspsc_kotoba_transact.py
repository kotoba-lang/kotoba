#!/usr/bin/env python3
"""Open-UNSPSC fleet → kotoba Datomic registry (ADR-2605171300; mirrors kabuto/ipaddress).

Scans the per-code generative-agent definitions (langgraph_graphs/unispsc_agents/c*.py),
extracts code→title, and registers UNSPSC SEGMENTS + a representative set of COMMODITY
codes (each with its did:web:etzhayyim.com:actor:c<code> identity) into a running kotoba
node's Datom log via POST /xrpc/com.etzhayyim.apps.kotoba.datomic.transact. This makes the
commodity fleet queryable as first-class Datomic entities (supersedes the NDJSON post-sink
as the commodity system-of-record; ADR-2605240100 keeps social egress).

AUTH (ADR-2605231525): a write needs an operator JWT (KOTOBA_TOKEN, sub == operator_did)
or a datom:transact CACAO. Without either it is a DRY RUN.

stdlib only. Usage:
    python3 unspsc_kotoba_transact.py                          # dry-run (segments + 8/seg)
    python3 unspsc_kotoba_transact.py --graph <CID> --per-seg 8   # live save
    python3 unspsc_kotoba_transact.py --graph <CID> --all         # full 18,342-code fleet
"""
from __future__ import annotations
import sys
import os
import re
import json
import pathlib
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
AGENTS = HERE / "src" / "kotodama" / "langgraph_graphs" / "unispsc_agents"
SCHEMA = HERE.parent.parent.parent / "00-contracts" / "schemas" / "unspsc-ontology.kotoba.edn"
NSID_TRANSACT = "com.etzhayyim.apps.kotoba.datomic.transact"
BATCH = 3500
_TITLE_RE = re.compile(r'TITLE\s*=\s*"([^"]*)"')


def edn_str(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def harvest(per_seg: int, take_all: bool):
    """Return (segment dict code2→title, list of (code, title)) representative set."""
    seg_title, picked, seg_count = {}, [], {}
    for f in sorted(AGENTS.glob("c*.py")):
        code = f.stem[1:]
        if len(code) < 2 or not code.isdigit():
            continue
        m = _TITLE_RE.search(f.read_text(encoding="utf-8", errors="replace"))
        title = m.group(1) if m else code
        s = code[:2]
        seg_title.setdefault(s, title)
        if take_all or seg_count.get(s, 0) < per_seg:
            picked.append((code, title))
            seg_count[s] = seg_count.get(s, 0) + 1
    return seg_title, picked


def rows_to_datoms(seg_title, picked):
    d = []
    for s, title in sorted(seg_title.items()):
        e = f"seg.{s}"
        d.append(f"[:db/add {edn_str(e)} :unspsc.seg/id {edn_str(e)}]")
        d.append(f"[:db/add {edn_str(e)} :unspsc.seg/code {edn_str(s)}]")
        d.append(f"[:db/add {edn_str(e)} :unspsc.seg/title {edn_str(title)}]")
        d.append(f"[:db/add {edn_str(e)} :unspsc.seg/sourcing :representative]")
    for code, title in picked:
        d.append(f"[:db/add {edn_str(code)} :unspsc/id {edn_str(code)}]")
        d.append(f"[:db/add {edn_str(code)} :unspsc/code {edn_str(code)}]")
        d.append(f"[:db/add {edn_str(code)} :unspsc/title {edn_str(title)}]")
        d.append(f"[:db/add {edn_str(code)} :unspsc/segment {edn_str('seg.' + code[:2])}]")
        d.append(f"[:db/add {edn_str(code)} :unspsc/did {edn_str('did:web:etzhayyim.com:actor:c' + code)}]")
        d.append(f"[:db/add {edn_str(code)} :unspsc/agent true]")
        d.append(f"[:db/add {edn_str(code)} :unspsc/sourcing :representative]")
    return d


def schema_datoms():
    txt = SCHEMA.read_text(encoding="utf-8")
    # extract each {:db/ident ...} attribute map, drop :db/doc (has '|')
    out = []
    for blk in re.findall(r'\{:db/ident[^}]*\}', txt):
        blk = re.sub(r'\s*:db/doc\s*"(?:[^"\\]|\\.)*"', "", blk)
        out.append(re.sub(r'\s+', " ", blk).strip())
    return out


def _tx(datoms):
    return "[\n " + "\n ".join(datoms) + "\n]"


def _post(url, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    tok = os.environ.get("KOTOBA_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (own node)
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        t = e.read().decode() or ""
        try:
            return e.code, json.loads(t)
        except json.JSONDecodeError:
            return e.code, {"error": t[:160]}


def main(argv):
    url = os.environ.get("KOTOBA_URL", "http://127.0.0.1:8077")
    graph = argv[argv.index("--graph") + 1] if "--graph" in argv else os.environ.get("UNSPSC_GRAPH_CID")
    per_seg = int(argv[argv.index("--per-seg") + 1]) if "--per-seg" in argv else 8
    take_all = "--all" in argv

    seg_title, picked = harvest(per_seg, take_all)
    schema = schema_datoms()
    data = rows_to_datoms(seg_title, picked)
    batches = [data[i:i + BATCH] for i in range(0, len(data), BATCH)] or [[]]
    print(f"unspsc.transact: graph={graph or '(unset)'}")
    print(f"  segments: {len(seg_title)} · commodity codes: {len(picked)}"
          f"{' (FULL FLEET)' if take_all else f' ({per_seg}/segment representative)'}")
    print(f"  schema: {len(schema)} attrs · data: {len(data)} datoms in {len(batches)} batch(es)")

    live = bool(graph) and bool(os.environ.get("KOTOBA_TOKEN")) and "--dry-run" not in argv
    if not live:
        print("  DRY RUN — provide --graph <CID> + KOTOBA_TOKEN operator JWT to write.")
        return 0

    st, resp = _post(f"{url}/xrpc/{NSID_TRANSACT}", {"graph": graph, "tx_edn": _tx(schema)})
    print(f"  schema → {st} datom_count={resp.get('datom_count', resp.get('error', '?'))}")
    for i, b in enumerate(batches, 1):
        st, resp = _post(f"{url}/xrpc/{NSID_TRANSACT}", {"graph": graph, "tx_edn": _tx(b)})
        if st != 200:
            print(f"!! data[{i}/{len(batches)}] → {st}: {resp}", file=sys.stderr)
            return 1
        print(f"  ok data[{i}/{len(batches)}]: datom_count={resp.get('datom_count', '?')}")
    print(f"  ✓ {len(seg_title)} segments + {len(picked)} commodity codes committed to {graph}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
