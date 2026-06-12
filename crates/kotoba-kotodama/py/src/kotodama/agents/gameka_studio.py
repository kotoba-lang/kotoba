"""
com.etzhayyim.agent.gameka.studio — LangGraph game-spec deliberation agent
(ADR 2604250900, P1 transitional task type).

5-node StateGraph:

    planner    — LLM proposes 3 candidate game specs given a brief +
                 prior_specs (Path F memory, supplied by BPMN caller).
                 Output: candidates[]
    researcher — Cheap signal pass: dedupe candidates against prior_specs
                 by slug + title (no external XRPC call in P1; will add
                 media_gamers.searchGames + kami.listSceneTemplates in P2).
    critic     — LLM scores each candidate on (fun, feasibility,
                 kami-coverage, novelty) → picks best, writes critique.
    loop_or_finalize — conditional edge:
                 iteration < max AND best_score < threshold → planner (revise)
                 otherwise → finalizer
    finalizer  — Emits a flat dict shaped like a vertex_gameka_spec row.
                 BPMN INSERTs it via generic.db.insert.

Why a dedicated task type and not generic.langgraph.run:
  ADR 2604250836 proposes generic.langgraph.run as the 8th primitive but
  is still status: proposed. Until that primitive lands (Migration Step 2),
  com.etzhayyim.agent.gameka.studio mirrors com.etzhayyim.agent.plan's shape so we can
  exercise the BPMN end-to-end on the existing zeebe-worker. Switching
  to generic.langgraph.run is a one-line BPMN change (taskDefinition
  type + state.graph_id="gameka.studio.v1") plus dropping this wrapper.

Input variables (Zeebe → state):
    brief         — required, the game brief (free text)
    priorSpecs    — list of {slug,title,score} from prior runs (Path F memory)
    iteration     — int, 0 for first call, BPMN increments on revise
    maxIterations — int, default 3
    scoreThreshold — float, default 0.8 (gates loop)
    threadId      — BPMN process instance key

Output (state → Zeebe variables):
    specId        — ULID-shape rkey
    title         — selected spec title
    slug          — kebab-case slug derived from title
    genre         — selected spec genre
    mechanicJson  — JSON string (game mechanic descriptor)
    sceneJson     — JSON string (scene + biome + camera config)
    budgetUsd     — float
    score         — critic score 0-1
    rationale     — <=200 char human rationale
    iterations    — total LangGraph iterations actually executed
    modelId       — LLM model id used for the deciding call
    deliberateLatencyMs — wall clock
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama import llm

log = logging.getLogger(__name__)

# ─── State ──────────────────────────────────────────────────────────────


class GamekaState(TypedDict, total=False):
    # Input
    brief: str
    priorSpecs: list[dict[str, Any]]
    iteration: int
    maxIterations: int
    scoreThreshold: float
    threadId: str
    # Working
    candidates: list[dict[str, Any]]
    critique: list[dict[str, Any]]
    # Output
    specId: str
    title: str
    slug: str
    genre: str
    mechanicJson: str
    sceneJson: str
    budgetUsd: float
    score: float
    rationale: str
    iterations: int
    modelId: str
    deliberateLatencyMs: int


# ─── Prompts ────────────────────────────────────────────────────────────


_PLANNER_SYSTEM = """\
You design original 2D / low-poly 3D browser games that target the kami-engine
(wgpu / WebGPU + WebGL2 fallback, Nintendo-style UI, Web Audio synthesis only).

Output ONE minified JSON object with this EXACT shape:
  {"candidates":[{<spec>}, {<spec>}, {<spec>}]}

Each <spec> has these EXACT keys (omit none):
  title       — short English title, <=40 chars
  slug        — lowercase kebab-case, <=24 chars, [a-z0-9-]+
  genre       — one of "platformer" | "puzzle" | "shmup" | "runner" |
                "sandbox" | "rhythm" | "rogue-lite" | "tower-defense"
  mechanic    — short English description of the core verb loop (<=200 chars)
  scene       — short English description of the scene / biome / camera
                (<=200 chars; pick from kami biome presets when possible:
                 plains / quarry / desert / tundra / voxel-sandbox)
  budgetUsd   — integer, total compute + asset budget in USD (50..500)

HARD RULES:
  - 3 candidates, distinct mechanic and scene per candidate.
  - Avoid mechanics overlapping any of the prior specs given.
  - No copyrighted IP, no real-person likeness, no R-rated content.
  - Output ONLY the JSON object. No preamble, no code fences.
"""

_CRITIC_SYSTEM = """\
You score game specs on a kami-engine-targeting browser studio's behalf.

Input: a brief, prior_specs (avoid-list), and N candidates.
Output ONE minified JSON object with this EXACT shape:
  {"selected": <int>, "score": <float>, "rationale": "<=200 chars",
   "perCandidate":[{"score":<float>,"reason":"..."}, ...]}

Scoring (0-1 each, weighted average → score):
  fun          (0.30) — hook strength + replayability
  feasibility  (0.30) — implementable in kami-app-{slug} crate within budget
  coverage     (0.20) — leverages existing kami-pipelines adapters (Sky /
                        Terrain / Water / VoxelChunk / Particle / Atlas)
  novelty      (0.20) — distinct from prior_specs

HARD RULES:
  - selected is the index (0-based) of the best candidate.
  - score, perCandidate[*].score in 0.0..1.0 (never null, never NaN).
  - Output ONLY the JSON object. No preamble.
"""


# ─── Helpers ────────────────────────────────────────────────────────────


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(s: str) -> str:
    base = re.sub(r"\s+", "-", (s or "").strip().lower())
    base = _SLUG_RE.sub("", base)
    return (base[:24] or "game").strip("-") or "game"


def _ulid_like(prefix: str) -> str:
    """Cheap ULID-shape: prefix + monotonic ms + 6 hex chars from time."""
    ms = int(time.time() * 1000)
    suffix = f"{ms & 0xFFFFFF:06x}"
    return f"{prefix}{ms}{suffix}"


# ─── Nodes ──────────────────────────────────────────────────────────────


def _planner(state: GamekaState) -> GamekaState:
    """LLM call 1: generate 3 candidate specs."""
    started = time.monotonic()
    prior = state.get("priorSpecs") or []
    user = (
        f"Brief: {state.get('brief','')[:1500]}\n"
        f"Prior specs (avoid duplicates):\n"
        f"{json.dumps(prior[:10], ensure_ascii=False)[:1500]}\n"
        "Propose 3 candidates."
    )
    result = llm.call_tier_json(
        "classifier",
        system=_PLANNER_SYSTEM,
        user=user,
        max_tokens=900,
        temperature=0.6,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    if not result.get("ok"):
        return {
            **state,
            "candidates": [],
            "modelId": str(result.get("model") or ""),
            "deliberateLatencyMs": int(state.get("deliberateLatencyMs", 0)) + latency_ms,
        }
    data = result.get("data") or {}
    raw = data.get("candidates") or []
    candidates: list[dict[str, Any]] = []
    for c in raw[:3]:
        if not isinstance(c, dict):
            continue
        title = str(c.get("title") or "Untitled")[:40]
        candidates.append({
            "title": title,
            "slug": _slugify(str(c.get("slug") or title)),
            "genre": str(c.get("genre") or "puzzle")[:24],
            "mechanic": str(c.get("mechanic") or "")[:200],
            "scene": str(c.get("scene") or "")[:200],
            "budgetUsd": _safe_float(c.get("budgetUsd"), 100.0, 50.0, 500.0),
        })
    return {
        **state,
        "candidates": candidates,
        "modelId": str(result.get("model") or ""),
        "deliberateLatencyMs": int(state.get("deliberateLatencyMs", 0)) + latency_ms,
    }


def _researcher(state: GamekaState) -> GamekaState:
    """Dedupe by slug+title against priorSpecs. P2 will add XRPC search."""
    prior = state.get("priorSpecs") or []
    seen_slugs = {str(p.get("slug") or "").lower() for p in prior}
    seen_titles = {str(p.get("title") or "").lower() for p in prior}
    deduped = [
        c for c in (state.get("candidates") or [])
        if c["slug"].lower() not in seen_slugs
        and c["title"].lower() not in seen_titles
    ]
    return {**state, "candidates": deduped}


def _critic(state: GamekaState) -> GamekaState:
    """LLM call 2: score candidates, pick best."""
    candidates = state.get("candidates") or []
    if not candidates:
        return {
            **state,
            "score": 0.0,
            "rationale": "no candidates after research dedupe",
            "critique": [],
        }
    started = time.monotonic()
    user = (
        f"Brief: {state.get('brief','')[:1500]}\n"
        f"Prior specs (avoid-list):\n"
        f"{json.dumps((state.get('priorSpecs') or [])[:10], ensure_ascii=False)[:1500]}\n"
        f"Candidates:\n"
        f"{json.dumps(candidates, ensure_ascii=False)[:2000]}\n"
        "Score them."
    )
    result = llm.call_tier_json(
        "classifier",
        system=_CRITIC_SYSTEM,
        user=user,
        max_tokens=600,
        temperature=0.2,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    if not result.get("ok"):
        # safety fallback — pick first candidate, low confidence
        chosen = candidates[0]
        return {
            **state,
            "score": 0.3,
            "rationale": f"critic-error:{str(result.get('error') or '')[:80]}",
            "modelId": str(result.get("model") or ""),
            "candidates": [chosen],
            "critique": [{"score": 0.3, "reason": "critic LLM failed"}],
            "deliberateLatencyMs": int(state.get("deliberateLatencyMs", 0)) + latency_ms,
        }
    data = result.get("data") or {}
    idx = _safe_int(data.get("selected"), 0, 0, max(0, len(candidates) - 1))
    chosen = candidates[idx]
    return {
        **state,
        "candidates": [chosen],
        "score": _safe_float(data.get("score"), 0.0, 0.0, 1.0),
        "rationale": str(data.get("rationale") or "")[:200],
        "critique": list(data.get("perCandidate") or [])[:3],
        "modelId": str(result.get("model") or ""),
        "deliberateLatencyMs": int(state.get("deliberateLatencyMs", 0)) + latency_ms,
    }


def _should_loop(state: GamekaState) -> str:
    iteration = int(state.get("iteration") or 0)
    max_iter = int(state.get("maxIterations") or 3)
    threshold = float(state.get("scoreThreshold") or 0.8)
    score = float(state.get("score") or 0.0)
    if iteration + 1 < max_iter and score < threshold and (state.get("candidates") or []):
        return "planner"
    return "finalizer"


def _planner_revise(state: GamekaState) -> GamekaState:
    """Same as _planner but increments iteration; back-edge target."""
    out = _planner(state)
    return {**out, "iteration": int(state.get("iteration") or 0) + 1}


def _finalizer(state: GamekaState) -> GamekaState:
    """Flatten to vertex_gameka_spec row shape."""
    chosen = (state.get("candidates") or [{}])[0]
    spec_id = _ulid_like("spec")
    iteration = int(state.get("iteration") or 0)
    title = chosen.get("title") or "Untitled"
    slug = chosen.get("slug") or _slugify(title)
    return {
        **state,
        "specId": spec_id,
        "title": title,
        "slug": slug,
        "genre": chosen.get("genre") or "",
        "mechanicJson": json.dumps({"description": chosen.get("mechanic") or ""}, ensure_ascii=False),
        "sceneJson": json.dumps({"description": chosen.get("scene") or ""}, ensure_ascii=False),
        "budgetUsd": float(chosen.get("budgetUsd") or 100.0),
        "iterations": iteration + 1,
    }


# ─── Safe coerce ────────────────────────────────────────────────────────


def _safe_float(v: Any, default: float, lo: float, hi: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return max(lo, min(f, hi))


def _safe_int(v: Any, default: int, lo: int, hi: int) -> int:
    try:
        i = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(i, hi))


# ─── Graph ──────────────────────────────────────────────────────────────


def _build_graph() -> Any:
    g = StateGraph(GamekaState)
    g.add_node("planner", _planner)
    g.add_node("researcher", _researcher)
    g.add_node("critic", _critic)
    g.add_node("planner_revise", _planner_revise)
    g.add_node("finalizer", _finalizer)
    g.add_edge(START, "planner")
    g.add_edge("planner", "researcher")
    g.add_edge("researcher", "critic")
    g.add_conditional_edges(
        "critic",
        _should_loop,
        {"planner": "planner_revise", "finalizer": "finalizer"},
    )
    g.add_edge("planner_revise", "researcher")
    g.add_edge("finalizer", END)
    return g.compile()


studio_graph = _build_graph()

# Register in the generic.langgraph.run registry (ADR-2604250836 step 2).
from kotodama.primitives import langgraph_registry as _lr  # noqa: E402
_lr.register("gameka.studio.v1", studio_graph)


# ─── LangServer task wrapper ───────────────────────────────────────────────


async def task_agent_gameka_studio(
    brief: str = "",
    priorSpecs: list[dict[str, Any]] | None = None,
    iteration: int = 0,
    maxIterations: int = 3,
    scoreThreshold: float = 0.8,
    threadId: str = "",
) -> dict:
    """Entry point registered as `com.etzhayyim.agent.gameka.studio` in
    kotodama.zeebe_worker_main. Returns a flat dict consumable by
    Zeebe FEEL ioMapping."""
    if not brief:
        return {
            "specId": "",
            "title": "",
            "slug": "",
            "score": 0.0,
            "rationale": "missing brief",
            "iterations": 0,
        }
    initial: GamekaState = {
        "brief": brief,
        "priorSpecs": priorSpecs or [],
        "iteration": int(iteration or 0),
        "maxIterations": int(maxIterations or 3),
        "scoreThreshold": float(scoreThreshold or 0.8),
        "threadId": threadId or "",
    }
    try:
        final = await studio_graph.ainvoke(initial)
    except Exception as e:  # noqa: BLE001
        log.warning("gameka.studio graph error: %s", e)
        return {
            "specId": "",
            "title": "",
            "slug": "",
            "genre": "",
            "mechanicJson": "{}",
            "sceneJson": "{}",
            "budgetUsd": 0.0,
            "score": 0.0,
            "rationale": f"graph-error:{type(e).__name__}:{str(e)[:80]}",
            "iterations": 0,
            "modelId": "",
            "deliberateLatencyMs": 0,
        }
    return {
        "specId": final.get("specId") or "",
        "title": final.get("title") or "",
        "slug": final.get("slug") or "",
        "genre": final.get("genre") or "",
        "mechanicJson": final.get("mechanicJson") or "{}",
        "sceneJson": final.get("sceneJson") or "{}",
        "budgetUsd": float(final.get("budgetUsd") or 0.0),
        "score": float(final.get("score") or 0.0),
        "rationale": final.get("rationale") or "",
        "iterations": int(final.get("iterations") or 0),
        "modelId": final.get("modelId") or "",
        "deliberateLatencyMs": int(final.get("deliberateLatencyMs") or 0),
    }
