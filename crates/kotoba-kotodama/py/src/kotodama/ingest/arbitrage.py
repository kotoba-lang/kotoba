"""Arbitrage signal business logic for Zeebe workers.

This module owns the logic formerly implemented in the ``arb.etzhayyim.com``
Cloudflare Worker. The Worker is now an edge facade that forwards XRPC to the
BPMN dispatcher.
"""

from __future__ import annotations

import json
import math
import os
import random
import string
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:arb.etzhayyim.com"
DISCLAIMER = "Educational signal. Not advice. No execution."
ASSET_CLASSES = {"eq", "fut", "fx", "com", "re", "cr"}
STOOQ_SYMBOLS: dict[str, list[str]] = {
    "eq": ["spy.us", "qqq.us", "dia.us", "iwm.us", "efa.us", "eem.us", "vgk.us", "ewj.us", "fxi.us", "vti.us"],
    "fut": ["gc.f", "si.f", "cl.f", "ng.f", "zw.f", "zc.f"],
    "com": ["gld.us", "slv.us", "uso.us", "ung.us", "weat.us", "corn.us", "soyb.us"],
    "re": ["vnq.us", "iyr.us", "xlre.us", "reet.us", "usrt.us"],
}
BINANCE_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT", "AVAXUSDT", "MATICUSDT"]





def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _float(value: Any, default: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _gen_id(prefix: str) -> str:
    ticks = base36(int(time.time() * 1000))
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return f"{prefix}{ticks}{suffix}"[:14]


def base36(n: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return "0"
    out = ""
    while n:
        n, rem = divmod(n, 36)
        out = chars[rem] + out
    return out


def quote_vid(owner_did: str, venue: str, symbol: str, ts: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in f"{venue}-{symbol}-{ts}")
    return f"at://{owner_did}/com.etzhayyim.apps.arb.quote/{safe}"


def proposal_vid(owner_did: str, proposal_id: str) -> str:
    return f"at://{owner_did}/com.etzhayyim.apps.arb.proposal/{proposal_id}"





def _http_json(url: str, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, headers={"accept": "application/json", "user-agent": "etzhayyim-arb-zeebe/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_text(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers={"accept": "text/csv,*/*", "user-agent": "etzhayyim-arb-zeebe/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def ingest_quote(args: dict[str, Any]) -> dict[str, Any]:
    asset_class = _str(args.get("assetClass"))
    venue = _str(args.get("venue"))
    symbol = _str(args.get("symbol"))
    ts = _str(args.get("ts"))
    mid = _float(args.get("mid"))
    if asset_class not in ASSET_CLASSES or not venue or not symbol or not ts or not math.isfinite(mid):
        return {"ok": False, "error": "InvalidRequest", "message": "assetClass/venue/symbol/ts/mid required"}

    owner = f"{_str(args.get('primaryDid') or OWNER_DID)}:scout"
    vid = quote_vid(owner, venue, symbol, ts)
    created_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vid,
        "created_date": created_at[:10],
        "sensitivity_ord": 1,
        "owner_did": owner,
        "asset_class": asset_class,
        "venue": venue,
        "symbol": symbol,
        "ts": ts,
        "bid": None if not math.isfinite(_float(args.get("bid"))) else _float(args.get("bid")),
        "ask": None if not math.isfinite(_float(args.get("ask"))) else _float(args.get("ask")),
        "mid": mid,
        "currency": _str(args.get("currency")),
        "src_url": _str(args.get("srcUrl")),
        "created_at": created_at,
        "org_id": _str(args.get("orgId") or "anon"),
        "user_id": _str(args.get("userId") or "anon"),
        "actor_id": "sys.arb.scout",
    }
    client.insert_row("vertex_arb_quote", row_dict)
    return {"ok": True, "vertexId": vid, "ts": ts}


def detect_spread(asset_class: str, min_spread_bps: float = 20) -> dict[str, Any]:
    if asset_class not in ASSET_CLASSES:
        return {"ok": False, "error": "InvalidAssetClass"}
    client = get_kotoba_client()
    rows = client.select_where(
        "vertex_arb_quote",
        "asset_class",
        asset_class,
        columns=["venue", "symbol", "mid", "ts", "currency"],
        limit=2000,
    )  # R0: Order by and limit handled in Python
    # Sort by ts DESC in Python
    rows.sort(key=lambda r: r["ts"], reverse=True)

    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row['venue']}:{row['symbol']}"
        latest.setdefault(key, row)

    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in latest.values():
        by_symbol.setdefault(row['symbol'], []).append(row)

    candidates: list[dict[str, Any]] = []
    for items in by_symbol.values():
        for i, a in enumerate(items):
            for b in items[i + 1 :]:
                ma = _float(a["mid"])
                mb = _float(b["mid"])
                if not math.isfinite(ma) or not math.isfinite(mb) or ma <= 0 or mb <= 0:
                    continue
                bps = round(((mb - ma) / ma) * 10_000)
                if abs(bps) < min_spread_bps:
                    continue
                long_leg = f"{a['venue']}:{a['symbol']}" if bps > 0 else f"{b['venue']}:{b['symbol']}"
                short_leg = f"{b['venue']}:{b['symbol']}" if bps > 0 else f"{a['venue']}:{a['symbol']}"
                candidates.append(
                    {
                        "legA": long_leg,
                        "legB": short_leg,
                        "spreadBps": abs(bps),
                        "edgeBps": max(0, abs(bps) - 10),
                        "rationale": f"same-symbol cross-venue mid spread ({a['ts']}/{b['ts']})",
                    }
                )
    candidates.sort(key=lambda c: c["edgeBps"], reverse=True)
    return {"ok": True, "candidates": candidates[:50]}


def propose_trade(args: dict[str, Any]) -> dict[str, Any]:
    asset_class = _str(args.get("assetClass"))
    leg_a = _str(args.get("legA"))
    leg_b = _str(args.get("legB"))
    spread_bps = round(_float(args.get("spreadBps"), 0))
    edge_bps = round(_float(args.get("edgeBps"), 0))
    if asset_class not in ASSET_CLASSES or not leg_a or not leg_b or spread_bps <= 0:
        return {"ok": False, "error": "InvalidRequest", "message": "assetClass/legA/legB/spreadBps required"}
    primary = _str(args.get("primaryDid") or OWNER_DID)
    owner = f"{primary}:{asset_class}"
    proposal_id = _gen_id("p")
    vid = proposal_vid(owner, proposal_id)
    created_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    expires_at_dt = datetime.fromisoformat(
        _str(args.get("expiresAt"))
    ) if args.get("expiresAt") else datetime.now(timezone.utc) + timedelta(minutes=30)
    expires_at = expires_at_dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
    org_id = _str(args.get("orgId") or "anon")
    user_id = _str(args.get("userId") or "anon")
    actor_id = f"sys.arb.{asset_class}"

    client = get_kotoba_client()
    proposal_row_dict = {
        "vertex_id": vid,
        "created_date": created_at[:10],
        "sensitivity_ord": 1,
        "owner_did": owner,
        "proposal_id": proposal_id,
        "asset_class": asset_class,
        "leg_a": leg_a,
        "leg_b": leg_b,
        "spread_bps": spread_bps,
        "edge_bps": edge_bps,
        "confidence": max(0, min(1, _float(args.get("confidence"), 0.5))),
        "rationale": _str(args.get("rationale")),
        "expires_at": expires_at,
        "executed": False,
        "created_at": created_at,
        "org_id": org_id,
        "user_id": user_id,
        "actor_id": actor_id,
    }
    client.insert_row("vertex_arb_proposal", proposal_row_dict)

    for side, leg in (("long", leg_a), ("short", leg_b)):
        edge_id = f"edge:{proposal_id}:{side}"
        edge_row_dict = {
            "edge_id": edge_id,
            "created_date": created_at[:10],
            "sensitivity_ord": 1,
            "owner_did": owner,
            "src_vid": vid,
            "dst_vid": leg,
            "side": side,
            "created_at": created_at,
            "org_id": org_id,
            "user_id": user_id,
            "actor_id": actor_id,
        }
        client.insert_row("edge_arb_proposal_leg", edge_row_dict)
    return {"ok": True, "proposalId": proposal_id, "uri": vid, "disclaimer": _str(args.get("disclaimer") or DISCLAIMER)}


def score_proposal(proposal_id: str, model: str = "heuristic-v1") -> dict[str, Any]:
    if not proposal_id:
        return {"ok": False, "error": "InvalidRequest", "message": "proposalId required"}
    client = get_kotoba_client()
    row = client.select_first_where(
        "vertex_arb_proposal",
        "proposal_id",
        proposal_id,
        columns=["edge_bps", "spread_bps", "confidence"],
    )
    if row is None:
        return {"ok": False, "error": "NotFound", "message": proposal_id}
    edge_factor = max(0, min(1, _float(row["edge_bps"], 0) / 200))
    spread_factor = max(0, min(1, _float(row["spread_bps"], 0) / 300))
    conf_factor = _float(row["confidence"], 0.5)
    score = round(0.5 * edge_factor + 0.3 * spread_factor + 0.2 * conf_factor, 4)
    risk_notes = (
        "low edge or low confidence; treat as noise"
        if score < 0.4
        else "moderate edge; verify frictions before sharing"
        if score < 0.7
        else "strong cross-venue dislocation; check borrow / FX leg / venue halt"
    )
    owner = f"{OWNER_DID}:judge"
    vid = f"at://{owner}/com.etzhayyim.apps.arb.score/{proposal_id}"
    created_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    score_row_dict = {
        "vertex_id": vid,
        "created_date": created_at[:10],
        "sensitivity_ord": 1,
        "owner_did": owner,
        "proposal_id": proposal_id,
        "score": score,
        "risk_notes": risk_notes,
        "llm_model": model,
        "created_at": created_at,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": "sys.arb.judge",
    }
    client.insert_row("vertex_arb_score", score_row_dict)
    return {"ok": True, "score": score, "riskNotes": risk_notes, "model": model}


def publish_proposal(proposal_id: str, mention_cohort: str = "trader.etzhayyim.com", disclaimer: str = DISCLAIMER) -> dict[str, Any]:
    if not proposal_id:
        return {"ok": False, "error": "InvalidRequest", "message": "proposalId required"}
    client = get_kotoba_client()
    # R0: Multi-table join requires q() Datalog escape hatch
    query_edn = """
    [:find ?asset_class ?leg_a ?leg_b ?spread_bps ?edge_bps ?score
     :in $ ?proposal_id
     :where
     [?p :vertex/type :vertex_arb_proposal]
     [?p :proposal_id ?proposal_id]
     [?p :asset_class ?asset_class]
     [?p :leg_a ?leg_a]
     [?p :leg_b ?leg_b]
     [?p :spread_bps ?spread_bps]
     [?p :edge_bps ?edge_bps]
     (or
      (and [?s :vertex/type :vertex_arb_score]
           [?s :proposal_id ?proposal_id]
           [?s :score ?score])
      (not [?s :proposal_id ?proposal_id]))]
    """
    rows = client.q(query_edn, (proposal_id,))
    row = (
        {
            "asset_class": r[0],
            "leg_a": r[1],
            "leg_b": r[2],
            "spread_bps": r[3],
            "edge_bps": r[4],
            "score": r[5],
        }
        for r in rows
    )
    row = next(row, None) # Get the first (and only) result

    if row is None:
        return {"ok": False, "error": "NotFound", "message": proposal_id}
    if row["score"] is None or _float(row["score"], 0) < 0.5:
        return {"ok": False, "error": "BelowThreshold", "message": "score < 0.5; skip publication"}
    text = "\n".join(
        [
            f"Arb signal [{row['asset_class']}] long {row['leg_a']} / short {row['leg_b']}",
            f"spread {row['spread_bps']}bps | edge {row['edge_bps']}bps | score {row['score']}",
            f"@{mention_cohort} - {disclaimer}",
        ]
    )
    post_uri = _pds_post(text)
    owner = f"{OWNER_DID}:herald"
    vid = f"at://{owner}/com.etzhayyim.apps.arb.publication/{proposal_id}"
    created_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    publication_row_dict = {
        "vertex_id": vid,
        "created_date": created_at[:10],
        "sensitivity_ord": 1,
        "owner_did": owner,
        "proposal_id": proposal_id,
        "post_uri": post_uri,
        "mentions": mention_cohort,
        "disclaimer": disclaimer,
        "created_at": created_at,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": "sys.arb.herald",
    }
    client.insert_row("vertex_arb_publication", publication_row_dict)
    return {"ok": True, "postUri": post_uri, "mentions": [mention_cohort]}


def _pds_post(text: str) -> str:
    from kotodama.primitives.yoro_social import build_repo_record, insert_social_post_record

    record = {"$type": "app.bsky.feed.post", "text": text, "createdAt": now_iso()}
    row = build_repo_record(repo=f"{OWNER_DID}:herald", collection="app.bsky.feed.post", record=record)
    try:
        result = insert_social_post_record(row, flush=False)
        return _str(result.get("uri") or "")
    except Exception as e:  # noqa: BLE001
        return f"error:pds:{e}"


def scout_quotes(asset_class: str) -> dict[str, Any]:
    if asset_class not in ASSET_CLASSES:
        return {"ok": False, "error": "InvalidAssetClass"}
    owner = f"{OWNER_DID}:scout"
    ts = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    count = 0
    if asset_class == "cr":
        pair_set = set(BINANCE_PAIRS)
        spot_params = urllib.parse.urlencode({"symbols": json.dumps(BINANCE_PAIRS)})
        spot = _http_json(f"https://api.binance.com/api/v3/ticker/price?{spot_params}", 10)
        fut = _http_json("https://fapi.binance.com/fapi/v1/ticker/price", 10)
        for venue, items in (("binance-spot", spot), ("binance-fut", [d for d in fut if d.get("symbol") in pair_set])):
            for item in items:
                mid = _float(item.get("price"))
                if not math.isfinite(mid) or mid <= 0:
                    continue
                ingest_quote({"assetClass": "cr", "venue": venue, "symbol": item["symbol"].replace("USDT", "").lower(), "ts": ts, "mid": mid, "currency": "USD", "srcUrl": "https://api.binance.com" if venue == "binance-spot" else "https://fapi.binance.com", "primaryDid": OWNER_DID})
                count += 1
        return {"ok": True, "count": count, "assetClass": asset_class, "source": "binance-spot+fut", "ts": ts}
    if asset_class == "fx":
        data = _http_json("https://api.frankfurter.app/latest?base=USD", 10)
        rate_ts = f"{data.get('date') or ts[:10]}T00:00:00Z"
        for currency, rate in (data.get("rates") or {}).items():
            rate_f = _float(rate)
            if not math.isfinite(rate_f) or rate_f <= 0:
                continue
            ingest_quote({"assetClass": "fx", "venue": "frankfurter", "symbol": f"USD{currency}", "ts": rate_ts, "mid": 1 / rate_f, "currency": currency, "srcUrl": "https://api.frankfurter.app", "primaryDid": OWNER_DID})
            count += 1
        return {"ok": True, "count": count, "assetClass": asset_class, "source": "frankfurter", "ts": ts}
    for symbol in STOOQ_SYMBOLS.get(asset_class, []):
        try:
            csv = _http_text(f"https://stooq.com/q/l/?s={urllib.parse.quote(symbol)}&f=sd2t2ohlcv&h&e=csv", 10)
            parts = (csv.strip().splitlines()[1] if len(csv.strip().splitlines()) > 1 else "").split(",")
            close = _float(parts[6] if len(parts) > 6 else None)
            if not math.isfinite(close) or close <= 0:
                continue
            date = parts[1] if len(parts) > 1 else ""
            clock = parts[2] if len(parts) > 2 else "00:00:00"
            row_ts = f"{date}T{clock}Z" if date else ts
            ingest_quote({"assetClass": asset_class, "venue": "stooq", "symbol": symbol.upper().replace(".US", "").replace(".F", "=F"), "ts": row_ts, "mid": close, "currency": "USD", "srcUrl": "https://stooq.com", "primaryDid": OWNER_DID})
            count += 1
        except Exception:
            continue
    return {"ok": True, "count": count, "assetClass": asset_class, "source": "stooq", "ts": ts}


def list_proposals(limit: int = 50, offset: int = 0, min_edge_bps: float = 20, asset_class: str = "") -> dict[str, Any]:
    client = get_kotoba_client()
    # R0: Datalog escape hatch for multi-predicate WHERE, ORDER BY, LIMIT, OFFSET
    # LIMIT and OFFSET are applied in Python. ORDER BY is applied in Python.

    query_edn_parts = [
        "[:find ?vertex_id ?proposal_id ?asset_class ?leg_a ?leg_b ?spread_bps ?edge_bps ?confidence ?expires_at ?score ?risk_notes",
        " :in $ ?min_edge_bps",
    ]
    query_params: list[Any] = [min_edge_bps]
    where_clauses = [
        "[?p :vertex/type :vertex_arb_proposal]",
        "[?p :vertex_id ?vertex_id]",
        "[?p :proposal_id ?proposal_id]",
        "[?p :asset_class ?asset_class]",
        "[?p :leg_a ?leg_a]",
        "[?p :leg_b ?leg_b]",
        "[?p :spread_bps ?spread_bps]",
        "[?p :edge_bps ?edge_bps]",
        "(>= ?edge_bps ?min_edge_bps)",
        "[?p :confidence ?confidence]",
        "[?p :expires_at ?expires_at]",
        """(or
            (and [?s :vertex/type :vertex_arb_score]
                 [?s :proposal_id ?proposal_id]
                 [?s :score ?score]
                 [?s :risk_notes ?risk_notes])
            (not [?s :proposal_id ?proposal_id]
                 [(nil) ?score]
                 [(nil) ?risk_notes]))""",
    ]

    if asset_class:
        query_edn_parts[1] += " ?asset_class_param"
        where_clauses.append("[?p :asset_class ?asset_class_param]")
        query_params.append(asset_class)

    query_edn_parts.append(" :where")
    query_edn_parts.extend(where_clauses)
    query_edn_parts.append("]")
    query_edn = "\n".join(query_edn_parts)

    rows = client.q(query_edn, tuple(query_params))

    # Convert to list of dicts for easier processing
    cols = ["vertex_id", "proposal_id", "asset_class", "leg_a", "leg_b", "spread_bps", "edge_bps",
            "confidence", "expires_at", "score", "risk_notes"]
    proposals_data = [dict(zip(cols, r)) for r in rows]

    # Apply ORDER BY, LIMIT, OFFSET in Python
    proposals_data.sort(key=lambda x: x["edge_bps"], reverse=True)
    total_proposals = len(proposals_data)
    proposals_data = proposals_data[offset : offset + limit]

    proposals = [
        {
            "vertex_id": r["vertex_id"],
            "proposal_id": r["proposal_id"],
            "asset_class": r["asset_class"],
            "leg_a": r["leg_a"],
            "leg_b": r["leg_b"],
            "spread_bps": r["spread_bps"],
            "edge_bps": r["edge_bps"],
            "confidence": r["confidence"],
            "expires_at": r["expires_at"],
            "score": r["score"],
            "risk_notes": r["risk_notes"],
        }
        for r in proposals_data
    ]
    return {"ok": True, "proposals": proposals, "total": total_proposals, "offset": offset, "limit": limit}


def get_proposal(proposal_id: str) -> dict[str, Any]:
    if not proposal_id:
        return {"ok": False, "error": "InvalidRequest", "message": "proposalId required"}
    client = get_kotoba_client()
    proposal = client.select_first_where("vertex_arb_proposal", "proposal_id", proposal_id)
    if proposal is None:
        return {"ok": False, "error": "NotFound", "message": proposal_id}
    score = client.select_first_where("vertex_arb_score", "proposal_id", proposal_id)
    publication = client.select_first_where("vertex_arb_publication", "proposal_id", proposal_id)
    return {"ok": True, "proposal": proposal, "score": score, "publication": publication}
