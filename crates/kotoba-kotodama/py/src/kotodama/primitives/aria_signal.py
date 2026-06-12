"""ARIA protocol signal ingestion + minimax computation primitives.

ARIA = Attention × Request × Influence × Affect (emotion) + Market + Money.

External internet signal ingestion and minimax computation layer for the
Well-Becoming objective function (ADR-2604291800).

Pyzeebe task types registered via register():
  aria.attention.ingest      — AT Protocol vertex_repo_record entropy
  aria.request.ingest        — recent XRPC collection distribution H
  aria.market.delta.ingest   — CoinGecko public price/24h-change delta
  aria.money.flow.ingest     — Blockchain.info on-chain volume flow
  aria.emotion.ingest        — vertex_actor_wellbecoming_profile risk cluster
  aria.influence.ingest      — edge_follows top-100 distribution H
  aria.minimax.sweep         — Von Neumann minimax over all signal etas
  aria.reverse.topo.replan   — reverse-topo-sort by propagation DAG order

ADR-2604291800 (Well-Becoming Spirit objective function).
ADR-0056 (BPMN-as-actor).
psycopg3 LIMIT rule: always use LIMIT {int(n)} f-string, never LIMIT %s param.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import hashlib
import json
import logging
import math
import os
import time
import urllib.error
import urllib.request
from typing import Any


LOG = logging.getLogger("aria.signal")

# ── Constants ──────────────────────────────────────────────────────────────────

AXIS_WEIGHTS: dict[str, float] = {
    "emotion":    1.55,
    "attention":  1.45,
    "request":    1.35,
    "market":     1.35,
    "money":      1.45,
    "influence":  1.80,
}

_ACTION_CANDIDATES: list[str] = [
    "post_content",
    "ingest_data",
    "connect_actors",
    "expand_coverage",
    "update_market",
]

# Propagation DAG order for reverse-topo-sort (leaf → root)
_TOPO_ORDER: list[str] = [
    "emotion",
    "attention",
    "request",
    "market",
    "money",
    "influence",
]

_HTTP_TIMEOUT = 15
_USER_AGENT = "aria-signal/1 (+https://etzhayyim.com)"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _now_ts() -> str:
    """UTC timestamp with timezone suffix for TIMESTAMPTZ columns."""
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S") + "+00:00"


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _shannon_h(counts: list[int | float]) -> float:
    """Shannon entropy H = -Σ p·log2(p) over a list of counts."""
    total = sum(counts)
    if total <= 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return -sum(p * math.log2(p) for p in probs)


def _eta(h: float, n: int) -> float:
    """Normalised entropy η = H / H_max where H_max = log2(max(n, 2))."""
    h_max = math.log2(max(n, 2))
    if h_max <= 0:
        return 0.0
    return min(1.0, h / h_max)


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def _table_not_found(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "does not exist" in msg
        or "table not found" in msg
        or "not exist" in msg
        or "undefined table" in msg
    )


# ── U_total (ADR-2604291800) ──────────────────────────────────────────────────

def _u_total(etas: dict[str, float]) -> float:
    u_s = (etas.get("emotion", 0.5) + etas.get("money", 0.5) + etas.get("influence", 0.5)) / 3
    u_w = (etas.get("attention", 0.5) + etas.get("request", 0.5) + etas.get("influence", 0.5)) / 3
    u_f = (etas.get("emotion", 0.5) + etas.get("attention", 0.5)) / 2
    u_b = (etas.get("market", 0.5) + etas.get("money", 0.5) + etas.get("request", 0.5)) / 3
    return u_s * u_w * u_f * u_b


# ── Task 1: attention ingest ──────────────────────────────────────────────────

def task_aria_attention_ingest(**kwargs: Any) -> dict[str, Any]:
    """Fetch attention signals from AT Protocol vertex_repo_record.

    Computes Shannon H over recent record collection distribution.
    Inserts into vertex_signal_attention.

    BPMN: aria/ariaSignalIngest.bpmn → Task_AttentionIngest
    """
    now = _now_ts()
    vertex_id = _stable_id("aria-attn", now[:16])

    # Source 1: AT Protocol record collection distribution (last 1h)
    # 10s timeout: vertex_repo_record (15M rows) times out at 120s without index.
    # On timeout, handler falls back to default eta=0.5 and still inserts the row.
    counts: dict[str, int] = {}
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q("SET statement_timeout = '10s'")
            _res = client.q(
                f"""SELECT collection, COUNT(*) AS cnt
                    FROM vertex_repo_record
                    WHERE ts_ms > (EXTRACT(EPOCH FROM NOW()) * 1000 - 3600000)
                    GROUP BY collection
                    ORDER BY cnt DESC
                    LIMIT {int(50)}"""
            )
            rows = _res
        for collection, cnt in rows:
            counts[str(collection)] = int(cnt or 0)
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.attention: vertex_repo_record not found: %s", exc)
        else:
            LOG.warning("aria.attention: DB query failed: %s", exc)

    count_values = list(counts.values())
    total = sum(count_values)
    h = _shannon_h(count_values) if count_values else 0.5
    n = len(count_values)
    eta_val = _eta(h, n) if n > 0 else 0.5
    magnitude = (max(count_values) / total) if total > 0 else 0.5
    valence = 1.0 if total > 100 else 0.5

    # Source 2: Google Trends (if key configured — skip otherwise)
    google_trends_note = "skipped"
    if os.environ.get("GOOGLE_TRENDS_KEY"):
        try:
            _fetch_json(
                "https://trends.googleapis.com/trends/api/realtimetrends"
                "?hl=en-US&tz=0&cat=all&fi=0&fs=0&ri=300&rs=20&geo=US"
            )
            google_trends_note = "fetched"
        except Exception as exc:
            LOG.warning("aria.attention: google trends fetch failed (non-critical): %s", exc)
            google_trends_note = f"error:{str(exc)[:80]}"

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "DELETE FROM vertex_signal_attention WHERE vertex_id = %s",
                (vertex_id,),
            )
            _res = client.q(
                """INSERT INTO vertex_signal_attention
                   (vertex_id, signal_axis, source, magnitude, valence,
                    entropy_h, eta, sample_count, metadata_json, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    vertex_id,
                    "attention",
                    "vertex_repo_record",
                    magnitude,
                    valence,
                    h,
                    eta_val,
                    n,
                    json.dumps({"google_trends": google_trends_note,
                                "top_collections": list(counts.keys())[:5]}),
                    now,
                ),
            )
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.attention: vertex_signal_attention not found, skipping insert: %s", exc)
            return {"ok": True, "skipped": True, "reason": "table not found",
                    "signal": "attention", "eta": eta_val}
        LOG.warning("aria.attention: insert failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300],
                "signal": "attention", "eta": eta_val}

    LOG.info("aria.attention.ingest: eta=%.3f h=%.3f n=%d total=%d", eta_val, h, n, total)
    return {
        "ok": True,
        "signal": "attention",
        "vertex_id": vertex_id,
        "eta": eta_val,
        "entropy_h": h,
        "magnitude": magnitude,
        "valence": valence,
        "sample_count": n,
        "total_records": total,
    }


# ── Task 2: request ingest ────────────────────────────────────────────────────

def task_aria_request_ingest(**kwargs: Any) -> dict[str, Any]:
    """Compute request pressure from recent XRPC collection activity.

    Sources from vertex_repo_record (last 1h) — no external HTTP.
    Inserts into vertex_signal_request.

    BPMN: aria/ariaSignalIngest.bpmn → Task_RequestIngest
    """
    now = _now_ts()
    vertex_id = _stable_id("aria-req", now[:16])

    # 10s timeout: vertex_repo_record (15M rows) times out at 120s without index.
    counts: dict[str, int] = {}
    total = 0
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q("SET statement_timeout = '10s'")
            _res = client.q(
                f"""SELECT collection, COUNT(*) AS cnt
                    FROM vertex_repo_record
                    WHERE ts_ms > (EXTRACT(EPOCH FROM NOW()) * 1000 - 3600000)
                    GROUP BY collection
                    ORDER BY cnt DESC
                    LIMIT {int(100)}"""
            )
            rows = _res
        for collection, cnt in rows:
            c = int(cnt or 0)
            counts[str(collection)] = c
            total += c
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.request: vertex_repo_record not found: %s", exc)
        else:
            LOG.warning("aria.request: DB query failed: %s", exc)

    count_values = list(counts.values())
    h = _shannon_h(count_values) if count_values else 0.5
    n = len(count_values)
    eta_val = _eta(h, n) if n > 0 else 0.5
    magnitude = (max(count_values) / total) if total > 0 else 0.5
    valence = 1.0  # growing assumption (request is active)

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "DELETE FROM vertex_signal_request WHERE vertex_id = %s",
                (vertex_id,),
            )
            _res = client.q(
                """INSERT INTO vertex_signal_request
                   (vertex_id, signal_axis, source, magnitude, valence,
                    entropy_h, eta, sample_count, metadata_json, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    vertex_id,
                    "request",
                    "vertex_repo_record:collection_distribution",
                    magnitude,
                    valence,
                    h,
                    eta_val,
                    n,
                    json.dumps({"total_records_1h": total,
                                "top_collections": list(counts.keys())[:5]}),
                    now,
                ),
            )
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.request: vertex_signal_request not found, skipping insert: %s", exc)
            return {"ok": True, "skipped": True, "reason": "table not found",
                    "signal": "request", "eta": eta_val}
        LOG.warning("aria.request: insert failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300],
                "signal": "request", "eta": eta_val}

    LOG.info("aria.request.ingest: eta=%.3f h=%.3f n=%d total_1h=%d", eta_val, h, n, total)
    return {
        "ok": True,
        "signal": "request",
        "vertex_id": vertex_id,
        "eta": eta_val,
        "entropy_h": h,
        "magnitude": magnitude,
        "valence": valence,
        "sample_count": n,
        "total_records_1h": total,
    }


# ── Task 3: market delta ingest ───────────────────────────────────────────────

def task_aria_market_delta_ingest(**kwargs: Any) -> dict[str, Any]:
    """Fetch open market data from CoinGecko public API (no key required).

    Computes price entropy H from 24h-change distribution.
    Inserts into vertex_signal_market.

    BPMN: aria/ariaSignalIngest.bpmn → Task_MarketDeltaIngest
    """
    now = _now_ts()
    vertex_id = _stable_id("aria-mkt", now[:16])

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
    )
    data: dict[str, Any] = {}
    fetch_error: str | None = None
    try:
        data = _fetch_json(url)
    except urllib.error.HTTPError as exc:
        fetch_error = f"HTTPError:{exc.code}"
        LOG.warning("aria.market: CoinGecko fetch HTTP error: %s", exc)
    except Exception as exc:
        fetch_error = str(exc)[:200]
        LOG.warning("aria.market: CoinGecko fetch failed: %s", exc)

    # Extract 24h change percentages
    changes: list[float] = []
    prices: dict[str, float] = {}
    if data:
        for coin, info in data.items():
            if isinstance(info, dict):
                chg = info.get("usd_24h_change")
                prc = info.get("usd")
                if chg is not None:
                    changes.append(float(chg))
                if prc is not None:
                    prices[coin] = float(prc)

    # Compute entropy over absolute-change distribution
    abs_changes = [abs(c) for c in changes]
    h = _shannon_h(abs_changes) if abs_changes else 0.5
    n = len(abs_changes)
    eta_val = _eta(h, n) if n > 0 else 0.5

    # Magnitude = mean absolute 24h change normalised to [0,1] (cap at 50%)
    mean_abs = (sum(abs_changes) / n) if n > 0 else 0.0
    magnitude = min(1.0, mean_abs / 50.0)

    # Valence: positive if net positive, negative if net negative
    net = sum(changes)
    valence = 1.0 if net > 0 else (0.0 if net < 0 else 0.5)

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "DELETE FROM vertex_signal_market WHERE vertex_id = %s",
                (vertex_id,),
            )
            _res = client.q(
                """INSERT INTO vertex_signal_market
                   (vertex_id, signal_axis, source, magnitude, valence,
                    entropy_h, eta, sample_count, metadata_json, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    vertex_id,
                    "market",
                    "coingecko.simple.price",
                    magnitude,
                    valence,
                    h,
                    eta_val,
                    n,
                    json.dumps({"prices": prices,
                                "changes_24h": changes,
                                "fetch_error": fetch_error}),
                    now,
                ),
            )
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.market: vertex_signal_market not found, skipping insert: %s", exc)
            return {"ok": True, "skipped": True, "reason": "table not found",
                    "signal": "market", "eta": eta_val}
        LOG.warning("aria.market: insert failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300],
                "signal": "market", "eta": eta_val}

    LOG.info("aria.market.delta.ingest: eta=%.3f h=%.3f magnitude=%.3f valence=%.1f",
             eta_val, h, magnitude, valence)
    return {
        "ok": True,
        "signal": "market",
        "vertex_id": vertex_id,
        "eta": eta_val,
        "entropy_h": h,
        "magnitude": magnitude,
        "valence": valence,
        "sample_count": n,
        "prices": prices,
        "fetch_error": fetch_error,
    }


# ── Task 4: money flow ingest ─────────────────────────────────────────────────

def task_aria_money_flow_ingest(**kwargs: Any) -> dict[str, Any]:
    """Fetch on-chain flow data from Blockchain.info stats API (public, no key).

    Normalises trade_volume_usd against 90-day max stored in vertex_signal_money.
    Inserts into vertex_signal_money.

    BPMN: aria/ariaSignalIngest.bpmn → Task_MoneyFlowIngest
    """
    now = _now_ts()
    vertex_id = _stable_id("aria-money", now[:16])

    url = "https://api.blockchain.info/stats"
    stats: dict[str, Any] = {}
    fetch_error: str | None = None
    try:
        stats = _fetch_json(url)
    except urllib.error.HTTPError as exc:
        fetch_error = f"HTTPError:{exc.code}"
        LOG.warning("aria.money: blockchain.info HTTP error: %s", exc)
    except Exception as exc:
        fetch_error = str(exc)[:200]
        LOG.warning("aria.money: blockchain.info fetch failed: %s", exc)

    trade_volume_usd = float(stats.get("trade_volume_usd", 0) or 0)
    est_tx_volume_usd = float(stats.get("estimated_transaction_volume_usd", 0) or 0)
    market_price_usd = float(stats.get("market_price_usd", 0) or 0)

    # Retrieve 90-day max from stored records
    max_90d: float = trade_volume_usd  # default: current is the max
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT MAX(magnitude)
                    FROM vertex_signal_money
                    WHERE signal_axis = 'money'
                      AND created_at > NOW() - INTERVAL '90 days'
                    LIMIT {int(1)}"""
            )
            row = (_res[0] if _res else None)
        if row and row[0] is not None:
            stored_max_mag = float(row[0])
            # magnitude was already normalised; recover approximate volume max
            # Use trade_volume_usd as floor reference
            max_90d = max(trade_volume_usd, trade_volume_usd / max(stored_max_mag, 0.001))
    except Exception as exc:
        if not _table_not_found(exc):
            LOG.warning("aria.money: 90d max query failed (non-critical): %s", exc)

    magnitude = min(1.0, trade_volume_usd / max_90d) if max_90d > 0 else 0.5
    # Valence: growing volume is positive
    valence = 1.0 if trade_volume_usd > 0 else 0.5

    # Entropy: 2-element distribution (trade vs est_tx)
    vol_counts = [trade_volume_usd, est_tx_volume_usd]
    h = _shannon_h(vol_counts) if sum(vol_counts) > 0 else 0.5
    eta_val = _eta(h, 2)

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "DELETE FROM vertex_signal_money WHERE vertex_id = %s",
                (vertex_id,),
            )
            _res = client.q(
                """INSERT INTO vertex_signal_money
                   (vertex_id, signal_axis, source, magnitude, valence,
                    entropy_h, eta, sample_count, metadata_json, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    vertex_id,
                    "money",
                    "blockchain.info.stats",
                    magnitude,
                    valence,
                    h,
                    eta_val,
                    2,
                    json.dumps({
                        "trade_volume_usd": trade_volume_usd,
                        "est_tx_volume_usd": est_tx_volume_usd,
                        "market_price_usd": market_price_usd,
                        "max_90d_reference": max_90d,
                        "fetch_error": fetch_error,
                    }),
                    now,
                ),
            )
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.money: vertex_signal_money not found, skipping insert: %s", exc)
            return {"ok": True, "skipped": True, "reason": "table not found",
                    "signal": "money", "eta": eta_val}
        LOG.warning("aria.money: insert failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300],
                "signal": "money", "eta": eta_val}

    LOG.info("aria.money.flow.ingest: eta=%.3f magnitude=%.3f trade_vol=%.0f",
             eta_val, magnitude, trade_volume_usd)
    return {
        "ok": True,
        "signal": "money",
        "vertex_id": vertex_id,
        "eta": eta_val,
        "entropy_h": h,
        "magnitude": magnitude,
        "valence": valence,
        "trade_volume_usd": trade_volume_usd,
        "market_price_usd": market_price_usd,
        "fetch_error": fetch_error,
    }


# ── Task 5: emotion ingest ────────────────────────────────────────────────────

def task_aria_emotion_ingest(**kwargs: Any) -> dict[str, Any]:
    """Source emotion signal from vertex_actor_wellbecoming_profile at-risk cluster.

    No external HTTP — reads existing RisingWave tables.
    Inserts into vertex_signal_emotion.

    BPMN: aria/ariaSignalIngest.bpmn → Task_EmotionIngest
    """
    now = _now_ts()
    vertex_id = _stable_id("aria-emo", now[:16])

    sep_deltas: list[float] = []
    axis_counts: dict[str, int] = {}
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT avg_separation_delta, bottleneck_axis
                    FROM vertex_actor_wellbecoming_profile
                    WHERE at_risk = true
                    LIMIT {int(500)}"""
            )
            rows = _res
        for avg_sep, axis in rows:
            sep_deltas.append(float(avg_sep or 0.0))
            key = str(axis or "unknown")
            axis_counts[key] = axis_counts.get(key, 0) + 1
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.emotion: profile table not found, skipping: %s", exc)
            return {"ok": True, "skipped": True, "reason": "table not found",
                    "signal": "emotion", "eta": 0.5}
        LOG.warning("aria.emotion: DB query failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300],
                "signal": "emotion", "eta": 0.5}

    n = len(sep_deltas)
    if n == 0:
        magnitude = 0.0
        valence = 0.5
        h = 0.5
        eta_val = 0.5
    else:
        mean_abs_delta = sum(abs(d) for d in sep_deltas) / n
        magnitude = min(1.0, mean_abs_delta)
        mean_delta = sum(sep_deltas) / n
        valence = 1.0 if mean_delta > 0 else (0.0 if mean_delta < 0 else 0.5)
        h = _shannon_h(list(axis_counts.values())) if axis_counts else 0.5
        eta_val = _eta(h, len(axis_counts)) if axis_counts else 0.5

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "DELETE FROM vertex_signal_emotion WHERE vertex_id = %s",
                (vertex_id,),
            )
            _res = client.q(
                """INSERT INTO vertex_signal_emotion
                   (vertex_id, signal_axis, source, magnitude, valence,
                    entropy_h, eta, sample_count, metadata_json, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    vertex_id,
                    "emotion",
                    "vertex_actor_wellbecoming_profile:at_risk",
                    magnitude,
                    valence,
                    h,
                    eta_val,
                    n,
                    json.dumps({"axis_distribution": axis_counts,
                                "at_risk_count": n}),
                    now,
                ),
            )
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.emotion: vertex_signal_emotion not found, skipping insert: %s", exc)
            return {"ok": True, "skipped": True, "reason": "table not found",
                    "signal": "emotion", "eta": eta_val}
        LOG.warning("aria.emotion: insert failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300],
                "signal": "emotion", "eta": eta_val}

    LOG.info("aria.emotion.ingest: eta=%.3f h=%.3f at_risk_n=%d magnitude=%.3f valence=%.1f",
             eta_val, h, n, magnitude, valence)
    return {
        "ok": True,
        "signal": "emotion",
        "vertex_id": vertex_id,
        "eta": eta_val,
        "entropy_h": h,
        "magnitude": magnitude,
        "valence": valence,
        "at_risk_count": n,
        "axis_distribution": axis_counts,
    }


# ── Task 6: influence ingest ──────────────────────────────────────────────────

def task_aria_influence_ingest(**kwargs: Any) -> dict[str, Any]:
    """Source influence signal from edge_follows top-100 follower distribution.

    No external HTTP — reads existing graph.
    Inserts into vertex_signal_influence.

    BPMN: aria/ariaSignalIngest.bpmn → Task_InfluenceIngest
    """
    now = _now_ts()
    vertex_id = _stable_id("aria-inf", now[:16])

    follower_counts: list[int] = []
    top_actor: str = ""
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT owner_did, COUNT(*) AS follower_cnt
                    FROM edge_follows
                    GROUP BY owner_did
                    ORDER BY follower_cnt DESC
                    LIMIT {int(100)}"""
            )
            rows = _res
        for i, (owner_did, cnt) in enumerate(rows):
            follower_counts.append(int(cnt or 0))
            if i == 0:
                top_actor = str(owner_did or "")
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.influence: edge_follows not found, skipping: %s", exc)
            return {"ok": True, "skipped": True, "reason": "table not found",
                    "signal": "influence", "eta": 0.5}
        LOG.warning("aria.influence: DB query failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300],
                "signal": "influence", "eta": 0.5}

    total = sum(follower_counts)
    n = len(follower_counts)
    h = _shannon_h(follower_counts) if follower_counts else 0.5
    eta_val = _eta(h, n) if n > 0 else 0.5
    magnitude = (follower_counts[0] / total) if (total > 0 and follower_counts) else 0.5
    valence = 0.5  # neutral: influence concentration is neither good nor bad

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "DELETE FROM vertex_signal_influence WHERE vertex_id = %s",
                (vertex_id,),
            )
            _res = client.q(
                """INSERT INTO vertex_signal_influence
                   (vertex_id, signal_axis, source, magnitude, valence,
                    entropy_h, eta, sample_count, metadata_json, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    vertex_id,
                    "influence",
                    "edge_follows:top100_distribution",
                    magnitude,
                    valence,
                    h,
                    eta_val,
                    n,
                    json.dumps({"top_actor": top_actor[:80],
                                "total_follows": total,
                                "top_100_actors": n}),
                    now,
                ),
            )
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.influence: vertex_signal_influence not found, skipping insert: %s", exc)
            return {"ok": True, "skipped": True, "reason": "table not found",
                    "signal": "influence", "eta": eta_val}
        LOG.warning("aria.influence: insert failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300],
                "signal": "influence", "eta": eta_val}

    LOG.info("aria.influence.ingest: eta=%.3f h=%.3f n=%d total=%d top=%s",
             eta_val, h, n, total, top_actor[:30])
    return {
        "ok": True,
        "signal": "influence",
        "vertex_id": vertex_id,
        "eta": eta_val,
        "entropy_h": h,
        "magnitude": magnitude,
        "valence": valence,
        "sample_count": n,
        "total_follows": total,
    }


# ── Task 7: minimax sweep ─────────────────────────────────────────────────────

def task_aria_minimax_sweep(**kwargs: Any) -> dict[str, Any]:
    """Von Neumann minimax computation over all ARIA signal etas.

    1. Reads current eta per signal from mv_signal_entropy (fallback: direct tables).
    2. Computes A_info = Σ_k axis_weight_k × eta_k.
    3. For each action candidate, simulates worst-case and best-case signal shifts.
    4. Selects argmin_action(max_regret) = minimax-optimal action.
    5. Inserts result into vertex_wellbecoming_event.

    BPMN: aria/ariaMinimaxSweep.bpmn → Task_MinimaxSweep
    """
    now = _now_ts()

    # ── Step 1: read current etas ──────────────────────────────────────────────
    etas: dict[str, float] = {}
    signal_source = "unknown"

    # Try mv_signal_entropy first
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT signal_axis, eta
                    FROM mv_signal_entropy
                    ORDER BY signal_axis
                    LIMIT {int(20)}"""
            )
            rows = _res
        if rows:
            for axis, eta_val in rows:
                etas[str(axis)] = float(eta_val or 0.5)
            signal_source = "mv_signal_entropy"
    except Exception as exc:
        if not _table_not_found(exc):
            LOG.warning("aria.minimax: mv_signal_entropy query failed: %s", exc)

    # Fallback: query each signal table directly for latest eta
    if not etas:
        _SIGNAL_TABLES = {
            "attention": "vertex_signal_attention",
            "request":   "vertex_signal_request",
            "market":    "vertex_signal_market",
            "money":     "vertex_signal_money",
            "emotion":   "vertex_signal_emotion",
            "influence": "vertex_signal_influence",
        }
        for axis, table in _SIGNAL_TABLES.items():
            try:
                if True:
                    client = get_kotoba_client()
                    _res = client.q(
                        f"""SELECT eta
                            FROM {table}
                            WHERE signal_axis = %s
                            ORDER BY created_at DESC
                            LIMIT {int(1)}""",
                        (axis,),
                    )
                    row = (_res[0] if _res else None)
                etas[axis] = float(row[0]) if row and row[0] is not None else 0.5
            except Exception:
                etas[axis] = 0.5  # default if table missing
        signal_source = "direct_tables_fallback"

    # Fill missing axes with default
    for axis in AXIS_WEIGHTS:
        if axis not in etas:
            etas[axis] = 0.5

    # ── Step 2: A_info and eta_global ─────────────────────────────────────────
    a_info = sum(AXIS_WEIGHTS[ax] * etas.get(ax, 0.5) for ax in AXIS_WEIGHTS)
    weight_sum = sum(AXIS_WEIGHTS.values())
    eta_global = a_info / weight_sum if weight_sum > 0 else 0.5

    # ── Step 3: minimax regret over action candidates ─────────────────────────
    # For each action, model a perturbation: the action improves its primary
    # signal axis by +0.1 (best-case) and degrades the worst axis by -0.05
    # (worst-case). Regret = U_total(best_world) - U_total(worst_world).
    # The action with the LOWEST max-regret is minimax-optimal.

    _ACTION_PRIMARY_SIGNAL: dict[str, str] = {
        "post_content":    "attention",
        "ingest_data":     "request",
        "connect_actors":  "influence",
        "expand_coverage": "attention",
        "update_market":   "market",
    }

    bottleneck_axis = min(etas, key=etas.get)  # lowest-eta signal
    regret_by_action: dict[str, float] = {}

    for action in _ACTION_CANDIDATES:
        primary = _ACTION_PRIMARY_SIGNAL.get(action, "attention")

        # Best-case: improve primary signal
        best_etas = dict(etas)
        best_etas[primary] = min(1.0, best_etas.get(primary, 0.5) + 0.1)

        # Worst-case: degrade the already-worst signal further
        worst_etas = dict(etas)
        worst_etas[bottleneck_axis] = max(0.0, worst_etas.get(bottleneck_axis, 0.5) - 0.05)

        u_best = _u_total(best_etas)
        u_worst = _u_total(worst_etas)
        regret = u_best - u_worst  # range [0, 1]; lower = more stable
        regret_by_action[action] = regret

    minimax_action = min(regret_by_action, key=regret_by_action.get)
    minimax_regret = regret_by_action[minimax_action]
    u_current = _u_total(etas)

    # ── Step 4: write result to vertex_wellbecoming_event ─────────────────────
    event_id = f"aria:minimax:{int(time.time() * 1000):x}"
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                """INSERT INTO vertex_wellbecoming_event
                   (vertex_id, case_id, agent_did, activity, layer_trigger,
                    floor_violated, response_length, response_preview,
                    tool_count, model,
                    score_spirit, score_wellbecoming, score_feeling, score_buffer,
                    score_total, separation_delta, scored, scored_at, created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    event_id,
                    "aria-minimax",
                    "did:web:bpmn.etzhayyim.com",
                    "aria_minimax_sweep",
                    bottleneck_axis,
                    False,
                    0,
                    f"minimax_action={minimax_action} regret={minimax_regret:.4f} eta_global={eta_global:.4f}"[:300],
                    0,
                    "aria-minimax-v1",
                    etas.get("emotion", 0.5),
                    etas.get("attention", 0.5),
                    etas.get("request", 0.5),
                    etas.get("money", 0.5),
                    u_current,
                    0.0,  # separation_delta not applicable to minimax event
                    True,
                    now,
                    now,
                ),
            )
    except Exception as exc:
        if _table_not_found(exc):
            LOG.warning("aria.minimax: vertex_wellbecoming_event not found: %s", exc)
        else:
            LOG.warning("aria.minimax: event insert failed: %s", exc)

    LOG.info(
        "aria.minimax.sweep: action=%s regret=%.4f a_info=%.3f eta_global=%.3f bottleneck=%s source=%s",
        minimax_action, minimax_regret, a_info, eta_global, bottleneck_axis, signal_source,
    )
    return {
        "ok": True,
        "a_info": a_info,
        "eta_global": eta_global,
        "minimax_action": minimax_action,
        "regret": minimax_regret,
        "regret_by_action": regret_by_action,
        "u_current": u_current,
        "bottleneck_axis": bottleneck_axis,
        "signals": etas,
        "signal_source": signal_source,
        "event_id": event_id,
        "timestamp": now,
    }


# ── Task 8: reverse topo replan ───────────────────────────────────────────────

def task_aria_reverse_topo_replan(**kwargs: Any) -> dict[str, Any]:
    """Reverse topological sort of signal ingestion priority by eta.

    Reads mv_signal_entropy for current eta per signal (fallback: default 0.5).
    Reverse-topo-sorts by propagation DAG order (emotion→…→influence).
    Signals with lowest eta get highest priority in reverse-topo direction.
    Returns sorted ingestion order with priority weights.

    BPMN: aria/ariaSignalIngest.bpmn → Task_ReverseTopo
    """
    now = _now_ts()

    # Read current etas
    etas: dict[str, float] = {}
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"""SELECT signal_axis, eta
                    FROM mv_signal_entropy
                    ORDER BY signal_axis
                    LIMIT {int(20)}"""
            )
            rows = _res
        for axis, eta_val in rows:
            etas[str(axis)] = float(eta_val or 0.5)
    except Exception as exc:
        if not _table_not_found(exc):
            LOG.warning("aria.reverse_topo: mv_signal_entropy failed (using defaults): %s", exc)

    # Fill defaults for missing axes
    for axis in _TOPO_ORDER:
        if axis not in etas:
            etas[axis] = 0.5

    # Reverse-topo-sort: signals with lowest eta = highest priority.
    # Start from the reverse of _TOPO_ORDER (influence first in reverse) and
    # further rank by ascending eta within each position.
    # Result: the signal that most urgently needs attention comes first.
    reverse_topo = list(reversed(_TOPO_ORDER))

    # Within the reversed order, sort by ascending eta so the most degraded
    # signal within its propagation neighbourhood leads the sweep.
    sorted_signals = sorted(
        reverse_topo,
        key=lambda ax: etas.get(ax, 0.5),
    )

    # Compute priority weights: inverse of eta, normalised to [0,1] per signal
    raw_priorities = {ax: 1.0 - etas.get(ax, 0.5) for ax in _TOPO_ORDER}
    total_pri = sum(raw_priorities.values()) or 1.0
    priority_weights = {ax: round(v / total_pri, 4) for ax, v in raw_priorities.items()}

    # Build rationale
    bottleneck = sorted_signals[0] if sorted_signals else "unknown"
    rationale = (
        f"Reverse-topo replan at {now}: bottleneck={bottleneck} "
        f"(eta={etas.get(bottleneck, 0.5):.3f}). "
        f"Ingestion order prioritises lowest-eta signals first within "
        f"reverse propagation DAG (influence→money→market→request→attention→emotion)."
    )

    LOG.info("aria.reverse_topo_replan: order=%s bottleneck=%s etas=%s",
             sorted_signals, bottleneck, {k: round(v, 3) for k, v in etas.items()})
    return {
        "ok": True,
        "signal_order": sorted_signals,
        "priority_weights": priority_weights,
        "etas": etas,
        "bottleneck": bottleneck,
        "rationale": rationale,
        "timestamp": now,
    }


# ── register() ────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire ARIA signal primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False,
                    timeout_ms=ms if ms is not None else timeout_ms)(fn)

    t("aria.attention.ingest",      task_aria_attention_ingest,    ms=60_000)
    t("aria.request.ingest",        task_aria_request_ingest,      ms=30_000)
    t("aria.market.delta.ingest",   task_aria_market_delta_ingest, ms=30_000)
    t("aria.money.flow.ingest",     task_aria_money_flow_ingest,   ms=30_000)
    t("aria.emotion.ingest",        task_aria_emotion_ingest,      ms=30_000)
    t("aria.influence.ingest",      task_aria_influence_ingest,    ms=30_000)
    t("aria.minimax.sweep",         task_aria_minimax_sweep,       ms=max(timeout_ms, 120_000))
    t("aria.reverse.topo.replan",   task_aria_reverse_topo_replan, ms=30_000)
