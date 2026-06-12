"""lifehack.etzhayyim.com household life-hack primitives (Phase 1 — dust prevention).

T2 actor (ADR-2604282300): kotodama module + BPMN + Zeebe, no CF Worker.
All domain writes hit RisingWave directly via Hyperdrive (ADR-0036). Social
posts go through `generic.pds.dispatch` from BPMN, never from this module.

Pipeline coverage (ADR-0056 BPMN-as-actor):
  researchTopic.bpmn               R/PT24H  → lifehack.topic.findStale
                                            → lifehack.tip.synth
                                            → lifehack.tip.gradeAuthority
                                            → lifehack.tip.persist
  dailyDustPost.bpmn               cron 09 JST + XRPC override
                                            → lifehack.topic.pickTrending
                                            → lifehack.tip.pickBest
                                            → lifehack.post.compose
                                            → generic.pds.dispatch
                                            → lifehack.postLog.persist
  staticAlert.bpmn                 R/PT6H   → lifehack.env.checkHumidity
                                            → lifehack.post.compose
                                            → generic.pds.dispatch
  submitTip.bpmn                   XRPC     → lifehack.tip.validateAuthority
                                            → lifehack.tip.gradeEffectiveness
                                            → lifehack.tip.persist
  recommend.bpmn                   XRPC     → lifehack.tip.rank
  agentLoop.bpmn                   XRPC     → lifehack.agent.chat
  submitEnvironmentReading.bpmn    XRPC     → lifehack.env.persistReading
  coverage.bpmn                    XRPC     → lifehack.coverage.snapshot

Output target tables (created by 20260508120000_vertex_lifehack_schema.ts):
  vertex_lifehack_topic / _tip / _product / _environment_reading /
  _post_log / _user_query  +  edge_lifehack_*

Content-addressed PKs (ADR-0041) — re-runs idempotent.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import re
import time
from typing import Any

from kotodama import llm

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

_LIFEHACK_ACTOR = "did:web:lifehack.etzhayyim.com"

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _strip_think_blocks(text: str) -> str:
    if not text:
        return text
    return _THINK_BLOCK_RE.sub("", text).strip()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _today_iso() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _slug(s: str, *, max_len: int = 80) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-.")
    return s[:max_len] or "x"


def _hash12(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _rw_execute(sql: str, params: tuple[Any, ...]) -> None:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)


def _rw_executemany(sql: str, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    chunk = 500
    if True:
        client = get_kotoba_client()
        for i in range(0, len(rows), chunk):
            _res = client.q(sql, rows[i:i + chunk])


def _rw_query(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)
        return list(_res)


def _scalar_count(sql: str, params: tuple[Any, ...] = ()) -> int:
    rows = _rw_query(sql, params)
    if not rows:
        return 0
    try:
        return int(rows[0][0] or 0)
    except (TypeError, ValueError):
        return 0


def _scalar_max(sql: str, params: tuple[Any, ...] = ()) -> int:
    rows = _rw_query(sql, params)
    if not rows or rows[0][0] is None:
        return 0
    try:
        return int(rows[0][0])
    except (TypeError, ValueError):
        return 0


def _topic_vertex_id(topic_id: str) -> str:
    return f"at://{_LIFEHACK_ACTOR}/com.etzhayyim.apps.lifehack.topic/{_slug(topic_id)}"


def _tip_vertex_id(tip_id: str) -> str:
    return f"at://{_LIFEHACK_ACTOR}/com.etzhayyim.apps.lifehack.tip/{tip_id}"


def _product_vertex_id(product_id: str) -> str:
    return f"at://{_LIFEHACK_ACTOR}/com.etzhayyim.apps.lifehack.product/{product_id}"


def _post_log_vertex_id(post_id: str) -> str:
    return f"at://{_LIFEHACK_ACTOR}/com.etzhayyim.apps.lifehack.postLog/{post_id}"


def _reading_vertex_id(reading_id: str) -> str:
    return f"at://{_LIFEHACK_ACTOR}/com.etzhayyim.apps.lifehack.environmentReading/{reading_id}"


# ──────────────────────────────────────────────────────────────────────
# Insert SQL
# ──────────────────────────────────────────────────────────────────────

_INSERT_TIP = (
    "INSERT INTO vertex_lifehack_tip ("
    "vertex_id, owner_did, sensitivity_ord, tip_id, topic_id, "
    "body_ja, body_en, effectiveness_score, cost_jpy_min, cost_jpy_max, "
    "difficulty, source_url, source_authority, evidence_summary, llm_model, "
    "status, created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_INSERT_POST_LOG = (
    "INSERT INTO vertex_lifehack_post_log ("
    "vertex_id, owner_did, sensitivity_ord, post_id, tip_id, topic_id, "
    "bsky_uri, bsky_cid, posted_at_ms, engagement_score, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_INSERT_READING = (
    "INSERT INTO vertex_lifehack_environment_reading ("
    "vertex_id, owner_did, sensitivity_ord, reading_id, reporter_did, "
    "location_h3, humidity_pct, temp_c, pm25_ugm3, ts_ms, source, "
    "status, created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


# ──────────────────────────────────────────────────────────────────────
# LLM prompts
# ──────────────────────────────────────────────────────────────────────

_TIP_SYNTH_SYSTEM = (
    "You generate household life-hack tips with citations. Output JSON ONLY:\n"
    "{ \"tips\": [ { \"bodyJa\": str, \"bodyEn\": str, \"costJpyMin\": int, "
    "\"costJpyMax\": int, \"difficulty\": \"easy|medium|hard\", "
    "\"sourceHint\": str, \"effectivenessScore\": int (0-100) } ] }\n"
    "Cite the most authoritative source you can name (manufacturer / govt / "
    "peer-reviewed). Avoid medical / legal advice. 3 tips per topic max."
)

_TIP_GRADE_SYSTEM = (
    "You grade household tip effectiveness on a 0-100 scale. Output JSON ONLY:\n"
    "{ \"effectivenessScore\": int (0-100), \"evidenceSummary\": str (<= 400 chars), "
    "\"rationale\": str (<= 200 chars) }\n"
    "Cap llm-synth tips at 60. Cap secondary sources at 80. Primary "
    "sources (manufacturer spec / govt / peer-reviewed) may exceed 80."
)

_POST_COMPOSE_SYSTEM = (
    "You write Japanese household life-hack social posts (≤ 280 chars). "
    "Output JSON ONLY:\n"
    "{ \"postText\": str }\n"
    "Style: friendly, concrete, single takeaway, no emoji spam, no hashtags. "
    "Always include a cost-or-effort hint. End with a soft call to action."
)

_AGENT_CHAT_SYSTEM = (
    "You are lifehack.etzhayyim.com, a household life-hack assistant. Use the "
    "context (active topics + top tips + recent posts) to answer in "
    "Japanese unless the user clearly writes English. Cite source URLs "
    "verbatim from the context — never invent URLs. Be concrete; prefer "
    "numbers over adjectives."
)


# ──────────────────────────────────────────────────────────────────────
# researchTopic — find stale + LLM synth + grade authority + persist
# ──────────────────────────────────────────────────────────────────────


async def task_lifehack_topic_find_stale(**kwargs: Any) -> dict[str, Any]:
    """Return active topic_ids whose newest tip is older than staleSeconds."""
    stale_seconds = int(kwargs.get("staleSeconds") or 604800)
    limit = int(kwargs.get("limit") or 10)
    cutoff_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - stale_seconds))

    rows = _rw_query(
        f"SELECT t.topic_id "
        f"FROM vertex_lifehack_topic t "
        f"LEFT JOIN vertex_lifehack_tip tp "
        f"  ON tp.topic_id = t.topic_id AND tp.status = 'active' "
        f"WHERE t.status = 'active' "
        f"GROUP BY t.topic_id "
        f"HAVING COALESCE(MAX(tp.created_at), '1970-01-01') < '{cutoff_iso}' "
        f"LIMIT {int(limit)}"
    )
    return {"ok": True, "topicIds": [str(r[0]) for r in rows]}


async def task_lifehack_tip_synth(**kwargs: Any) -> dict[str, Any]:
    """For each topic, ask LLM for candidate tips. Caps at tipsPerTopic."""
    topic_ids = kwargs.get("topicIds") or []
    if isinstance(topic_ids, str):
        topic_ids = [topic_ids]
    tips_per_topic = max(1, min(int(kwargs.get("tipsPerTopic") or 3), 5))

    candidates: list[dict[str, Any]] = []
    for tid in topic_ids:
        topic_row = _rw_query(
            "SELECT title_ja, summary_ja FROM vertex_lifehack_topic "
            "WHERE topic_id = %s AND status = 'active' LIMIT 1",
            (str(tid),),
        )
        title = str(topic_row[0][0]) if topic_row else str(tid)
        summary = str(topic_row[0][1]) if topic_row and topic_row[0][1] else ""

        user_msg = (
            f"Topic: {title}\n"
            f"Summary: {summary}\n"
            f"Generate up to {tips_per_topic} household tips in JSON."
        )
        result = llm.call_tier_json(
            "balanced", _TIP_SYNTH_SYSTEM, user_msg,
            max_tokens=1500, temperature=0.4,
        )
        data = result.get("data") if isinstance(result, dict) else None
        tips = (data or {}).get("tips") if isinstance(data, dict) else None
        if not isinstance(tips, list):
            continue
        for raw in tips[:tips_per_topic]:
            if not isinstance(raw, dict):
                continue
            body_ja = str(raw.get("bodyJa") or "")[:4000]
            if len(body_ja) < 30:
                continue
            candidates.append({
                "topicId": str(tid),
                "bodyJa": body_ja,
                "bodyEn": str(raw.get("bodyEn") or "")[:4000],
                "costJpyMin": float(raw.get("costJpyMin") or 0.0),
                "costJpyMax": float(raw.get("costJpyMax") or 0.0),
                "difficulty": str(raw.get("difficulty") or "easy")[:16],
                "sourceHint": str(raw.get("sourceHint") or "")[:500],
                "effectivenessScoreHint": float(raw.get("effectivenessScore") or 50.0),
                "graderModel": str(result.get("model") or "unknown"),
            })
    return {"ok": True, "candidates": candidates}


async def task_lifehack_tip_grade_authority(**kwargs: Any) -> dict[str, Any]:
    """For each candidate, derive sourceAuthority (default 'llm-synth') and
    cap effectiveness via the LLM grader. Synth-only candidates are capped
    at 60 (authority-chain compliance)."""
    candidates = kwargs.get("candidates") or []
    if not isinstance(candidates, list):
        return {"ok": True, "graded": []}

    graded: list[dict[str, Any]] = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        # No external citation = llm-synth.  Cap score at 60.
        source_hint = str(c.get("sourceHint") or "")
        source_authority = "llm-synth"
        if source_hint.startswith("http://") or source_hint.startswith("https://"):
            source_authority = "secondary"

        user_msg = (
            f"Tip:\n{c.get('bodyJa')}\n"
            f"Source hint: {source_hint or 'none'}\n"
            "Grade JSON."
        )
        gr = llm.call_tier_json(
            "fast", _TIP_GRADE_SYSTEM, user_msg,
            max_tokens=400, temperature=0.1,
        )
        data = (gr or {}).get("data") if isinstance(gr, dict) else None
        try:
            score = float((data or {}).get("effectivenessScore") or
                          c.get("effectivenessScoreHint") or 50.0)
        except (TypeError, ValueError):
            score = 50.0
        score = max(0.0, min(score, 100.0))
        if source_authority == "llm-synth" and score > 60.0:
            score = 60.0
        if source_authority == "secondary" and score > 80.0:
            score = 80.0
        evidence = str((data or {}).get("evidenceSummary") or "")[:1000]
        graded.append({
            **c,
            "effectivenessScore": score,
            "sourceAuthority": source_authority,
            "sourceUrl": source_hint if source_authority != "llm-synth" else "",
            "evidenceSummary": evidence,
            "graderModel": str((gr or {}).get("model") or "unknown"),
        })
    return {"ok": True, "graded": graded}


async def task_lifehack_tip_persist(**kwargs: Any) -> dict[str, Any]:
    """Insert tip rows. Two modes:
      - bulk: kwargs['graded'] = [{...}, ...] (researchTopic path)
      - single: kwargs has topicId/bodyJa/... directly (submitTip path)
    Returns {ok, insertedCount} for bulk OR {ok, tipId, vertexId} for single.
    """
    graded = kwargs.get("graded")
    now_iso = _now_iso()

    def _row_for(c: dict[str, Any]) -> tuple[Any, ...]:
        topic_id = str(c.get("topicId") or "")
        body_ja = str(c.get("bodyJa") or "")
        body_en = str(c.get("bodyEn") or "") or None
        score = c.get("effectivenessScore")
        try:
            score_f = float(score) if score is not None else None
        except (TypeError, ValueError):
            score_f = None
        cost_min = c.get("costJpyMin")
        cost_max = c.get("costJpyMax")
        try:
            cost_min_f = float(cost_min) if cost_min is not None else None
            cost_max_f = float(cost_max) if cost_max is not None else None
        except (TypeError, ValueError):
            cost_min_f = None
            cost_max_f = None
        difficulty = str(c.get("difficulty") or "easy")[:16]
        source_url = str(c.get("sourceUrl") or "") or None
        source_authority = str(c.get("sourceAuthority") or "llm-synth")[:32]
        evidence_summary = str(c.get("evidenceSummary") or "") or None
        grader_model = str(c.get("graderModel") or "unknown")[:64]

        seed = f"tip|{topic_id}|{body_ja}|{source_url or ''}"
        tip_id = f"tip-{_hash12(seed)}"
        vertex_id = _tip_vertex_id(tip_id)
        return (
            vertex_id, _LIFEHACK_ACTOR, 0, tip_id, topic_id,
            body_ja, body_en, score_f, cost_min_f, cost_max_f,
            difficulty, source_url, source_authority, evidence_summary, grader_model,
            "active", now_iso, _LIFEHACK_ACTOR, _LIFEHACK_ACTOR, "lifehack.tip.persist",
        )

    if isinstance(graded, list):
        rows = [_row_for(c) for c in graded if isinstance(c, dict) and c.get("bodyJa")]
        _rw_executemany(_INSERT_TIP, rows)
        return {"ok": True, "insertedCount": len(rows)}

    # single mode (submitTip)
    row = _row_for(kwargs)
    _rw_execute(_INSERT_TIP, row)
    tip_id = row[3]
    vertex_id = row[0]
    return {"ok": True, "tipId": tip_id, "vertexId": vertex_id}


# ──────────────────────────────────────────────────────────────────────
# dailyDustPost — pickTrending / pickBest / compose / postLog persist
# ──────────────────────────────────────────────────────────────────────


async def task_lifehack_topic_pick_trending(**kwargs: Any) -> dict[str, Any]:
    hint = str(kwargs.get("topicIdHint") or "").strip()
    if hint:
        return {"ok": True, "topicId": hint}
    rows = _rw_query(
        "SELECT t.topic_id FROM vertex_lifehack_topic t "
        "LEFT JOIN mv_lifehack_trending_topic m ON m.topic_id = t.topic_id "
        "WHERE t.status = 'active' "
        "ORDER BY COALESCE(m.engagement_total, 0) DESC, "
        "         COALESCE(m.last_posted_at_ms, 0) ASC "
        "LIMIT 1"
    )
    topic_id = str(rows[0][0]) if rows else "dust-on-desk"
    return {"ok": True, "topicId": topic_id}


async def task_lifehack_tip_pick_best(**kwargs: Any) -> dict[str, Any]:
    """Pick the highest-effectiveness tip for the topic that has not been
    posted within dedupWindowMs. Returns skipped=true when no candidate."""
    topic_id = str(kwargs.get("topicId") or "dust-on-desk")
    tip_id_hint = str(kwargs.get("tipIdHint") or "").strip()
    dedup_ms = int(kwargs.get("dedupWindowMs") or 30 * 24 * 3_600_000)
    cutoff_ms = _now_ms() - dedup_ms

    if tip_id_hint:
        rows = _rw_query(
            "SELECT tip_id, body_ja FROM vertex_lifehack_tip "
            "WHERE tip_id = %s AND status = 'active' LIMIT 1",
            (tip_id_hint,),
        )
        if rows:
            return {"ok": True, "tipId": str(rows[0][0]),
                    "bodyJa": str(rows[0][1] or ""), "skipped": False}

    rows = _rw_query(
        f"SELECT t.tip_id, t.body_ja "
        f"FROM vertex_lifehack_tip t "
        f"LEFT JOIN mv_lifehack_recently_posted r ON r.tip_id = t.tip_id "
        f"WHERE t.topic_id = %s AND t.status = 'active' "
        f"  AND COALESCE(r.last_posted_at_ms, 0) < {int(cutoff_ms)} "
        f"ORDER BY COALESCE(t.effectiveness_score, 0) DESC, t.created_at ASC "
        f"LIMIT 1",
        (topic_id,),
    )
    if not rows:
        return {"ok": True, "tipId": "", "bodyJa": "", "skipped": True}
    return {"ok": True, "tipId": str(rows[0][0]),
            "bodyJa": str(rows[0][1] or ""), "skipped": False}


async def task_lifehack_post_compose(**kwargs: Any) -> dict[str, Any]:
    topic_id = str(kwargs.get("topicId") or "dust-on-desk")
    body_ja = str(kwargs.get("bodyJa") or "")
    compose_kind = str(kwargs.get("composeKind") or "tip-post")
    max_chars = int(kwargs.get("maxChars") or 280)
    min_humidity = kwargs.get("minHumidity")

    if compose_kind == "static-alert":
        try:
            mh = float(min_humidity) if min_humidity is not None else None
        except (TypeError, ValueError):
            mh = None
        user_msg = (
            f"観測湿度: {mh if mh is not None else '不明'}%\n"
            "静電気でホコリが付着しやすい状況です。280文字以内で警告 + 1行アクションを書いてください。"
        )
    else:
        user_msg = (
            f"Topic: {topic_id}\n"
            f"Tip body:\n{body_ja}\n"
            f"Rewrite as a {max_chars}-char Japanese social post."
        )

    result = llm.call_tier_json(
        "fast", _POST_COMPOSE_SYSTEM, user_msg,
        max_tokens=600, temperature=0.5,
    )
    data = (result or {}).get("data") if isinstance(result, dict) else None
    text = str((data or {}).get("postText") or "").strip()
    text = _strip_think_blocks(text)
    if not text:
        # fallback heuristic
        if compose_kind == "static-alert":
            text = "静電気警報。湿度が低いとホコリが机周りに集中します。加湿器で50%まで上げると体感1/3に減ります。"
        else:
            text = (body_ja[:max_chars - 20] + "…") if len(body_ja) > max_chars - 20 else body_ja
    if len(text) > max_chars:
        text = text[:max_chars - 1] + "…"
    return {"ok": True, "postText": text}


async def task_lifehack_post_log_persist(**kwargs: Any) -> dict[str, Any]:
    tip_id = str(kwargs.get("tipId") or "")
    topic_id = str(kwargs.get("topicId") or "")
    bsky_uri = str(kwargs.get("bskyUri") or "")
    bsky_cid = str(kwargs.get("bskyCid") or "") or None
    posted_at_ms = _now_ms()
    seed = f"post|{tip_id}|{bsky_uri}|{posted_at_ms}"
    post_id = f"post-{_hash12(seed)}"
    vertex_id = _post_log_vertex_id(post_id)
    now_iso = _now_iso()
    _rw_execute(_INSERT_POST_LOG, (
        vertex_id, _LIFEHACK_ACTOR, 0, post_id, tip_id, topic_id,
        bsky_uri, bsky_cid, posted_at_ms, 0.0, "active",
        now_iso, _LIFEHACK_ACTOR, _LIFEHACK_ACTOR, "lifehack.postLog.persist",
    ))
    return {"ok": True, "postId": post_id, "vertexId": vertex_id}


# ──────────────────────────────────────────────────────────────────────
# staticAlert — env humidity check
# ──────────────────────────────────────────────────────────────────────


async def task_lifehack_env_check_humidity(**kwargs: Any) -> dict[str, Any]:
    threshold = float(kwargs.get("thresholdPct") or 35.0)
    rows = _rw_query(
        "SELECT COUNT(*), MIN(min_humidity_pct), AVG(avg_humidity_pct) "
        "FROM mv_lifehack_static_risk_now "
        f"WHERE COALESCE(min_humidity_pct, 100.0) < {float(threshold)}"
    )
    risk_count = 0
    min_h: float | None = None
    avg_h: float | None = None
    if rows:
        try:
            risk_count = int(rows[0][0] or 0)
        except (TypeError, ValueError):
            risk_count = 0
        try:
            min_h = float(rows[0][1]) if rows[0][1] is not None else None
        except (TypeError, ValueError):
            min_h = None
        try:
            avg_h = float(rows[0][2]) if rows[0][2] is not None else None
        except (TypeError, ValueError):
            avg_h = None
    return {
        "ok": True,
        "riskCellCount": risk_count,
        "minHumidity": min_h,
        "avgHumidity": avg_h,
    }


# ──────────────────────────────────────────────────────────────────────
# submitTip — validate authority + grade effectiveness
# ──────────────────────────────────────────────────────────────────────


async def task_lifehack_tip_validate_authority(**kwargs: Any) -> dict[str, Any]:
    source_url = str(kwargs.get("sourceUrl") or "").strip()
    source_authority = str(kwargs.get("sourceAuthority") or "secondary")
    valid = bool(source_url) and (
        source_url.startswith("http://") or source_url.startswith("https://")
    )
    return {
        "ok": True,
        "valid": valid,
        "normalizedSourceUrl": source_url if valid else "",
        "sourceAuthority": source_authority if valid else "llm-synth",
    }


async def task_lifehack_tip_grade_effectiveness(**kwargs: Any) -> dict[str, Any]:
    body_ja = str(kwargs.get("bodyJa") or "")
    source_authority = str(kwargs.get("sourceAuthority") or "llm-synth")
    user_msg = (
        f"Tip:\n{body_ja}\n"
        f"Authority: {source_authority}\nGrade JSON."
    )
    result = llm.call_tier_json(
        "fast", _TIP_GRADE_SYSTEM, user_msg,
        max_tokens=400, temperature=0.1,
    )
    data = (result or {}).get("data") if isinstance(result, dict) else None
    try:
        score = float((data or {}).get("effectivenessScore") or 50.0)
    except (TypeError, ValueError):
        score = 50.0
    score = max(0.0, min(score, 100.0))
    if source_authority == "llm-synth" and score > 60.0:
        score = 60.0
    if source_authority == "secondary" and score > 80.0:
        score = 80.0
    evidence = str((data or {}).get("evidenceSummary") or "")[:1000]
    return {
        "ok": True,
        "effectivenessScore": score,
        "evidenceSummary": evidence,
        "graderModel": str((result or {}).get("model") or "unknown"),
    }


# ──────────────────────────────────────────────────────────────────────
# recommend — rank tips + attach products
# ──────────────────────────────────────────────────────────────────────


async def task_lifehack_tip_rank(**kwargs: Any) -> dict[str, Any]:
    topic_id = str(kwargs.get("topicId") or "")
    if not topic_id:
        return {"ok": False, "topicId": "", "headline": "", "tips": []}
    budget_max = kwargs.get("budgetJpyMax")
    prefer_diy = bool(kwargs.get("preferDiy") or False)
    limit = max(1, min(int(kwargs.get("limit") or 5), 10))

    # Topic title for headline
    topic_rows = _rw_query(
        "SELECT title_ja FROM vertex_lifehack_topic WHERE topic_id = %s "
        "AND status = 'active' LIMIT 1",
        (topic_id,),
    )
    headline = str(topic_rows[0][0]) if topic_rows else topic_id

    # Top tips with optional cost filter
    where = ["topic_id = %s", "status = 'active'", "effectiveness_score IS NOT NULL"]
    params: list[Any] = [topic_id]
    if budget_max is not None:
        try:
            bm = float(budget_max)
            where.append(f"COALESCE(cost_jpy_min, 0) <= {bm}")
        except (TypeError, ValueError):
            pass
    where_sql = " AND ".join(where)
    rows = _rw_query(
        f"SELECT tip_id, body_ja, effectiveness_score, cost_jpy_min, cost_jpy_max, "
        f"       difficulty, source_url "
        f"FROM vertex_lifehack_tip WHERE {where_sql} "
        f"ORDER BY effectiveness_score DESC, created_at ASC "
        f"LIMIT {int(limit)}",
        tuple(params),
    )

    tips_out: list[dict[str, Any]] = []
    for tip_id, body_ja, score, cost_min, cost_max, difficulty, source_url in rows:
        prods = _rw_query(
            "SELECT p.product_id, p.name, p.source_type, p.amazon_search_keyword, "
            "       p.tsukuru_cad_model_did "
            "FROM edge_lifehack_tip_recommends_product e "
            "JOIN vertex_lifehack_product p ON p.vertex_id = e.dst_vid "
            "WHERE e.src_vid = %s AND p.status = 'active' "
            "LIMIT 5",
            (_tip_vertex_id(str(tip_id)),),
        )
        products = []
        for pid, pname, ps_type, akw, cad_did in prods:
            if prefer_diy and str(ps_type) != "diy_tsukuru":
                continue
            products.append({
                "productId": str(pid or ""),
                "name": str(pname or ""),
                "sourceType": str(ps_type or "commercial"),
                "amazonSearchKeyword": str(akw or ""),
                "tsukuruCadModelDid": str(cad_did or ""),
            })
        tips_out.append({
            "tipId": str(tip_id),
            "bodyJa": str(body_ja or ""),
            "effectivenessScore": float(score or 0.0),
            "costJpyMin": float(cost_min) if cost_min is not None else None,
            "costJpyMax": float(cost_max) if cost_max is not None else None,
            "difficulty": str(difficulty or "easy"),
            "sourceUrl": str(source_url or ""),
            "products": products,
        })

    return {
        "ok": True,
        "topicId": topic_id,
        "headline": headline,
        "tips": tips_out,
    }


# ──────────────────────────────────────────────────────────────────────
# agentLoop — Path F unified chat (memory + audit + scheduler)
# ──────────────────────────────────────────────────────────────────────


async def task_lifehack_agent_chat(**kwargs: Any) -> dict[str, Any]:
    prompt = str(kwargs.get("prompt") or "")
    tier = str(kwargs.get("tier") or "balanced")
    topic_focus = str(kwargs.get("topicFocus") or "").strip()
    max_tokens = int(kwargs.get("maxTokens") or 1500)
    if not prompt:
        return {"ok": False, "content": "", "error": "prompt required"}

    # context: top tips for focused topic (or trending)
    if topic_focus:
        ctx_rows = _rw_query(
            "SELECT topic_id, body_ja, effectiveness_score, source_url "
            "FROM vertex_lifehack_tip WHERE topic_id = %s AND status = 'active' "
            "ORDER BY effectiveness_score DESC LIMIT 6",
            (topic_focus,),
        )
    else:
        ctx_rows = _rw_query(
            "SELECT topic_id, body_ja, effectiveness_score, source_url "
            "FROM vertex_lifehack_tip WHERE status = 'active' "
            "ORDER BY effectiveness_score DESC LIMIT 6"
        )
    topic_set: set[str] = set()
    tips_used = 0
    ctx_lines: list[str] = []
    for tid, body, score, src in ctx_rows:
        topic_set.add(str(tid))
        tips_used += 1
        ctx_lines.append(
            f"- [{tid} score={float(score or 0.0):.0f}] {str(body or '')[:240]} "
            f"({str(src or 'no-source')})"
        )

    user_msg = (
        f"Context tips:\n" + "\n".join(ctx_lines) + f"\n\nUser asks:\n{prompt}"
        if ctx_lines else f"User asks:\n{prompt}"
    )

    result = llm.call_tier(
        tier, _AGENT_CHAT_SYSTEM, user_msg,
        max_tokens=max_tokens, temperature=0.4,
    )
    content = _strip_think_blocks(str((result or {}).get("content") or ""))
    return {
        "ok": bool((result or {}).get("ok", False)),
        "content": content,
        "model": str((result or {}).get("model") or "unknown"),
        "latencyMs": int((result or {}).get("latencyMs") or 0),
        "topicsUsed": len(topic_set),
        "tipsUsed": tips_used,
    }


# ──────────────────────────────────────────────────────────────────────
# submitEnvironmentReading — persist + flag static risk
# ──────────────────────────────────────────────────────────────────────


def _h3_from_lat_lon(lat: float | None, lon: float | None,
                     existing: str | None) -> str:
    if existing:
        return str(existing)
    if lat is None or lon is None:
        return ""
    # Coarse fallback: discretize to 0.5° grid → "geo:LAT_LON" stable token.
    try:
        return f"geo:{round(float(lat) * 2) / 2:.1f}_{round(float(lon) * 2) / 2:.1f}"
    except (TypeError, ValueError):
        return ""


async def task_lifehack_env_persist_reading(**kwargs: Any) -> dict[str, Any]:
    location_h3 = _h3_from_lat_lon(
        kwargs.get("lat"), kwargs.get("lon"), kwargs.get("locationH3")
    )
    try:
        humidity = float(kwargs.get("humidityPct"))
    except (TypeError, ValueError):
        return {"ok": False, "error": "humidityPct required"}
    temp = kwargs.get("tempC")
    pm25 = kwargs.get("pm25Ugm3")
    try:
        temp_f = float(temp) if temp is not None else None
    except (TypeError, ValueError):
        temp_f = None
    try:
        pm25_f = float(pm25) if pm25 is not None else None
    except (TypeError, ValueError):
        pm25_f = None
    source = str(kwargs.get("source") or "user-submit")[:64]

    ts_ms = _now_ms()
    seed = f"reading|{location_h3}|{humidity}|{ts_ms}"
    reading_id = f"r-{_hash12(seed)}"
    vertex_id = _reading_vertex_id(reading_id)
    static_risk = humidity < 35.0
    now_iso = _now_iso()
    _rw_execute(_INSERT_READING, (
        vertex_id, _LIFEHACK_ACTOR, 0, reading_id, _LIFEHACK_ACTOR,
        location_h3, humidity, temp_f, pm25_f, ts_ms, source,
        "active", now_iso, _LIFEHACK_ACTOR, _LIFEHACK_ACTOR, "lifehack.env.persistReading",
    ))
    return {
        "ok": True,
        "readingId": reading_id,
        "vertexId": vertex_id,
        "staticRisk": static_risk,
    }


# ──────────────────────────────────────────────────────────────────────
# coverage — read-only snapshot for soak monitor / dashboard
# ──────────────────────────────────────────────────────────────────────


async def task_lifehack_coverage_snapshot(**kwargs: Any) -> dict[str, Any]:
    cutoff_ms = _now_ms() - 24 * 3_600_000
    topics_active = _scalar_count(
        "SELECT count(*) FROM vertex_lifehack_topic WHERE status = 'active'")
    tips_active = _scalar_count(
        "SELECT count(*) FROM vertex_lifehack_tip WHERE status = 'active'")
    products_active = _scalar_count(
        "SELECT count(*) FROM vertex_lifehack_product WHERE status = 'active'")
    posts_total = _scalar_count(
        "SELECT count(*) FROM vertex_lifehack_post_log WHERE status = 'active'")
    posts_24h = _scalar_count(
        f"SELECT count(*) FROM vertex_lifehack_post_log "
        f"WHERE status = 'active' AND posted_at_ms > {int(cutoff_ms)}"
    )
    last_posted_ms = _scalar_max(
        "SELECT max(posted_at_ms) FROM vertex_lifehack_post_log "
        "WHERE status = 'active'"
    )
    env_readings = _scalar_count(
        "SELECT count(*) FROM vertex_lifehack_environment_reading "
        "WHERE status = 'active'"
    )
    static_risk_cells = _scalar_count(
        "SELECT count(*) FROM mv_lifehack_static_risk_now"
    )
    return {
        "asOf":             _now_iso(),
        "topicsActive":     topics_active,
        "tipsActive":       tips_active,
        "productsActive":   products_active,
        "postsTotal":       posts_total,
        "postsLast24h":     posts_24h,
        "lastPostedAtMs":   last_posted_ms,
        "envReadings":      env_readings,
        "staticRiskCells":  static_risk_cells,
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Wire all lifehack task types onto the shared LangServer worker.

    Static manifest below repeats each task_type as a literal so the
    BPMN worker-task coverage linter discovers camelCase names.

      task_type="lifehack.topic.findStale"
      task_type="lifehack.topic.pickTrending"
      task_type="lifehack.tip.synth"
      task_type="lifehack.tip.gradeAuthority"
      task_type="lifehack.tip.gradeEffectiveness"
      task_type="lifehack.tip.validateAuthority"
      task_type="lifehack.tip.persist"
      task_type="lifehack.tip.pickBest"
      task_type="lifehack.tip.rank"
      task_type="lifehack.post.compose"
      task_type="lifehack.postLog.persist"
      task_type="lifehack.env.checkHumidity"
      task_type="lifehack.env.persistReading"
      task_type="lifehack.agent.chat"
      task_type="lifehack.coverage.snapshot"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("lifehack.topic.findStale",        task_lifehack_topic_find_stale)
    t("lifehack.topic.pickTrending",     task_lifehack_topic_pick_trending)
    t("lifehack.tip.synth",              task_lifehack_tip_synth,            ms=180_000)
    t("lifehack.tip.gradeAuthority",     task_lifehack_tip_grade_authority,  ms=180_000)
    t("lifehack.tip.gradeEffectiveness", task_lifehack_tip_grade_effectiveness, ms=60_000)
    t("lifehack.tip.validateAuthority",  task_lifehack_tip_validate_authority)
    t("lifehack.tip.persist",            task_lifehack_tip_persist)
    t("lifehack.tip.pickBest",           task_lifehack_tip_pick_best)
    t("lifehack.tip.rank",               task_lifehack_tip_rank,             ms=30_000)
    t("lifehack.post.compose",           task_lifehack_post_compose,         ms=60_000)
    t("lifehack.postLog.persist",        task_lifehack_post_log_persist)
    t("lifehack.env.checkHumidity",      task_lifehack_env_check_humidity)
    t("lifehack.env.persistReading",     task_lifehack_env_persist_reading,  ms=15_000)
    t("lifehack.agent.chat",             task_lifehack_agent_chat,           ms=60_000)
    t("lifehack.coverage.snapshot",      task_lifehack_coverage_snapshot,    ms=15_000)


__all__ = [
    "register",
    "task_lifehack_topic_find_stale",
    "task_lifehack_topic_pick_trending",
    "task_lifehack_tip_synth",
    "task_lifehack_tip_grade_authority",
    "task_lifehack_tip_grade_effectiveness",
    "task_lifehack_tip_validate_authority",
    "task_lifehack_tip_persist",
    "task_lifehack_tip_pick_best",
    "task_lifehack_tip_rank",
    "task_lifehack_post_compose",
    "task_lifehack_post_log_persist",
    "task_lifehack_env_check_humidity",
    "task_lifehack_env_persist_reading",
    "task_lifehack_agent_chat",
    "task_lifehack_coverage_snapshot",
]
