"""
com.etzhayyim.apps.media_gamers chart analysis primitives.

Two LangServer task types backing chartFetch.bpmn + chartAnalyze.bpmn:

  mediaGamers.chart.fetchAndPersist
      Fetch weekly top-20 charts from SteamSpy (free, no auth) and optionally
      RAWG (API key from env RAWG_API_KEY).  Match titles to vertex_game_title
      via external_ids. Compute rank_delta vs previous week. Persist
      vertex_game_chart_snapshot rows + edge_game_charted_at edges.
      Returns: weekStart, source, snapshotCount.

  mediaGamers.chart.analyze
      Load current-week snapshots from DB. Build LLM context (top titles,
      rising/falling, genre distribution). Call Murakumo for Japanese insight
      text + insight_tags. Persist vertex_game_chart_analysis. Post to social
      feed via insert_social_post_record. Returns: analysisUri, socialText.

ADR-2605262130: domain writes direct to kotoba Datom log (ADR-2605312345).
ADR-0056: BPMN-as-actor.
ADR-0044: Murakumo LLM via kotodama.llm (external IO tier).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import urllib.error as _u_err
import urllib.request as _u_req
from datetime import timezone
from typing import Any

from kotodama import llm as _llm
from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives.yoro_social import insert_social_post_record

_ACTOR_DID = os.getenv("MEDIA_GAMERS_ACTOR_DID", "did:web:media-gamers.etzhayyim.com")
_COLLECTION_SNAPSHOT = "com.etzhayyim.apps.media_gamers.chartSnapshot"
_COLLECTION_ANALYSIS = "com.etzhayyim.apps.media_gamers.chartAnalysis"

_STEAMSPY_TOP2W_URL = "https://steamspy.com/api.php?request=top100in2weeks"
_RAWG_GAMES_URL = "https://api.rawg.io/api/games"
_STEAMSPY_DETAILS_URL = "https://steamspy.com/api.php?request=appdetails&appid={appid}"

_HTTP_TIMEOUT = 20.0
_CHART_LIMIT = 20  # how many ranks to store per source per week


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _week_start(ref: _dt.date | None = None) -> _dt.date:
    """Return the Monday of the ISO week containing ref (default: today)."""
    d = ref or _dt.date.today()
    return d - _dt.timedelta(days=d.weekday())


def _rkey(prefix: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:6]}"


def _http_get_json(url: str, headers: dict | None = None, timeout: float = _HTTP_TIMEOUT) -> Any:
    req = _u_req.Request(url, headers=headers or {"User-Agent": "etzhayyim-media-gamers/1.0"})
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (_u_err.HTTPError, _u_err.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"HTTP GET failed {url}: {exc}") from exc


def _vertex_id_snapshot(source: str, week: _dt.date, rank: int) -> str:
    return f"at://{_ACTOR_DID}/{_COLLECTION_SNAPSHOT}/{source}-{week}-{rank:03d}"


def _vertex_id_analysis(source: str, week: _dt.date) -> str:
    return f"at://{_ACTOR_DID}/{_COLLECTION_ANALYSIS}/{source}-{week}"


def _edge_id_charted(title_did: str, source: str, week: _dt.date) -> str:
    slug = title_did.replace("://", "__").replace("/", "_")
    return f"{slug}:{source}:{week}"


# ── SteamSpy fetch ────────────────────────────────────────────────────────────

def _fetch_steamspy_top2w() -> list[dict]:
    """Return top-100 games by 2-week player count from SteamSpy (public API).

    Response is a dict keyed by appid → {name, developer, publisher, owners,
    players_2weeks, positive, negative, price, ...}.
    We take top _CHART_LIMIT by players_2weeks descending.
    """
    raw = _http_get_json(_STEAMSPY_TOP2W_URL)
    if not isinstance(raw, dict):
        return []

    items: list[dict] = []
    for appid, data in raw.items():
        players = data.get("players_2weeks", 0) or 0
        positive = data.get("positive", 0) or 0
        negative = data.get("negative", 0) or 0
        total_reviews = positive + negative
        positive_pct = (positive / total_reviews * 100.0) if total_reviews > 0 else None
        price_usd = None
        raw_price = data.get("price") or data.get("initialprice")
        if raw_price and str(raw_price).isdigit() and int(raw_price) > 0:
            price_usd = int(raw_price) / 100.0

        items.append({
            "external_id": str(appid),
            "title_hint": (data.get("name") or "").strip()[:255],
            "players_2w": int(players),
            "score_source": positive_pct,
            "price_usd": price_usd,
            "tags": list(data.get("tags", {}).keys())[:10] if data.get("tags") else [],
            "reviews_total": total_reviews,
        })

    items.sort(key=lambda x: x["players_2w"], reverse=True)
    return items[:_CHART_LIMIT]


# ── RAWG fetch ────────────────────────────────────────────────────────────────

def _fetch_rawg_top(api_key: str, week: _dt.date) -> list[dict]:
    """Return top games from RAWG ordered by metacritic score for the past week."""
    since = (week - _dt.timedelta(days=7)).isoformat()
    until = week.isoformat()
    params = f"key={api_key}&ordering=-metacritic&page_size={_CHART_LIMIT}&dates={since},{until}"
    url = f"{_RAWG_GAMES_URL}?{params}"
    try:
        raw = _http_get_json(url, timeout=25.0)
    except RuntimeError:
        return []

    items = []
    for game in (raw.get("results") or []):
        steam_id = None
        for store in (game.get("stores") or []):
            if (store.get("store", {}) or {}).get("slug") == "steam":
                url_part = store.get("url", "")
                parts = [p for p in url_part.rstrip("/").split("/") if p.isdigit()]
                if parts:
                    steam_id = parts[-1]
        items.append({
            "external_id": str(game.get("id", "")),
            "steam_id": steam_id,
            "title_hint": (game.get("name") or "").strip()[:255],
            "players_2w": None,
            "score_source": float(game.get("metacritic") or 0) if game.get("metacritic") else None,
            "price_usd": None,
            "tags": [g["name"] for g in (game.get("genres") or [])][:10],
            "reviews_total": game.get("reviews_count") or 0,
        })
    return items


# ── title matching ────────────────────────────────────────────────────────────

def _match_title_did(external_id: str, steam_id: str | None, title_hint: str) -> str | None:
    """Try to match a chart entry to an existing vertex_game_title row.

    Strategy:
      1. external_ids column contains comma-separated 'key:value' pairs.
         Look for steam:{external_id} or steam:{steam_id}.
      2. Fuzzy: case-insensitive exact match on title_en.
    Returns vertex_id or None.
    """
    candidates = {external_id}
    if steam_id:
        candidates.add(steam_id)

    kotoba = get_kotoba_client()
    for cid in candidates:
        # R0: using q() for LIKE and OR conditions
        result = kotoba.q(
            """
            [:find ?vid .
             :in $ ?steam_cid ?steamspy_cid
             :where
              [?e :vertex/type :vertex.game.title]
              [?e :vertex.game.title/vertex-id ?vid]
              [?e :vertex.game.title/external-ids ?ext_ids]
              (or
                [(clojure.string/includes? ?ext_ids ?steam_cid)]
                [(clojure.string/includes? ?ext_ids ?steamspy_cid)]
              )
            :limit 1]
            """,
            args=(f"steam:{cid}", f"steamspy:{cid}")
        )
        if result:
            return result[0][0]

    # title-based fallback (exact, case-insensitive)
    if title_hint:
        lower_title_hint = title_hint.lower()
        # R0: using q() for LOWER() and OR conditions
        result = kotoba.q(
            """
            [:find ?vid .
             :in $ ?lower_title_hint
             :where
              [?e :vertex/type :vertex.game.title]
              [?e :vertex.game.title/vertex-id ?vid]
              (or
                (and [?e :vertex.game.title/title-en ?title_en] [(= (clojure.string/lower ?title_en) ?lower_title_hint)])
                (and [?e :vertex.game.title/title-ja ?title_ja] [(= (clojure.string/lower ?title_ja) ?lower_title_hint)])
              )
            :limit 1]
            """,
            args=(lower_title_hint,)
        )
        if result:
            return result[0][0]
    return None


# ── previous week rank lookup ─────────────────────────────────────────────────

def _prev_week_ranks(source: str, prev_week: _dt.date) -> dict[str, int]:
    """Return {external_id → rank} for the given source + prev_week."""
    kotoba = get_kotoba_client()
    # R0: using q() for multi-predicate SELECT
    results = kotoba.q(
        """
        [:find ?ext_id ?rank
         :in $ ?source ?week_start
         :where
          [?e :vertex/type :vertex.game.chart-snapshot]
          [?e :vertex.game.chart-snapshot/source ?source]
          [?e :vertex.game.chart-snapshot/week-start ?week_start]
          [?e :vertex.game.chart-snapshot/external-id ?ext_id]
          [?e :vertex.game.chart-snapshot/rank ?rank]]
        """,
        args=(source, prev_week.isoformat())
    )
    return {row[0]: row[1] for row in results}


# ── Task 1: mediaGamers.chart.fetchAndPersist ─────────────────────────────────

def task_media_gamers_chart_fetch_and_persist() -> dict[str, Any]:
    """Fetch weekly charts, match titles, persist snapshots + edges.

    Returns:
        weekStart     — ISO date string (Monday of this week)
        source        — "steamspy_top2w" (primary source used)
        snapshotCount — total rows upserted into vertex_game_chart_snapshot
    """
    week = _week_start()
    prev_week = week - _dt.timedelta(days=7)
    created_at = _now_iso()
    source = "steamspy_top2w"

    # Fetch
    try:
        entries = _fetch_steamspy_top2w()
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc), "weekStart": str(week), "source": source, "snapshotCount": 0}

    if not entries:
        return {"ok": True, "weekStart": str(week), "source": source, "snapshotCount": 0}

    prev_ranks = _prev_week_ranks(source, prev_week)
    snapshot_count = 0
    kotoba = get_kotoba_client() # Initialize kotoba client once

    for rank, entry in enumerate(entries, start=1):
        ext_id = entry["external_id"]
        title_did = _match_title_did(ext_id, None, entry["title_hint"])

        rank_prev = prev_ranks.get(ext_id)
        rank_delta = (rank_prev - rank) if rank_prev is not None else None

        vertex_id = _vertex_id_snapshot(source, week, rank)
        metadata = {
            "tags": entry.get("tags", []),
            "reviews_total": entry.get("reviews_total", 0),
        }
        metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))

        snapshot_row = {
            "vertex_id": vertex_id,
            "owner_did": _ACTOR_DID,
            "title_did": title_did,
            "source": source,
            "week_start": week.isoformat(),
            "rank": rank,
            "rank_prev": rank_prev,
            "rank_delta": rank_delta,
            "external_id": ext_id,
            "title_hint": entry["title_hint"],
            "score_source": entry.get("score_source"),
            "players_2w": entry.get("players_2w"),
            "price_usd": entry.get("price_usd"),
            "metadata_json": metadata_json,
            "fetched_at": created_at,
            "actor_did": _ACTOR_DID,
            "org_did": _ACTOR_DID,
            "sensitivity_ord": 1,
            "created_at": created_at,
        }
        kotoba.insert_row("vertex_game_chart_snapshot", snapshot_row)
        snapshot_count += 1

        # Edge: title → snapshot (only when matched)
        if title_did:
            edge_id = _edge_id_charted(title_did, source, week)
            edge_row = {
                "edge_id": edge_id,
                "owner_did": _ACTOR_DID,
                "src_vid": title_did,
                "dst_vid": vertex_id,
                "rank": rank,
                "source": source,
                "week_start": week.isoformat(),
                "sensitivity_ord": 1,
                "created_at": created_at,
            }
            kotoba.insert_row("edge_game_charted_at", edge_row)

    # Also try RAWG if API key is available (secondary source, non-blocking)
    rawg_key = os.getenv("RAWG_API_KEY", "")
    if rawg_key:
        _persist_rawg_source(rawg_key, week, prev_week, created_at)

    return {
        "ok": True,
        "weekStart": str(week),
        "source": source,
        "snapshotCount": snapshot_count,
    }


def _persist_rawg_source(api_key: str, week: _dt.date, prev_week: _dt.date, created_at: str) -> None:
    source = "rawg_top"
    try:
        entries = _fetch_rawg_top(api_key, week)
    except Exception:  # noqa: BLE001
        return
    if not entries:
        return
    prev_ranks = _prev_week_ranks(source, prev_week)
    kotoba = get_kotoba_client()
    for rank, entry in enumerate(entries, start=1):
        ext_id = entry["external_id"]
        steam_id = entry.get("steam_id")
        title_did = _match_title_did(ext_id, steam_id, entry["title_hint"])
        rank_prev = prev_ranks.get(ext_id)
        rank_delta = (rank_prev - rank) if rank_prev is not None else None
        vertex_id = _vertex_id_snapshot(source, week, rank)
        metadata = {"tags": entry.get("tags", []), "reviews_total": entry.get("reviews_total", 0)}
        snapshot_row = {
            "vertex_id": vertex_id,
            "owner_did": _ACTOR_DID,
            "title_did": title_did,
            "source": source,
            "week_start": week.isoformat(),
            "rank": rank,
            "rank_prev": rank_prev,
            "rank_delta": rank_delta,
            "external_id": ext_id,
            "title_hint": entry["title_hint"],
            "score_source": entry.get("score_source"),
            "players_2w": None,
            "price_usd": None,
            "metadata_json": json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
            "fetched_at": created_at,
            "actor_did": _ACTOR_DID,
            "org_did": _ACTOR_DID,
            "sensitivity_ord": 1,
            "created_at": created_at,
        }
        kotoba.insert_row("vertex_game_chart_snapshot", snapshot_row)
        if title_did:
            edge_row = {
                "edge_id": _edge_id_charted(title_did, source, week),
                "owner_did": _ACTOR_DID,
                "src_vid": title_did,
                "dst_vid": vertex_id,
                "rank": rank,
                "source": source,
                "week_start": week.isoformat(),
                "sensitivity_ord": 1,
                "created_at": created_at,
            }
            kotoba.insert_row("edge_game_charted_at", edge_row)


# ── Task 2: mediaGamers.chart.analyze ────────────────────────────────────────

_ANALYSIS_SYSTEM = (
    "You are a game industry analyst writing for media-gamers.etzhayyim.com.\n"
    "Output ONLY valid JSON, no prose, no code fences.\n"
    "Schema: {\n"
    '  "analysis_ja": string (≤280 chars, Japanese, for AT Protocol social post),\n'
    '  "analysis_en": string (≤400 chars, English summary),\n'
    '  "top_genre": string (most common genre in top 10),\n'
    '  "insight_tags": [string] (2-5 short English tags like "indie-surge", "sequel-effect",\n'
    '    "seasonal", "early-access-peak", "jrpg-week", "battle-royale-resurgence")\n'
    "}"
)


def task_media_gamers_chart_analyze(
    weekStart: str = "",
    source: str = "steamspy_top2w",
) -> dict[str, Any]:
    """LLM-analyze current-week chart data and persist vertex_game_chart_analysis.

    Reads vertex_game_chart_snapshot for weekStart × source, joins with
    vertex_game_title for genre info via edge_game_has_genre, builds LLM
    context, generates analysis_ja + insight_tags, persists, and posts to
    the media-gamers AT social feed.

    Returns:
        analysisUri — vertex_id of vertex_game_chart_analysis
        socialText  — Japanese post text used for social feed
    """
    # Resolve weekStart
    if weekStart:
        try:
            week = _dt.date.fromisoformat(weekStart)
        except ValueError:
            week = _week_start()
    else:
        week = _week_start()

    created_at = _now_iso()
    vertex_id = _vertex_id_analysis(source, week)
    kotoba = get_kotoba_client() # Initialize kotoba client once

    # ── Load snapshot rows for this week + source ──────────────────────────
    # R0: using select_where and in-Python filtering/ordering for complex SELECT
    snapshots = kotoba.select_where(
        "vertex_game_chart_snapshot",
        "source", source,
        columns=[
            "rank", "rank_delta", "rank_prev", "title_hint",
            "players_2w", "score_source", "external_id",
            "title_did", "metadata_json", "week_start"
        ]
    )
    rows_dicts = [s for s in snapshots if s.get("week_start") == week.isoformat()]
    rows_dicts.sort(key=lambda x: x["rank"])
    rows_dicts = rows_dicts[:_CHART_LIMIT]

    if not rows_dicts:
        return {
            "ok": False,
            "error": f"no snapshots for {source} week {week}",
            "analysisUri": vertex_id,
            "socialText": "",
        }

    # ── Genre lookup for matched titles ───────────────────────────────────
    matched_dids = [r["title_did"] for r in rows_dicts if r.get("title_did")]
    genre_map: dict[str, str] = {}
    if matched_dids:
        # R0: using q() for JOIN and IN clause
        results = kotoba.q(
            """
            [:find ?src_vid ?genre_name
             :in $ [?src_vid_list ...]
             :where
              [?g :vertex/type :edge.game.has-genre]
              [?g :edge.game.has-genre/src-vid ?src_vid]
              [(.contains ?src_vid_list ?src_vid)]
              [?g :edge.game.has-genre/is-primary true]
              [?g :edge.game.has-genre/dst-vid ?genre_vid]
              [?vgg :vertex/type :vertex.game.genre]
              [?vgg :vertex.game.genre/vertex-id ?genre_vid]
              [?vgg :vertex.game.genre/name ?genre_name]]
            """,
            args=(matched_dids,)
        )
        for r in results:
            genre_map[r[0]] = r[1]

    # ── Build context for LLM ─────────────────────────────────────────────
    rising: list[dict] = []
    falling: list[dict] = []
    new_entries: list[dict] = []
    genre_counts: dict[str, int] = {}

    top_lines: list[str] = []
    for r in rows_dicts: # Iterate over dictionaries now
        rank = r["rank"]
        rank_delta = r.get("rank_delta")
        rank_prev = r.get("rank_prev")
        title_hint = r["title_hint"]
        players_2w = r.get("players_2w")
        title_did = r.get("title_did")
        genre = genre_map.get(title_did or "", "Unknown")
        genre_counts[genre] = genre_counts.get(genre, 0) + 1

        delta_str = ""
        if rank_delta is not None:
            if rank_delta > 0:
                delta_str = f"↑{rank_delta}"
                rising.append({"title_hint": title_hint, "rank": rank, "rank_delta": rank_delta, "title_did": title_did})
            elif rank_delta < 0:
                delta_str = f"↓{abs(rank_delta)}"
                falling.append({"title_hint": title_hint, "rank": rank, "rank_delta": rank_delta, "title_did": title_did})
        if rank_prev is None:
            new_entries.append({"title_hint": title_hint, "rank": rank, "title_did": title_did})

        players_str = f"{players_2w:,}" if players_2w else "N/A"
        top_lines.append(f"#{rank} {title_hint} [{genre}] players={players_str} {delta_str}")

    top_genre = max(genre_counts, key=lambda k: genre_counts[k]) if genre_counts else "Unknown"
    context = (
        f"Week: {week} | Source: {source}\n"
        f"Top {len(rows_dicts)} games:\n" # Changed rows to rows_dicts
        + "\n".join(top_lines[:15])
        + f"\n\nRising: {[r['title_hint'] for r in rising[:3]]}"
        + f"\nFalling: {[f['title_hint'] for f in falling[:3]]}"
        + f"\nNew entries: {[n['title_hint'] for n in new_entries[:3]]}"
        + f"\nTop genre: {top_genre}"
    )

    # ── LLM call ──────────────────────────────────────────────────────────
    llm_result: dict = {}
    model_id = "unknown"
    try:
        resp = _llm.call_tier_json(
            "fast",
            system=_ANALYSIS_SYSTEM,
            user=f"Analyze this weekly game chart:\n\n{context}",
            max_tokens=600,
            temperature=0.5,
        )
        if resp.get("ok") and isinstance(resp.get("data"), dict):
            llm_result = resp["data"]
            model_id = resp.get("model_id", "unknown")
    except Exception:  # noqa: BLE001
        pass

    analysis_ja = (llm_result.get("analysis_ja") or
                   f"今週のゲームチャート({source}): {top_lines[0] if top_lines else ''}ほか{len(rows_dicts)}作品をランクイン。")[:280] # Changed rows to rows_dicts
    analysis_en = (llm_result.get("analysis_en") or
                   f"Weekly chart ({source}, {week}): {top_genre} leads with {len(rows_dicts)} titles tracked.")[:400] # Changed rows to rows_dicts
    insight_tags = llm_result.get("insight_tags") or []
    if not isinstance(insight_tags, list):
        insight_tags = []

    # ── Persist vertex_game_chart_analysis ────────────────────────────────
    analysis_row = {
        "vertex_id": vertex_id,
        "owner_did": _ACTOR_DID,
        "week_start": week.isoformat(),
        "source": source,
        "analysis_ja": analysis_ja,
        "analysis_en": analysis_en,
        "top_genre": top_genre,
        "rising_titles_json": json.dumps(rising[:5], ensure_ascii=False),
        "falling_titles_json": json.dumps(falling[:5], ensure_ascii=False),
        "new_entries_json": json.dumps(new_entries[:5], ensure_ascii=False),
        "insight_tags_json": json.dumps(insight_tags[:5], ensure_ascii=False),
        "model_id": model_id,
        "actor_did": _ACTOR_DID,
        "org_did": _ACTOR_DID,
        "sensitivity_ord": 1,
        "created_at": created_at,
    }
    kotoba.insert_row("vertex_game_chart_analysis", analysis_row)

    # ── Social post ───────────────────────────────────────────────────────
    social_rkey = _rkey("chart")
    try:
        insert_social_post_record(
            repo=_ACTOR_DID,
            rkey=social_rkey,
            text=analysis_ja,
            langs=["ja"],
        )
        # R0: Update social_post_rkey using insert_row (upsert behavior)
        kotoba.insert_row(
            "vertex_game_chart_analysis",
            {"vertex_id": vertex_id, "social_post_rkey": social_rkey}
        )
    except Exception:  # noqa: BLE001
        pass

    return {
        "ok": True,
        "analysisUri": vertex_id,
        "socialText": analysis_ja,
        "weekStart": str(week),
        "source": source,
        "topGenre": top_genre,
        "insightTags": insight_tags,
    }


# ── LangServer registration ──────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire media-gamers chart primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    # fetchAndPersist may be slow on SteamSpy (rate limits) — give 5min
    t("mediaGamers.chart.fetchAndPersist", task_media_gamers_chart_fetch_and_persist, timeout=300_000)
    # analyze includes LLM call — give 3min
    t("mediaGamers.chart.analyze", task_media_gamers_chart_analyze, timeout=180_000)


__all__ = [
    "register",
    "task_media_gamers_chart_fetch_and_persist",
    "task_media_gamers_chart_analyze",
]
