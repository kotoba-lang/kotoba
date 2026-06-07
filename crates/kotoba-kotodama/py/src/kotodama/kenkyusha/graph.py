"""kenkyusha research LangGraph — 6-role co-scientist Pregel loop.

Graph topology (Google co-scientist roles, BSP super-steps):

    START → seed_frontier ─┬─ no_frontier → END
                            └─ frontier ──→ generation
                                              ↓
                                            reflection
                                              ↓
                                            ranking
                                              ↓
                                            evolution
                                              ↓
                                            proximity
                                              ↓
                                            meta_review → END

Each super-step is a self-contained LangGraph node that reads / writes
shared Pregel state (KenkyushaState). The "Pregel" abstraction maps to
LangGraph's BSP execution: every node is a function over the full
state, edges define vertex-program flow.

Persistence model (ADR-2605111200 — pod-only RW):

  vertex_kenkyusha_frontier   ← seed_frontier  (when newly detected)
  vertex_kenkyusha_hypothesis ← generation, evolution
                              ← ranking        (elo_rating UPDATE)
  vertex_kenkyusha_evidence   ← proximity      (per supporting/contradicting row)
  edge_kenkyusha_supports     ← proximity
  edge_kenkyusha_contradicts  ← proximity
  vertex_kenkyusha_frontier   ← meta_review    (status / consensus_level UPDATE)

Frontier detection sources (seed_frontier):
  - citationGap         — Bunken cluster with no inward CITES edges
  - temporalDecay       — high citation, no new paper in 5y
  - crossDisciplineVoid — bunken pairs across disciplines, low density
  - legalScienceGap     — hanrei with contested science, no consensus
  - llmUncertainty      — Murakumo LLM high-entropy answer (sampled)

ADR refs:
  - 2605080600 LangGraph Server + Granian L3 Runtime
  - 2605082000 LangGraph Graph Definition as Data
  - 2605082100 LangGraph Checkpointer Storage (lg_kenkyusha_checkpoint)
  - 2605111200 CF Worker = Edge-Only (this pod owns the RW writes)
  - 0019       Identifier Topology (did:web:kenkyusha.etzhayyim.com:...)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

_log = logging.getLogger(__name__)


# ── Config (resolveModelId pattern — no hardcoded model names) ───────────────
_LLM_URL   = os.getenv("etzhayyim_LLM_URL", "https://gemma.etzhayyim.com/v1")
_LLM_MODEL = os.getenv("etzhayyim_LLM_MODEL", "gemma-4-E2B-it")
_LLM_KEY   = os.getenv("etzhayyim_LLM_API_KEY", "")

_DB_URL = os.getenv(
    "DATABASE_URL",
    "REDACTED_USE_DATABASE_URL_ENV",
)

ACTOR_KENKYUSHA = os.getenv("KENKYUSHA_OWNER_DID", "did:web:kenkyusha.etzhayyim.com")

# Hypothesis tournament configuration.
HYPOTHESES_PER_FRONTIER  = int(os.getenv("KENKYUSHA_HYPOTHESES_PER_FRONTIER", "4"))
EVIDENCE_FETCH_LIMIT     = int(os.getenv("KENKYUSHA_EVIDENCE_LIMIT", "8"))
ELO_K                    = int(os.getenv("KENKYUSHA_ELO_K", "32"))

# Phase 2C — disagreement-as-discovery (scienceearth.org).
# When Reflection finds a critique containing a structural-flaw keyword OR
# the per-hypothesis score_delta variance exceeds the threshold, the
# disagreement_split node persists a child frontier with depth = parent+1.
# Recursion is bounded by MAX_DISAGREEMENT_DEPTH so we never explode LLM
# spend; sub-frontiers beyond the cap are silently dropped.
MAX_DISAGREEMENT_DEPTH       = int(os.getenv("KENKYUSHA_MAX_DISAGREEMENT_DEPTH", "2"))
DISAGREEMENT_VARIANCE_THRESH = int(os.getenv("KENKYUSHA_DISAGREEMENT_VARIANCE", "400"))
DISAGREEMENT_MAX_SPLITS      = int(os.getenv("KENKYUSHA_DISAGREEMENT_MAX_SPLITS", "3"))

# Phase 2D — evidence sources for the proximity node. Each entry maps a
# logical source_type to:
#   table        — source table (graphar.<table>)
#   title_col    — column carrying the human-readable title
#   did_col      — column carrying the canonical DID (or "" if vertex_id-keyed)
#   year_col     — year column (or "" / date column to substring)
#   embed_kind   — kind filter on vertex_actor_embedding when this source's
#                  rows have been embedded (NULL/empty = no vector path)
# A source is gracefully skipped (no rows emitted) when its table doesn't
# exist in the live schema — see _table_exists().
_EVIDENCE_SOURCES: tuple[dict[str, str], ...] = (
    {
        "source_type": "bunken",
        "table":       "vertex_bunken_record",
        "title_col":   "title",
        "did_col":     "did",
        "year_col":    "year",
        "embed_kind":  "bunken",
    },
    {
        # Legacy table name retained from Phase 1 — the live RisingWave
        # schema may have either ``vertex_bunken`` (Phase-1 code) or
        # ``vertex_bunken_record`` (alembic source). _table_exists makes
        # one of the two no-op while preserving the other.
        "source_type": "bunken",
        "table":       "vertex_bunken",
        "title_col":   "title",
        "did_col":     "did",
        "year_col":    "published_year",
        "embed_kind":  "",
    },
    {
        "source_type": "hanrei",
        "table":       "vertex_hanrei_case_record",
        "title_col":   "title",
        "did_col":     "",   # vertex_id only
        "year_col":    "decision_date",   # SUBSTR(_,1,4) at query time
        "embed_kind":  "hanrei",
    },
    {
        "source_type": "isbn",
        "table":       "vertex_isbn_book",
        "title_col":   "title",
        "did_col":     "",
        "year_col":    "publication_year",
        "embed_kind":  "isbn",
    },
    {
        "source_type": "intel",
        "table":       "vertex_intel_subject",
        "title_col":   "label",
        "did_col":     "source_did",
        "year_col":    "",
        "embed_kind":  "intel",
    },
)


# Phase 2H — arxiv submission gating. The arxiv_submit node fires only when
# all of the following hold:
#   - consensus_level == "strong"
#   - next_action     == "publish"
#   - depth           == 0          (sub-frontiers don't auto-submit; partial)
#   - ARXIV_SUBMIT_ENABLED env != "0"
ARXIV_SUBMIT_ENABLED = os.getenv("KENKYUSHA_ARXIV_SUBMIT_ENABLED", "1") != "0"
ARXIV_DEFAULT_CATEGORY = os.getenv("KENKYUSHA_ARXIV_CATEGORY", "cs.AI")


# Critique keywords (English + Japanese) that map to canonical split_reason.
_DISAGREEMENT_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("circular reasoning", "circular argument", "begging the question",
      "assumes the conclusion", "restates the question",
      "循環論証", "前提と結論が同じ", "問いを繰り返"),
     "circular_reasoning"),
    (("hidden assumption", "unstated assumption", "implicit assumption",
      "conflates",
      "隠れ仮定", "暗黙の仮定", "前提の混同"),
     "hidden_assumption"),
    (("contradicts established", "contradicts the evidence",
      "contradicts prior", "incompatible with",
      "既存研究と矛盾", "矛盾する"),
     "evidence_contradict"),
)

# Evidence retrieval — peer actor XRPC base (bunken/arxiv/hanrei). Pod talks to
# the canonical edge router; per-actor routing happens server-side.
_XRPC_BASE = os.getenv("XRPC_BASE", "https://atproto.etzhayyim.com/xrpc")


# ── State (Pregel global state — all nodes see/write it) ─────────────────────


class Hypothesis(TypedDict, total=False):
    id: str
    statement: str
    rationale: str
    elo: int
    confidence: int       # 0-1000 permille
    parent_id: str        # for evolution lineage
    mutation_kind: str    # "seed" | "mutation" | "crossover"
    super_step: int
    supporting: int       # evidence count
    contradicting: int
    status: str           # "proposed" | "supported" | "refuted" | "inconclusive"


class Evidence(TypedDict, total=False):
    id: str
    hypothesis_id: str
    source_type: str      # bunken | arxiv | hanrei | intel | external
    source_did: str
    source_uri: str
    source_title: str
    source_year: int
    relevance: int        # 0-1000 permille
    evidence_type: str    # "supports" | "contradicts" | "neutral"
    extracted_claim: str


class KenkyushaState(TypedDict, total=False):
    # ── Input ──
    frontierTitle: str            # optional pre-seeded frontier
    primaryDiscipline: str        # ISCED-F 4-digit, default 0613
    maxHypotheses: int
    # Phase 2C lineage — set when this run was spawned by a parent disagreement.
    parentFrontierId: str
    depth: int
    splitReason: str

    # ── seed_frontier output ──
    frontier_id: str
    frontier_did: str
    detection_method: str         # citationGap | temporalDecay | pending_sub | ...
    frontier_status: str          # "detected" | "no_frontier"
    source_did: str

    # ── generation / evolution output ──
    hypotheses: list[Hypothesis]

    # ── reflection output ──
    critiques: list[dict[str, Any]]   # [{hypothesis_id, critique, score_delta}]

    # ── disagreement_split output (Phase 2C) ──
    disagreements: list[dict[str, Any]]     # raw signals: hypothesis_id + reason + critique
    sub_frontiers_spawned: list[dict[str, Any]]

    # ── ranking output ──
    tournament_rounds: int
    winner_hypothesis_id: str

    # ── proximity output (evidence per hypothesis) ──
    evidence: list[Evidence]

    # ── meta_review output ──
    consensus_level: str           # none | disputed | emerging | partial | strong
    next_action: str               # "publish" | "iterate" | "abandon"

    # ── Bookkeeping ──
    llm_calls: int
    duration_ms_per_node: dict[str, int]
    error: str


# ── Helpers ──────────────────────────────────────────────────────────────────


def _hash(val: str) -> str:
    return hashlib.sha256(val.encode()).hexdigest()[:24]


def _utc_now_str() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _llm(temperature: float = 0.4, max_tokens: int = 768) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=_LLM_URL,
        api_key=_LLM_KEY or "none",
        model=_LLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _json_or_empty(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        # Tolerate models that wrap JSON in code fences.
        stripped = text.strip().strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
        try:
            return json.loads(stripped)
        except Exception:
            return None


# ── Node 1: seed_frontier ────────────────────────────────────────────────────
# Detect or accept an unresolved research frontier.
async def seed_frontier(state: KenkyushaState) -> dict[str, Any]:
    """Resolve the frontier to run on, by priority:

      1. Explicit `frontierTitle` in input (manual / publishFrontier path).
         Also honors `parentFrontierId`/`depth`/`splitReason` from input —
         when a sub-frontier row exists, the existing row is reused.
      2. Pending sub-frontier created by an earlier disagreement_split node
         (status='detected', parent_frontier_id IS NOT NULL, oldest first).
         These have highest cron-tick priority because they encode an
         already-detected research question.
      3. Citation-gap candidate from vertex_bunken — fallback.
    """
    t0 = time.time()
    discipline = state.get("primaryDiscipline") or "0613"
    title = (state.get("frontierTitle") or "").strip()
    parent_id    = (state.get("parentFrontierId") or "").strip()
    depth        = int(state.get("depth") or 0)
    split_reason = (state.get("splitReason") or "").strip()
    detection = "manual" if title else "citationGap"
    source_did = ""

    if not title:
        # Priority 2 — pending sub-frontier from a previous disagreement_split.
        try:
            conn = await asyncpg.connect(_DB_URL)
            try:
                pending = await conn.fetchrow(
                    """
                    SELECT frontier_id, title, parent_frontier_id, split_reason,
                           depth, primary_discipline
                    FROM graphar.vertex_kenkyusha_frontier
                    WHERE status = 'detected'
                      AND parent_frontier_id IS NOT NULL
                      AND parent_frontier_id <> ''
                    ORDER BY detected_at ASC
                    LIMIT 1
                    """,
                )
            finally:
                await conn.close()
            if pending:
                title        = pending["title"] or ""
                parent_id    = pending["parent_frontier_id"] or ""
                split_reason = pending["split_reason"] or ""
                depth        = int(pending["depth"] or 0)
                discipline   = pending["primary_discipline"] or discipline
                detection    = f"sub_frontier_{split_reason}" if split_reason else "sub_frontier"
        except Exception as exc:
            _log.warning("[kenkyusha][seed_frontier] pending sub scan: %s", exc)

    if not title:
        # Priority 3 — citation-gap detection from vertex_bunken.
        try:
            conn = await asyncpg.connect(_DB_URL)
            try:
                row = await conn.fetchrow(
                    """
                    SELECT title, did, country
                    FROM graphar.vertex_bunken
                    WHERE citation_count > 5
                      AND NOT EXISTS (
                          SELECT 1 FROM graphar.edge_bunken_cites
                          WHERE dst = vertex_bunken.did
                      )
                    ORDER BY citation_count DESC
                    LIMIT 1
                    """,
                )
            finally:
                await conn.close()
            if row:
                title = row["title"] or ""
                source_did = row["did"] or ""
        except Exception as exc:
            _log.warning("[kenkyusha][seed_frontier] gap scan: %s", exc)

    if not title:
        return {
            "frontier_status": "no_frontier",
            "duration_ms_per_node": {"seed_frontier": int((time.time() - t0) * 1000)},
        }

    # Sub-frontiers reuse the same hash construction so the row written by
    # disagreement_split is the row we INSERT-IF-NOT-EXISTS here. For
    # citation-gap / manual paths, parent_id is empty.
    if parent_id:
        frontier_id = _hash(parent_id + title + (split_reason or ""))
    else:
        frontier_id = _hash(title + discipline)
    frontier_did = f"{ACTOR_KENKYUSHA}:frontier:{frontier_id}"
    vid = f"at://{frontier_did}/com.etzhayyim.apps.kenkyusha.frontier/{frontier_id}"
    now = _utc_now_str()

    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO graphar.vertex_kenkyusha_frontier
                    (vertex_id, rkey, repo, frontier_id, did,
                     title, description, detection_method,
                     primary_discipline, secondary_disciplines,
                     urgency, evidence_level, consensus_level,
                     hypothesis_count, evidence_count, status,
                     source_did, detected_at, last_analyzed_at,
                     parent_frontier_id, split_reason, depth,
                     actor_did, org_did, created_at, sensitivity_ord)
                SELECT $1,$2,$3,$4,$5,
                       $6,'',$7,
                       $8,'',
                       'medium','none','none',
                       0,0,'detected',
                       $9,$10,$10,
                       $11,$12,$13,
                       $14,$14,$10,0
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.vertex_kenkyusha_frontier
                    WHERE frontier_id = $4
                )
                """,
                vid, frontier_id, ACTOR_KENKYUSHA, frontier_id, frontier_did,
                title[:240], detection,
                discipline,
                source_did, now,
                parent_id or "", split_reason or "", depth,
                ACTOR_KENKYUSHA,
            )
            await conn.execute("FLUSH")
        finally:
            await conn.close()
    except Exception as exc:
        _log.warning("[kenkyusha][seed_frontier] insert: %s", exc)

    return {
        "frontier_id":       frontier_id,
        "frontier_did":      frontier_did,
        "frontierTitle":     title,
        "detection_method":  detection,
        "frontier_status":   "detected",
        "source_did":        source_did,
        "parentFrontierId":  parent_id,
        "splitReason":       split_reason,
        "depth":             depth,
        "primaryDiscipline": discipline,
        "hypotheses":        [],
        "critiques":         [],
        "evidence":          [],
        "duration_ms_per_node": {"seed_frontier": int((time.time() - t0) * 1000)},
    }


# ── Node 2: generation ───────────────────────────────────────────────────────
GENERATION_SYSTEM = """You are the Generation role of a multi-agent research network.
Given an unresolved research frontier, propose N distinct testable hypotheses.

Each hypothesis MUST be:
  - Falsifiable (an experiment or observation could refute it)
  - Specific (mechanism + scope, not vague claims)
  - Novel relative to the source citation

Output a JSON array of exactly N objects with fields:
  statement   — one sentence, concrete prediction
  rationale   — 1-2 sentences explaining the mechanism
  confidence  — integer 0-1000 (your prior, permille)

No markdown, no prose outside the JSON array.
"""


def _coerce_hypotheses(parsed: Any, n: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(parsed, list):
        for h in parsed[:n]:
            if not isinstance(h, dict):
                continue
            stmt = str(h.get("statement", "")).strip()
            if not stmt:
                continue
            out.append({
                "statement":  stmt[:480],
                "rationale":  str(h.get("rationale", ""))[:600],
                "confidence": max(0, min(1000, int(h.get("confidence", 500)))),
            })
    return out


async def generation(state: KenkyushaState) -> dict[str, Any]:
    t0 = time.time()
    if state.get("frontier_status") != "detected":
        return {}

    n = max(2, min(state.get("maxHypotheses") or HYPOTHESES_PER_FRONTIER, 8))
    title = state.get("frontierTitle", "")

    prompt = (
        f"Research frontier: {title}\n"
        f"Primary discipline (ISCED-F 4-digit): {state.get('primaryDiscipline','0613')}\n"
        f"N: {n}\n"
        f"Detection method: {state.get('detection_method','citationGap')}\n"
    )
    items: list[dict[str, Any]] = []
    try:
        result = _llm(temperature=0.55, max_tokens=900).invoke([
            SystemMessage(content=GENERATION_SYSTEM),
            HumanMessage(content=prompt),
        ])
        items = _coerce_hypotheses(_json_or_empty(result.content), n)
    except Exception as exc:
        _log.warning("[kenkyusha][generation] LLM: %s", exc)

    hyps: list[Hypothesis] = []
    super_step = 1
    frontier_id = state.get("frontier_id", "")
    now = _utc_now_str()

    # Persist; collect ids back to state for downstream nodes.
    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            for h in items:
                hid = _hash(frontier_id + h["statement"] + str(super_step))
                vid = f"at://{ACTOR_KENKYUSHA}/com.etzhayyim.apps.kenkyusha.hypothesis/{hid}"
                await conn.execute(
                    """
                    INSERT INTO graphar.vertex_kenkyusha_hypothesis
                        (vertex_id, rkey, repo, hypothesis_id, frontier_id,
                         statement, rationale,
                         supporting_evidence, contradicting_evidence,
                         confidence_score, elo_rating,
                         super_step, parent_hypothesis_id, mutation_kind,
                         llm_model, status,
                         actor_did, org_did, created_at, sensitivity_ord)
                    SELECT $1,$2,$3,$4,$5,
                           $6,$7,
                           0,0,
                           $8,1200,
                           $9,'','seed',
                           $10,'proposed',
                           $11,$11,$12,0
                    WHERE NOT EXISTS (
                        SELECT 1 FROM graphar.vertex_kenkyusha_hypothesis
                        WHERE hypothesis_id = $4
                    )
                    """,
                    vid, hid, ACTOR_KENKYUSHA, hid, frontier_id,
                    h["statement"], h["rationale"],
                    h["confidence"],
                    super_step,
                    _LLM_MODEL,
                    ACTOR_KENKYUSHA, now,
                )
                hyps.append({
                    "id": hid,
                    "statement": h["statement"],
                    "rationale": h["rationale"],
                    "elo": 1200,
                    "confidence": h["confidence"],
                    "parent_id": "",
                    "mutation_kind": "seed",
                    "super_step": super_step,
                    "supporting": 0,
                    "contradicting": 0,
                    "status": "proposed",
                })
            await conn.execute("FLUSH")
        finally:
            await conn.close()
    except Exception as exc:
        _log.warning("[kenkyusha][generation] insert: %s", exc)

    durations = dict(state.get("duration_ms_per_node") or {})
    durations["generation"] = int((time.time() - t0) * 1000)
    return {
        "hypotheses": hyps,
        "llm_calls": int(state.get("llm_calls", 0)) + 1,
        "duration_ms_per_node": durations,
    }


# ── Node 3: reflection (critical review, à la scienceearth circular-reasoning) ─
REFLECTION_SYSTEM = """You are the Reflection role — a critical reviewer.
Given a research frontier and a list of hypotheses, identify which hypotheses:
  - Contain circular reasoning (premise = conclusion)
  - Are unfalsifiable in practice
  - Restate the question rather than answering
  - Conflate correlation with causation
  - Have hidden assumptions

For EACH hypothesis, output {hypothesis_id, critique, score_delta} where
score_delta is in [-300, 300] permille (negative = weaker, positive = stronger).
No hypothesis is fixed; this drives Ranking + Evolution.

Output JSON array only. No markdown.
"""


async def reflection(state: KenkyushaState) -> dict[str, Any]:
    t0 = time.time()
    hyps = state.get("hypotheses") or []
    if not hyps:
        return {}

    payload = [
        {"hypothesis_id": h["id"], "statement": h["statement"], "rationale": h["rationale"]}
        for h in hyps
    ]
    prompt = (
        f"Frontier: {state.get('frontierTitle','')}\n"
        f"Hypotheses:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    critiques: list[dict[str, Any]] = []
    try:
        result = _llm(temperature=0.2, max_tokens=900).invoke([
            SystemMessage(content=REFLECTION_SYSTEM),
            HumanMessage(content=prompt),
        ])
        parsed = _json_or_empty(result.content)
        if isinstance(parsed, list):
            for c in parsed:
                if not isinstance(c, dict):
                    continue
                hid = str(c.get("hypothesis_id", ""))
                if not hid:
                    continue
                critiques.append({
                    "hypothesis_id": hid,
                    "critique":   str(c.get("critique", ""))[:600],
                    "score_delta": max(-300, min(300, int(c.get("score_delta", 0)))),
                })
    except Exception as exc:
        _log.warning("[kenkyusha][reflection] LLM: %s", exc)

    # Apply score_delta to confidence (clamped 0..1000).
    by_id = {c["hypothesis_id"]: c["score_delta"] for c in critiques}
    new_hyps: list[Hypothesis] = []
    for h in hyps:
        delta = by_id.get(h["id"], 0)
        new_confidence = max(0, min(1000, int(h.get("confidence", 500)) + delta))
        new_hyps.append({**h, "confidence": new_confidence})

    durations = dict(state.get("duration_ms_per_node") or {})
    durations["reflection"] = int((time.time() - t0) * 1000)
    return {
        "hypotheses": new_hyps,
        "critiques": critiques,
        "llm_calls": int(state.get("llm_calls", 0)) + 1,
        "duration_ms_per_node": durations,
    }


# ── Node 4: ranking — pairwise Elo tournament ────────────────────────────────
RANKING_SYSTEM = """You are the Ranking role — a pairwise judge.
You'll be given two competing hypotheses (A, B) for the same frontier.
Decide which is the stronger candidate, balancing:
  - Falsifiability
  - Specificity of the proposed mechanism
  - Novelty vs. existing source citations
  - Plausibility (mechanism is physically/biologically possible)

Reply with EXACTLY one JSON object:
  {"winner":"A","reason":"..."} or {"winner":"B","reason":"..."}.
No other keys. No markdown.
"""


def _elo_update(ra: int, rb: int, winner: str, k: int = ELO_K) -> tuple[int, int]:
    ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400))
    eb = 1.0 - ea
    sa = 1.0 if winner == "A" else 0.0
    sb = 1.0 - sa
    return int(ra + k * (sa - ea)), int(rb + k * (sb - eb))


async def ranking(state: KenkyushaState) -> dict[str, Any]:
    t0 = time.time()
    hyps = list(state.get("hypotheses") or [])
    if len(hyps) < 2:
        durations = dict(state.get("duration_ms_per_node") or {})
        durations["ranking"] = int((time.time() - t0) * 1000)
        return {"duration_ms_per_node": durations, "tournament_rounds": 0}

    # All pairs once (round-robin). For 4 hypotheses → 6 rounds.
    llm = _llm(temperature=0.1, max_tokens=128)
    rounds = 0
    for i in range(len(hyps)):
        for j in range(i + 1, len(hyps)):
            a, b = hyps[i], hyps[j]
            prompt = (
                f"Frontier: {state.get('frontierTitle','')}\n\n"
                f"A) {a['statement']}\n"
                f"   rationale: {a.get('rationale','')}\n\n"
                f"B) {b['statement']}\n"
                f"   rationale: {b.get('rationale','')}\n"
            )
            winner = "A"
            try:
                result = llm.invoke([
                    SystemMessage(content=RANKING_SYSTEM),
                    HumanMessage(content=prompt),
                ])
                parsed = _json_or_empty(result.content) or {}
                winner = "A" if str(parsed.get("winner", "A")).upper().startswith("A") else "B"
            except Exception as exc:
                _log.warning("[kenkyusha][ranking] LLM: %s", exc)
            new_a, new_b = _elo_update(a["elo"], b["elo"], winner)
            a["elo"], b["elo"] = new_a, new_b
            rounds += 1

    # Persist elo updates.
    now = _utc_now_str()
    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            for h in hyps:
                await conn.execute(
                    """
                    UPDATE graphar.vertex_kenkyusha_hypothesis
                    SET elo_rating = $2, confidence_score = $3
                    WHERE hypothesis_id = $1
                    """,
                    h["id"], h["elo"], h.get("confidence", 500),
                )
            await conn.execute("FLUSH")
        finally:
            await conn.close()
    except Exception as exc:
        _log.warning("[kenkyusha][ranking] update: %s", exc)

    hyps.sort(key=lambda h: h.get("elo", 0), reverse=True)
    durations = dict(state.get("duration_ms_per_node") or {})
    durations["ranking"] = int((time.time() - t0) * 1000)
    return {
        "hypotheses": hyps,
        "tournament_rounds": rounds,
        "winner_hypothesis_id": hyps[0]["id"] if hyps else "",
        "llm_calls": int(state.get("llm_calls", 0)) + rounds,
        "duration_ms_per_node": durations,
    }


# ── Node 5: evolution — mutate the winners, retire the losers ────────────────
EVOLUTION_SYSTEM = """You are the Evolution role.
Given the top-2 hypotheses from a pairwise tournament, propose ONE refined
hypothesis that is:
  - Inspired by the strongest mechanism in either parent
  - Strictly more specific (narrower scope OR sharper prediction)
  - Different enough that a critic would call it a new claim

Output ONE JSON object: {"statement":"...","rationale":"...","mutation_kind":"crossover","confidence":700}.
No markdown.
"""


async def evolution(state: KenkyushaState) -> dict[str, Any]:
    t0 = time.time()
    hyps = list(state.get("hypotheses") or [])
    if len(hyps) < 2:
        return {}

    top2 = hyps[:2]
    prompt = (
        f"Frontier: {state.get('frontierTitle','')}\n\n"
        f"Top-1 (elo={top2[0]['elo']}): {top2[0]['statement']}\n"
        f"   rationale: {top2[0].get('rationale','')}\n\n"
        f"Top-2 (elo={top2[1]['elo']}): {top2[1]['statement']}\n"
        f"   rationale: {top2[1].get('rationale','')}\n"
    )
    child: Optional[dict[str, Any]] = None
    try:
        result = _llm(temperature=0.6, max_tokens=350).invoke([
            SystemMessage(content=EVOLUTION_SYSTEM),
            HumanMessage(content=prompt),
        ])
        parsed = _json_or_empty(result.content) or {}
        stmt = str(parsed.get("statement", "")).strip()
        if stmt:
            child = {
                "statement":     stmt[:480],
                "rationale":     str(parsed.get("rationale", ""))[:600],
                "confidence":    max(0, min(1000, int(parsed.get("confidence", 700)))),
                "mutation_kind": str(parsed.get("mutation_kind", "crossover"))[:24],
            }
    except Exception as exc:
        _log.warning("[kenkyusha][evolution] LLM: %s", exc)

    new_hyps = hyps
    if child:
        super_step = 2
        frontier_id = state.get("frontier_id", "")
        hid = _hash(frontier_id + child["statement"] + str(super_step))
        vid = f"at://{ACTOR_KENKYUSHA}/com.etzhayyim.apps.kenkyusha.hypothesis/{hid}"
        parent_id = top2[0]["id"]
        now = _utc_now_str()
        try:
            conn = await asyncpg.connect(_DB_URL)
            try:
                await conn.execute(
                    """
                    INSERT INTO graphar.vertex_kenkyusha_hypothesis
                        (vertex_id, rkey, repo, hypothesis_id, frontier_id,
                         statement, rationale,
                         supporting_evidence, contradicting_evidence,
                         confidence_score, elo_rating,
                         super_step, parent_hypothesis_id, mutation_kind,
                         llm_model, status,
                         actor_did, org_did, created_at, sensitivity_ord)
                    SELECT $1,$2,$3,$4,$5,
                           $6,$7,
                           0,0,
                           $8,1250,
                           $9,$10,$11,
                           $12,'proposed',
                           $13,$13,$14,0
                    WHERE NOT EXISTS (
                        SELECT 1 FROM graphar.vertex_kenkyusha_hypothesis
                        WHERE hypothesis_id = $4
                    )
                    """,
                    vid, hid, ACTOR_KENKYUSHA, hid, frontier_id,
                    child["statement"], child["rationale"],
                    child["confidence"],
                    super_step, parent_id, child["mutation_kind"],
                    _LLM_MODEL,
                    ACTOR_KENKYUSHA, now,
                )
                await conn.execute("FLUSH")
            finally:
                await conn.close()
        except Exception as exc:
            _log.warning("[kenkyusha][evolution] insert: %s", exc)

        new_hyps = hyps + [{
            "id": hid,
            "statement":  child["statement"],
            "rationale":  child["rationale"],
            "elo":        1250,
            "confidence": child["confidence"],
            "parent_id":  parent_id,
            "mutation_kind": child["mutation_kind"],
            "super_step": super_step,
            "supporting": 0,
            "contradicting": 0,
            "status": "proposed",
        }]

    durations = dict(state.get("duration_ms_per_node") or {})
    durations["evolution"] = int((time.time() - t0) * 1000)
    return {
        "hypotheses": new_hyps,
        "llm_calls": int(state.get("llm_calls", 0)) + (1 if child else 0),
        "duration_ms_per_node": durations,
    }


# ── Node 6: proximity — pull evidence rows from bunken/arxiv/hanrei ──────────
async def _embedding_kind_has_rows(conn: asyncpg.Connection, kind: str) -> bool:
    """Probe whether vertex_actor_embedding contains rows of the given kind.

    Used to decide whether the vector-search branch is viable for a source.
    Cheap: an indexed lookup returns within milliseconds.
    """
    if not kind:
        return False
    try:
        row = await conn.fetchrow(
            "SELECT 1 FROM graphar.vertex_actor_embedding WHERE kind = $1 LIMIT 1",
            kind,
        )
        return row is not None
    except Exception:
        return False


async def _fetch_evidence_rows(
    conn: asyncpg.Connection,
    source: dict[str, str],
    frontier_title: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` candidate evidence rows for one source.

    Strategy (per source):
      1. Skip if the source table doesn't exist (_table_exists).
      2. If embeddings exist for the source kind → vector search via
         actor_embed UDF + ``<=>`` cosine distance, joining the source
         table on either ``did`` or ``vertex_id``.
      3. Otherwise → LIKE-pattern fallback against the source title column.

    All paths return the same row shape:
      {source_type, source_did, source_title, source_year}

    Exceptions are swallowed (logged) so one broken source never poisons
    the whole proximity step.
    """
    table     = source["table"]
    title_col = source["title_col"]
    did_col   = source["did_col"] or ""
    year_col  = source["year_col"] or ""
    stype     = source["source_type"]
    kind      = source["embed_kind"] or ""

    if not await _table_exists(conn, table):
        return []

    # Year projection — substring date columns down to a year integer.
    if year_col == "decision_date":
        year_expr = "COALESCE(NULLIF(SUBSTR(s.decision_date, 1, 4), '')::INTEGER, 0)"
    elif year_col:
        year_expr = f"COALESCE(s.{year_col}::INTEGER, 0)"
    else:
        year_expr = "0"

    did_expr = f"COALESCE(s.{did_col}, '')" if did_col else "''"

    # ── Vector path ──
    # NB: RisingWave rejects ``LIMIT $N`` (param) — inline ``limit`` as a
    # validated int literal. ``limit`` is bounded by EVIDENCE_FETCH_LIMIT
    # at the caller, never user-supplied.
    safe_limit = max(1, min(int(limit), 100))
    if kind and await _embedding_kind_has_rows(conn, kind):
        try:
            sql = f"""
                SELECT
                    {did_expr} AS source_did,
                    s.{title_col} AS source_title,
                    {year_expr} AS source_year,
                    '{stype}' AS source_type,
                    1 - (e.emb <=> actor_embed($1, NULL, NULL, 'query')::vector(384))
                        AS score
                FROM graphar.vertex_actor_embedding e
                JOIN graphar.{table} s ON s.vertex_id = e.vertex_id
                WHERE e.kind = $2
                  AND e.emb IS NOT NULL
                ORDER BY e.emb <=> actor_embed($1, NULL, NULL, 'query')::vector(384)
                LIMIT {safe_limit}
            """
            rows = await conn.fetch(sql, frontier_title[:600], kind)
            return [{
                "source_type":  stype,
                "source_did":   r["source_did"] or "",
                "source_title": r["source_title"] or "",
                "source_year":  int(r["source_year"] or 0),
                "score":        float(r.get("score") or 0.0),
            } for r in rows]
        except Exception as exc:
            _log.warning(
                "[kenkyusha][proximity] vector path failed for %s (%s) — "
                "falling back to LIKE: %s",
                table, kind, exc,
            )

    # ── LIKE fallback ──
    title_terms = frontier_title.lower().split()[:3]
    if not title_terms:
        return []
    like_pattern = "%" + "%".join(title_terms) + "%"
    try:
        sql = f"""
            SELECT
                {did_expr} AS source_did,
                s.{title_col} AS source_title,
                {year_expr} AS source_year,
                '{stype}' AS source_type
            FROM graphar.{table} s
            WHERE LOWER(s.{title_col}) LIKE $1
            LIMIT {safe_limit}
        """
        rows = await conn.fetch(sql, like_pattern)
        return [{
            "source_type":  stype,
            "source_did":   r["source_did"] or "",
            "source_title": r["source_title"] or "",
            "source_year":  int(r["source_year"] or 0),
            "score":        0.0,
        } for r in rows]
    except Exception as exc:
        _log.warning("[kenkyusha][proximity] LIKE fallback failed for %s: %s", table, exc)
        return []


async def proximity(state: KenkyushaState) -> dict[str, Any]:
    """Phase 2D — RW vector search + multi-source evidence retrieval.

    For each hypothesis (capped by top-3 elo), query 4-5 source kinds:
        bunken / hanrei / isbn / intel (+ legacy vertex_bunken if present)
    Each source uses vector search via actor_embed UDF when embeddings
    exist, else falls back to LIKE. The LLM then labels each row as
    supports / contradicts / neutral. Writes vertex_kenkyusha_evidence +
    edge_kenkyusha_{supports,contradicts}.
    """
    t0 = time.time()
    hyps = state.get("hypotheses") or []
    if not hyps:
        return {}

    frontier_title = state.get("frontierTitle", "")
    if not frontier_title.strip():
        return {}

    rows: list[dict[str, Any]] = []
    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            per_source_limit = max(2, EVIDENCE_FETCH_LIMIT // max(1, len(_EVIDENCE_SOURCES)))
            seen: set[tuple[str, str]] = set()   # dedup by (source_type, title)
            for src in _EVIDENCE_SOURCES:
                src_rows = await _fetch_evidence_rows(
                    conn, src, frontier_title, per_source_limit,
                )
                for r in src_rows:
                    k = (r["source_type"], r["source_title"][:120])
                    if k in seen:
                        continue
                    seen.add(k)
                    rows.append(r)
        finally:
            await conn.close()
    except Exception as exc:
        _log.warning("[kenkyusha][proximity] scan: %s", exc)
        rows = []

    if not rows:
        durations = dict(state.get("duration_ms_per_node") or {})
        durations["proximity"] = int((time.time() - t0) * 1000)
        return {"evidence": [], "duration_ms_per_node": durations}

    # Have the LLM label each (hypothesis × row) pair. Cap at top-3
    # hypotheses by elo to bound LLM cost.
    top_hyps = sorted(hyps, key=lambda h: h.get("elo", 0), reverse=True)[:3]
    label_system = """For each row, decide if the cited source supports,
contradicts, or is neutral toward the hypothesis. Output a JSON array of
{"row":N,"evidence_type":"supports|contradicts|neutral","relevance":0-1000,"claim":"<one sentence>"}."""
    evidence_out: list[Evidence] = []
    llm = _llm(temperature=0.15, max_tokens=900)
    now = _utc_now_str()

    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            for h in top_hyps:
                listing = "\n".join(
                    f"{i}) {r['source_title']} ({r['source_type']}, {r['source_year']})"
                    for i, r in enumerate(rows)
                )
                prompt = f"Hypothesis: {h['statement']}\n\nRows:\n{listing}"
                try:
                    result = llm.invoke([
                        SystemMessage(content=label_system),
                        HumanMessage(content=prompt),
                    ])
                    parsed = _json_or_empty(result.content) or []
                except Exception as exc:
                    _log.warning("[kenkyusha][proximity] LLM: %s", exc)
                    parsed = []
                if not isinstance(parsed, list):
                    continue
                supp = 0
                contra = 0
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    idx = int(item.get("row", -1))
                    if not 0 <= idx < len(rows):
                        continue
                    r = rows[idx]
                    etype = str(item.get("evidence_type", "neutral"))
                    if etype not in ("supports", "contradicts", "neutral"):
                        etype = "neutral"
                    rel = max(0, min(1000, int(item.get("relevance", 500))))
                    claim = str(item.get("claim", ""))[:480]
                    eid = _hash(h["id"] + r["source_did"] + etype)
                    evid_vid = f"at://{ACTOR_KENKYUSHA}/com.etzhayyim.apps.kenkyusha.evidence/{eid}"
                    await conn.execute(
                        """
                        INSERT INTO graphar.vertex_kenkyusha_evidence
                            (vertex_id, rkey, repo, evidence_id,
                             frontier_id, hypothesis_id,
                             source_type, source_did, source_uri,
                             source_title, source_year,
                             relevance_score, evidence_type, extracted_claim,
                             llm_model, actor_did, org_did,
                             created_at, sensitivity_ord)
                        SELECT $1,$2,$3,$4,
                               $5,$6,
                               $7,$8,'',
                               $9,$10,
                               $11,$12,$13,
                               $14,$15,$15,
                               $16,0
                        WHERE NOT EXISTS (
                            SELECT 1 FROM graphar.vertex_kenkyusha_evidence
                            WHERE evidence_id = $4
                        )
                        """,
                        evid_vid, eid, ACTOR_KENKYUSHA, eid,
                        state.get("frontier_id", ""), h["id"],
                        r["source_type"], r["source_did"],
                        r["source_title"][:240], r["source_year"],
                        rel, etype, claim,
                        _LLM_MODEL, ACTOR_KENKYUSHA, now,
                    )
                    if etype == "supports":
                        edge_vid = f"e-supports-{eid}"
                        await conn.execute(
                            """
                            INSERT INTO graphar.edge_kenkyusha_supports
                                (vertex_id, src, dst, weight, created_at, actor_did)
                            SELECT $1,$2,$3,$4,$5,$6
                            WHERE NOT EXISTS (
                                SELECT 1 FROM graphar.edge_kenkyusha_supports
                                WHERE src = $2 AND dst = $3
                            )
                            """,
                            edge_vid, eid, h["id"], rel, now, ACTOR_KENKYUSHA,
                        )
                        supp += 1
                    elif etype == "contradicts":
                        edge_vid = f"e-contradicts-{eid}"
                        await conn.execute(
                            """
                            INSERT INTO graphar.edge_kenkyusha_contradicts
                                (vertex_id, src, dst, weight, created_at, actor_did)
                            SELECT $1,$2,$3,$4,$5,$6
                            WHERE NOT EXISTS (
                                SELECT 1 FROM graphar.edge_kenkyusha_contradicts
                                WHERE src = $2 AND dst = $3
                            )
                            """,
                            edge_vid, eid, h["id"], rel, now, ACTOR_KENKYUSHA,
                        )
                        contra += 1
                    evidence_out.append({
                        "id": eid,
                        "hypothesis_id": h["id"],
                        "source_type":   r["source_type"],
                        "source_did":    r["source_did"],
                        "source_uri":    "",
                        "source_title":  r["source_title"],
                        "source_year":   r["source_year"],
                        "relevance":     rel,
                        "evidence_type": etype,
                        "extracted_claim": claim,
                    })
                if supp or contra:
                    await conn.execute(
                        """
                        UPDATE graphar.vertex_kenkyusha_hypothesis
                        SET supporting_evidence    = supporting_evidence + $2,
                            contradicting_evidence = contradicting_evidence + $3
                        WHERE hypothesis_id = $1
                        """,
                        h["id"], supp, contra,
                    )
                    h["supporting"]    = int(h.get("supporting", 0)) + supp
                    h["contradicting"] = int(h.get("contradicting", 0)) + contra
            await conn.execute("FLUSH")
        finally:
            await conn.close()
    except Exception as exc:
        _log.warning("[kenkyusha][proximity] persist: %s", exc)

    durations = dict(state.get("duration_ms_per_node") or {})
    durations["proximity"] = int((time.time() - t0) * 1000)
    return {
        "evidence": evidence_out,
        "hypotheses": hyps,
        "llm_calls": int(state.get("llm_calls", 0)) + len(top_hyps),
        "duration_ms_per_node": durations,
    }


async def _table_exists(conn: asyncpg.Connection, name: str) -> bool:
    """RisingWave-compatible table-exists probe (information_schema)."""
    try:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'graphar' AND table_name = $1
            """,
            name,
        )
        return row is not None
    except Exception:
        return False


# ── Phase 2C: disagreement_split helpers + node ──────────────────────────────


def _detect_disagreement_signals(
    critiques: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Classify each critique row by structural flaw markers + score variance.

    Returns one entry per detected disagreement with:
        hypothesis_id   — which hypothesis triggered the signal
        reason          — split_reason canonical name (matches Alembic schema)
        critique        — original critique text (truncated)
        score_delta     — original score_delta (for traceability)

    Pure: no LLM, no I/O. Triggered keywords are documented in
    _DISAGREEMENT_KEYWORDS. The variance heuristic fires once for the whole
    batch if max(score_delta) - min(score_delta) >= DISAGREEMENT_VARIANCE_THRESH;
    when it does it attaches to the lowest-confidence hypothesis (the
    weakest survivor is the most informative split anchor).
    """
    out: list[dict[str, Any]] = []
    if not critiques:
        return out

    # Keyword pass — per-row.
    for c in critiques:
        text = str(c.get("critique") or "").lower()
        if not text:
            continue
        for needles, reason in _DISAGREEMENT_KEYWORDS:
            if any(n in text for n in needles):
                out.append({
                    "hypothesis_id": str(c.get("hypothesis_id") or ""),
                    "reason":        reason,
                    "critique":      str(c.get("critique") or "")[:480],
                    "score_delta":   int(c.get("score_delta") or 0),
                })
                break   # one reason per critique row

    # Variance pass — single batch-level signal.
    deltas = [int(c.get("score_delta") or 0) for c in critiques]
    if deltas and (max(deltas) - min(deltas)) >= DISAGREEMENT_VARIANCE_THRESH:
        # Anchor to the row with the *smallest* score_delta — that's the
        # hypothesis the reviewer felt most strongly was weakened, hence
        # the most informative one to fork on.
        anchor = min(critiques, key=lambda c: int(c.get("score_delta") or 0))
        out.append({
            "hypothesis_id": str(anchor.get("hypothesis_id") or ""),
            "reason":        "score_variance",
            "critique":      str(anchor.get("critique") or "")[:480],
            "score_delta":   int(anchor.get("score_delta") or 0),
        })

    # Cap total splits per parent to bound LLM cost on the sub-title pass.
    return out[:DISAGREEMENT_MAX_SPLITS]


_SUB_TITLE_SYSTEM = """You are the Disagreement-as-Discovery role.
Given a parent research frontier and a list of detected disagreement signals
(circular reasoning, hidden assumption, evidence contradiction, score variance),
re-cast each signal as a *new, falsifiable sub-frontier* — a research question
whose resolution would dissolve the original disagreement.

Each sub-frontier MUST be:
  - Strictly narrower than the parent (a sub-claim, not a paraphrase)
  - Phrased as an investigable question or testable claim
  - Independent of the others (different mechanism / scope)

Output a JSON array, one object per input signal, in the same order, with:
  {"hypothesis_id":"<orig id>", "title":"<sub-frontier sentence>"}.
No markdown.
"""


def _coerce_sub_titles(
    parsed: Any,
    fallback_signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair LLM output with the original signal list. If the LLM returns
    something malformed we fall back to a deterministic title from the
    critique text so the disagreement is still captured."""
    by_hyp: dict[str, str] = {}
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            hid = str(item.get("hypothesis_id") or "").strip()
            t = str(item.get("title") or "").strip()
            if hid and t:
                by_hyp[hid] = t[:240]

    out: list[dict[str, Any]] = []
    for sig in fallback_signals:
        hid = sig.get("hypothesis_id", "")
        title = by_hyp.get(hid) or (
            f"[{sig.get('reason','disagreement')}] {sig.get('critique','')}"[:240]
        )
        out.append({**sig, "title": title})
    return out


async def disagreement_split(state: KenkyushaState) -> dict[str, Any]:
    """Detect disagreement → persist sub-frontiers (deferred-execution model).

    Phase 2C, scienceearth.org "disagreement-as-discovery":
      1. Scan critiques for structural-flaw keywords + score variance.
      2. If depth >= MAX_DISAGREEMENT_DEPTH, log and skip (recursion cap).
      3. For each detected disagreement, propose a falsifiable sub-frontier
         title via LLM, then INSERT a child vertex_kenkyusha_frontier row
         + edge_kenkyusha_spawned_from edge.
      4. The next cron tick (or any /runs invocation) will pick up these
         sub-frontiers via seed_frontier's pending-sub priority order.

    The current run continues to ranking / evolution / proximity / meta_review
    for the *parent* frontier — we do NOT block on sub-frontier completion.
    """
    t0 = time.time()
    durations = dict(state.get("duration_ms_per_node") or {})

    current_depth = int(state.get("depth") or 0)
    if current_depth >= MAX_DISAGREEMENT_DEPTH:
        durations["disagreement_split"] = int((time.time() - t0) * 1000)
        return {
            "disagreements": [],
            "sub_frontiers_spawned": [],
            "duration_ms_per_node": durations,
        }

    signals = _detect_disagreement_signals(state.get("critiques") or [])
    if not signals:
        durations["disagreement_split"] = int((time.time() - t0) * 1000)
        return {
            "disagreements": [],
            "sub_frontiers_spawned": [],
            "duration_ms_per_node": durations,
        }

    # LLM pass — re-cast signals as falsifiable sub-titles.
    sub_with_titles: list[dict[str, Any]] = []
    try:
        listing = "\n".join(
            f"{i}) reason={s['reason']} hypothesis_id={s['hypothesis_id']} "
            f"critique={s['critique']}"
            for i, s in enumerate(signals)
        )
        prompt = (
            f"Parent frontier: {state.get('frontierTitle','')}\n"
            f"Parent discipline: {state.get('primaryDiscipline','0613')}\n"
            f"Parent depth: {current_depth}\n\n"
            f"Signals:\n{listing}"
        )
        result = _llm(temperature=0.4, max_tokens=600).invoke([
            SystemMessage(content=_SUB_TITLE_SYSTEM),
            HumanMessage(content=prompt),
        ])
        parsed = _json_or_empty(result.content)
        sub_with_titles = _coerce_sub_titles(parsed, signals)
    except Exception as exc:
        _log.warning("[kenkyusha][disagreement_split] LLM: %s", exc)
        sub_with_titles = _coerce_sub_titles(None, signals)

    # Persist sub-frontier rows + lineage edges (idempotent).
    spawned: list[dict[str, Any]] = []
    parent_id   = state.get("frontier_id", "")
    parent_disc = state.get("primaryDiscipline", "0613")
    now         = _utc_now_str()
    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            for sub in sub_with_titles:
                title  = sub["title"]
                reason = sub["reason"]
                fid    = _hash(parent_id + title + reason)
                fdid   = f"{ACTOR_KENKYUSHA}:frontier:{fid}"
                vid    = f"at://{fdid}/com.etzhayyim.apps.kenkyusha.frontier/{fid}"
                child_depth = current_depth + 1

                await conn.execute(
                    """
                    INSERT INTO graphar.vertex_kenkyusha_frontier
                        (vertex_id, rkey, repo, frontier_id, did,
                         title, description, detection_method,
                         primary_discipline, secondary_disciplines,
                         urgency, evidence_level, consensus_level,
                         hypothesis_count, evidence_count, status,
                         source_did, detected_at, last_analyzed_at,
                         parent_frontier_id, split_reason, depth,
                         actor_did, org_did, created_at, sensitivity_ord)
                    SELECT $1,$2,$3,$4,$5,
                           $6,$7,$8,
                           $9,'',
                           'medium','none','none',
                           0,0,'detected',
                           '',$10,$10,
                           $11,$12,$13,
                           $14,$14,$10,0
                    WHERE NOT EXISTS (
                        SELECT 1 FROM graphar.vertex_kenkyusha_frontier
                        WHERE frontier_id = $4
                    )
                    """,
                    vid, fid, ACTOR_KENKYUSHA, fid, fdid,
                    title[:240], sub.get("critique", "")[:600], "disagreement_split",
                    parent_disc, now,
                    parent_id, reason, child_depth, ACTOR_KENKYUSHA,
                )
                # Lineage edge — parent (src) → child (dst).
                edge_vid = f"e-spawned-{fid}"
                await conn.execute(
                    """
                    INSERT INTO graphar.edge_kenkyusha_spawned_from
                        (vertex_id, src, dst, split_reason, depth, created_at, actor_did)
                    SELECT $1,$2,$3,$4,$5,$6,$7
                    WHERE NOT EXISTS (
                        SELECT 1 FROM graphar.edge_kenkyusha_spawned_from
                        WHERE src = $2 AND dst = $3
                    )
                    """,
                    edge_vid, parent_id, fid, reason, child_depth, now, ACTOR_KENKYUSHA,
                )
                spawned.append({
                    "frontier_id": fid,
                    "title":       title,
                    "reason":      reason,
                    "depth":       child_depth,
                    "hypothesis_id": sub.get("hypothesis_id", ""),
                })
            await conn.execute("FLUSH")
        finally:
            await conn.close()
    except Exception as exc:
        _log.warning("[kenkyusha][disagreement_split] persist: %s", exc)

    durations["disagreement_split"] = int((time.time() - t0) * 1000)
    return {
        "disagreements":         signals,
        "sub_frontiers_spawned": spawned,
        "llm_calls":             int(state.get("llm_calls", 0)) + (1 if signals else 0),
        "duration_ms_per_node":  durations,
    }


# ── Phase 2K: sub-frontier rollup helpers ────────────────────────────────────


def _rollup_weight(consensus: str) -> int:
    """Per-child weight when summing rollup totals at the parent. Strong
    children carry full weight; partial half (rounded down). Anything else
    is dropped (returns 0)."""
    if consensus == "strong":
        return 1000
    if consensus == "partial":
        return 500
    return 0


def _apply_rollup(
    parent_supports: int,
    parent_contradicts: int,
    children: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Pure rollup math: fold strong/partial child evidence into the parent
    totals. Returns ``(supports, contradicts, n_counted_children)``.

    Each child is ``{consensus_level, evidence_supports, evidence_contradicts}``.
    A child whose consensus is none/disputed/emerging contributes nothing —
    we only roll up children that have themselves crossed the same publish
    threshold the parent is about to evaluate.
    """
    rolled_supports    = int(parent_supports or 0)
    rolled_contradicts = int(parent_contradicts or 0)
    counted = 0
    for c in children:
        w = _rollup_weight(str(c.get("consensus_level") or ""))
        if w == 0:
            continue
        rolled_supports    += (int(c.get("evidence_supports")    or 0) * w) // 1000
        rolled_contradicts += (int(c.get("evidence_contradicts") or 0) * w) // 1000
        counted += 1
    return rolled_supports, rolled_contradicts, counted


# ── Node 7: meta_review — score the frontier, set next action ────────────────
def _consensus_from_counts(supports: int, contradicts: int) -> str:
    total = supports + contradicts
    if total == 0:
        return "none"
    ratio = supports / total
    if total < 3:
        return "disputed" if ratio < 0.6 else "emerging"
    if ratio >= 0.85:
        return "strong"
    if ratio >= 0.65:
        return "partial"
    if ratio >= 0.4:
        return "disputed"
    return "none"


async def meta_review(state: KenkyushaState) -> dict[str, Any]:
    """Aggregate the supports/contradicts counts of the top hypothesis and
    write back consensus_level, evidence_level, status. Decides next_action.

    Phase 2K — when this run is for a parent frontier (depth=0) and child
    sub-frontiers exist with their own settled consensus, fold their
    evidence counts into the parent's totals BEFORE computing the
    parent's consensus_level. Strong children contribute full weight;
    partial children contribute half. This closes the disagreement-as-
    discovery loop introduced in Phase 2C.
    """
    t0 = time.time()
    hyps = state.get("hypotheses") or []
    if not hyps:
        return {}
    top = max(hyps, key=lambda h: h.get("elo", 0))
    supports = int(top.get("supporting", 0))
    contradicts = int(top.get("contradicting", 0))

    # Sub-frontier rollup (parent-only; sub-frontiers don't recurse rollups).
    frontier_id  = state.get("frontier_id", "")
    current_depth = int(state.get("depth") or 0)
    rolled_children: list[dict[str, Any]] = []
    if current_depth == 0 and frontier_id:
        try:
            conn = await asyncpg.connect(_DB_URL)
            try:
                child_rows = await conn.fetch(
                    """
                    SELECT consensus_level,
                           COALESCE(rollup_supports_total, 0) AS rs,
                           COALESCE(rollup_contradicts_total, 0) AS rc,
                           hypothesis_count, evidence_count
                    FROM   graphar.vertex_kenkyusha_frontier
                    WHERE  parent_frontier_id = $1
                      AND  consensus_level IN ('strong', 'partial')
                    """,
                    frontier_id,
                )
            finally:
                await conn.close()
            for r in child_rows:
                # Child evidence count is conservative — use the sum of its
                # own evidence + any rollup it already absorbed. (Phase 2K
                # children themselves only run rollup when depth=0, which
                # by construction never holds for children — so rs/rc
                # default to 0 and we fall back to evidence_count.)
                rolled_children.append({
                    "consensus_level":      r["consensus_level"],
                    "evidence_supports":    int(r["rs"]) or int(r["evidence_count"] or 0),
                    "evidence_contradicts": int(r["rc"]) or 0,
                })
        except Exception as exc:
            _log.warning("[kenkyusha][meta_review] child rollup query: %s", exc)
            rolled_children = []
    supports, contradicts, counted_children = _apply_rollup(
        supports, contradicts, rolled_children,
    )
    consensus = _consensus_from_counts(supports, contradicts)

    if consensus in ("strong", "partial"):
        next_action = "publish"
        status = "supported"
    elif consensus == "emerging":
        next_action = "iterate"
        status = "investigating"
    elif consensus == "disputed":
        next_action = "iterate"
        status = "investigating"
    else:
        next_action = "abandon" if supports + contradicts == 0 else "iterate"
        status = "inconclusive"

    evidence_level = "experimental" if supports >= 5 else (
        "observational" if supports >= 2 else (
            "anecdotal" if supports >= 1 else "none"
        )
    )
    frontier_id = state.get("frontier_id", "")
    now = _utc_now_str()
    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            await conn.execute(
                """
                UPDATE graphar.vertex_kenkyusha_frontier
                SET consensus_level = $2,
                    evidence_level  = $3,
                    status          = CASE WHEN $4 = 'publish' THEN 'frontier_resolved'
                                           WHEN $4 = 'abandon' THEN 'frontier_dormant'
                                           ELSE 'frontier_active' END,
                    hypothesis_count = $5,
                    evidence_count   = $6,
                    last_analyzed_at = $7,
                    rollup_supports_total    = $8,
                    rollup_contradicts_total = $9,
                    rollup_strong_children   = $10,
                    rollup_last_at           = $7
                WHERE frontier_id = $1
                """,
                frontier_id, consensus, evidence_level, next_action,
                len(hyps), len(state.get("evidence") or []),
                now,
                int(supports), int(contradicts), int(counted_children),
            )
            await conn.execute(
                """
                UPDATE graphar.vertex_kenkyusha_hypothesis
                SET status = $2
                WHERE hypothesis_id = $1
                """,
                top["id"], status,
            )
            await conn.execute("FLUSH")
        finally:
            await conn.close()
    except Exception as exc:
        _log.warning("[kenkyusha][meta_review] update: %s", exc)

    durations = dict(state.get("duration_ms_per_node") or {})
    durations["meta_review"] = int((time.time() - t0) * 1000)
    return {
        "consensus_level":        consensus,
        "next_action":            next_action,
        "rollup_supports_total":  int(supports),
        "rollup_contradicts_total": int(contradicts),
        "rollup_strong_children": int(counted_children),
        "duration_ms_per_node":   durations,
    }


# ── Phase 2H: arxiv_submit (strong consensus → LaTeX manuscript) ────────────


def _arxiv_should_submit(state: KenkyushaState) -> bool:
    """Pure gating predicate. True iff:
        - global env-level enable flag is on
        - consensus_level == 'strong'
        - next_action     == 'publish'
        - depth           == 0           (sub-frontier results are partial)
        - at least one hypothesis present
    """
    if not ARXIV_SUBMIT_ENABLED:
        return False
    if int(state.get("depth") or 0) != 0:
        return False
    if state.get("consensus_level") != "strong":
        return False
    if state.get("next_action") != "publish":
        return False
    if not (state.get("hypotheses") or []):
        return False
    return True


def _latex_escape(s: str) -> str:
    """Bare-minimum LaTeX escape for body text. Enough for titles + claims;
    NOT a safe substitute for full TeX escaping. Newlines preserved as-is.

    Uses a NUL-byte sentinel for the backslash → \\textbackslash{} replacement
    so the subsequent ``{``/``}`` rules don't re-escape the braces inside
    that command.
    """
    if not s:
        return ""
    SENTINEL = "\x00BACKSLASH\x00"
    out = s.replace("\\", SENTINEL)
    for ch, repl in (
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
        ("<",  r"\textless{}"),
        (">",  r"\textgreater{}"),
    ):
        out = out.replace(ch, repl)
    out = out.replace(SENTINEL, r"\textbackslash{}")
    return out


def _build_arxiv_tex(state: KenkyushaState, winner: Hypothesis,
                     evidence: list[Evidence]) -> tuple[str, str]:
    """Compose ``main.tex`` content + plaintext abstract. Pure function.

    Layout:
      \\documentclass{article}
      \\title{<frontier title>}
      \\author{Kenkyusha AI Research Frontier Explorer}
      \\begin{document}
        \\maketitle
        \\begin{abstract} ... 1-paragraph synthesis ... \\end{abstract}
        \\section{Frontier}      ... description + discipline ...
        \\section{Hypothesis}    ... winner statement + rationale ...
        \\section{Supporting Evidence}
          \\begin{enumerate}
            \\item ... [source_type:source_year] title ...
          \\end{enumerate}
        \\section{Contradicting Evidence} (only if any)
        \\section{Methods}       ... 6-role Pregel loop description ...
      \\end{document}
    """
    title       = state.get("frontierTitle", "(untitled frontier)")
    discipline  = state.get("primaryDiscipline", "0613")
    detection   = state.get("detection_method", "citationGap")
    consensus   = state.get("consensus_level", "strong")

    supports    = [e for e in evidence if e.get("evidence_type") == "supports"]
    contradicts = [e for e in evidence if e.get("evidence_type") == "contradicts"]

    abstract_plain = (
        f"This manuscript reports the result of the Kenkyusha AI research-"
        f"frontier exploration loop on the question: \"{title}\". Operating in "
        f"ISCED-F field {discipline}, the system identified the frontier via "
        f"{detection}, generated and tournament-ranked competing hypotheses, "
        f"and retrieved supporting and contradicting evidence from multiple "
        f"knowledge sources. The strongest surviving hypothesis is: "
        f"\"{winner.get('statement','')}\". Evidence aggregation yields "
        f"consensus_level={consensus} with "
        f"{len(supports)} supporting and {len(contradicts)} contradicting items."
    )

    def _evidence_items(rows: list[Evidence]) -> str:
        if not rows:
            return "  \\item (none)\n"
        out_lines = []
        for r in rows:
            year = r.get("source_year") or 0
            year_str = f", {year}" if year else ""
            line = (
                f"  \\item \\textbf{{[{_latex_escape(r.get('source_type',''))}{_latex_escape(year_str)}]}} "
                f"{_latex_escape(r.get('source_title',''))}. "
                f"\\textit{{{_latex_escape(r.get('extracted_claim',''))}}} "
                f"(relevance permille: {int(r.get('relevance', 0))})"
            )
            out_lines.append(line)
        return "\n".join(out_lines) + "\n"

    body_parts = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{enumitem}",
        r"\usepackage{hyperref}",
        r"\title{" + _latex_escape(title) + r"}",
        r"\author{Kenkyusha — AI Research Frontier Explorer\\"
        r"\texttt{did:web:kenkyusha.etzhayyim.com}}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\begin{abstract}",
        _latex_escape(abstract_plain),
        r"\end{abstract}",
        r"\section{Frontier}",
        r"\textbf{Title:} " + _latex_escape(title) + r"\\",
        r"\textbf{Discipline (ISCED-F):} " + _latex_escape(discipline) + r"\\",
        r"\textbf{Detection method:} " + _latex_escape(detection) + r"\\",
        r"\textbf{Consensus level:} " + _latex_escape(consensus),
        r"\section{Hypothesis}",
        r"\textbf{Statement.} " + _latex_escape(str(winner.get("statement", ""))) + r"\\",
        r"\textbf{Rationale.} " + _latex_escape(str(winner.get("rationale", ""))) + r"\\",
        r"\textbf{Elo rating after tournament:} "
        + str(int(winner.get("elo", 0))) + r"\\",
        r"\textbf{Mutation kind:} "
        + _latex_escape(str(winner.get("mutation_kind", "seed"))),
        r"\section{Supporting Evidence}",
        r"\begin{enumerate}[leftmargin=*]",
        _evidence_items(supports).rstrip(),
        r"\end{enumerate}",
    ]
    if contradicts:
        body_parts.extend([
            r"\section{Contradicting Evidence}",
            r"\begin{enumerate}[leftmargin=*]",
            _evidence_items(contradicts).rstrip(),
            r"\end{enumerate}",
        ])
    body_parts.extend([
        r"\section{Methods}",
        r"This frontier was processed by the Kenkyusha 6-role co-scientist "
        r"Pregel loop (Generation, Reflection, Ranking, Evolution, Proximity, "
        r"Meta-review), inspired by Google's AI co-scientist and "
        r"\href{https://scienceearth.org/}{Science Earth}'s EACN3 lifecycle. "
        r"Evidence retrieval used vector search (multilingual-e5-small / 384-dim "
        r"cosine distance) against the RisingWave knowledge graph, with "
        r"graceful degradation to keyword matching when source embeddings "
        r"were unavailable.",
        r"\end{document}",
        "",
    ])
    return "\n".join(body_parts), abstract_plain


async def arxiv_submit(state: KenkyushaState) -> dict[str, Any]:
    """Phase 2H — persist a LaTeX manuscript when the frontier converged.

    Side-effects:
      INSERT vertex_kenkyusha_submission (idempotent by frontier_id)

    Returns nothing user-visible when gating predicate fails (zero-cost
    pass-through).
    """
    t0 = time.time()
    durations = dict(state.get("duration_ms_per_node") or {})

    if not _arxiv_should_submit(state):
        durations["arxiv_submit"] = int((time.time() - t0) * 1000)
        return {"duration_ms_per_node": durations}

    hyps = state.get("hypotheses") or []
    winner: Hypothesis = max(hyps, key=lambda h: int(h.get("elo", 0)))
    evidence: list[Evidence] = state.get("evidence") or []
    supports    = sum(1 for e in evidence if e.get("evidence_type") == "supports")
    contradicts = sum(1 for e in evidence if e.get("evidence_type") == "contradicts")

    tex, abstract = _build_arxiv_tex(state, winner, evidence)
    frontier_id   = state.get("frontier_id", "")
    submission_id = _hash(frontier_id + "submission" + winner.get("id", ""))
    vid = f"at://{ACTOR_KENKYUSHA}/com.etzhayyim.apps.kenkyusha.submission/{submission_id}"
    now = _utc_now_str()
    evidence_csv = ",".join(e.get("id", "") for e in evidence if e.get("id"))

    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO graphar.vertex_kenkyusha_submission
                    (vertex_id, rkey, repo, submission_id,
                     frontier_id, winner_hypothesis_id, evidence_ids,
                     arxiv_category, title, abstract,
                     manuscript_tex, manuscript_byte_size,
                     consensus_level, evidence_supports, evidence_contradicts,
                     llm_model, status,
                     actor_did, org_did, created_at, sensitivity_ord)
                SELECT $1,$2,$3,$4,
                       $5,$6,$7,
                       $8,$9,$10,
                       $11,$12,
                       $13,$14,$15,
                       $16,'manuscript_ready',
                       $17,$17,$18,0
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.vertex_kenkyusha_submission
                    WHERE frontier_id = $5
                )
                """,
                vid, submission_id, ACTOR_KENKYUSHA, submission_id,
                frontier_id, winner.get("id", ""), evidence_csv[:8000],
                ARXIV_DEFAULT_CATEGORY,
                str(state.get("frontierTitle", ""))[:240],
                abstract[:8000],
                tex, len(tex.encode("utf-8")),
                state.get("consensus_level", "strong"),
                supports, contradicts,
                _LLM_MODEL,
                ACTOR_KENKYUSHA, now,
            )
            await conn.execute("FLUSH")
        finally:
            await conn.close()
    except Exception as exc:
        _log.warning("[kenkyusha][arxiv_submit] persist: %s", exc)

    durations["arxiv_submit"] = int((time.time() - t0) * 1000)
    return {
        "arxiv_submission_id":    submission_id,
        "arxiv_manuscript_bytes": len(tex.encode("utf-8")),
        "duration_ms_per_node":   durations,
    }


# ── Routing ──────────────────────────────────────────────────────────────────


def _route_after_seed(state: KenkyushaState) -> str:
    return "generation" if state.get("frontier_status") == "detected" else END


# ── Build graph ──────────────────────────────────────────────────────────────


def _build() -> StateGraph:
    g = StateGraph(KenkyushaState)
    g.add_node("seed_frontier",      seed_frontier)
    g.add_node("generation",         generation)
    g.add_node("reflection",         reflection)
    g.add_node("disagreement_split", disagreement_split)
    g.add_node("ranking",            ranking)
    g.add_node("evolution",          evolution)
    g.add_node("proximity",          proximity)
    g.add_node("meta_review",        meta_review)
    g.add_node("arxiv_submit",       arxiv_submit)

    g.set_entry_point("seed_frontier")
    g.add_conditional_edges(
        "seed_frontier",
        _route_after_seed,
        {"generation": "generation", END: END},
    )
    g.add_edge("generation",         "reflection")
    g.add_edge("reflection",         "disagreement_split")
    g.add_edge("disagreement_split", "ranking")
    g.add_edge("ranking",            "evolution")
    g.add_edge("evolution",          "proximity")
    g.add_edge("proximity",          "meta_review")
    g.add_edge("meta_review",        "arxiv_submit")
    g.add_edge("arxiv_submit",       END)
    return g


app = _build().compile()


def build_graph():
    """Factory entry point for langgraph_loader (py_factory kind)."""
    return _build().compile()
