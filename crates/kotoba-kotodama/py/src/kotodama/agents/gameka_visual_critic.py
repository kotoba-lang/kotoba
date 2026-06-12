"""
com.etzhayyim.agent.gameka.visualCritic — LangGraph visual + perf scoring loop
for gameka playtests (ADR 2604250900 P4).

Closes the **inner QA loop**: takes 3 headless-WebGPU screenshots + page
metrics from the playwright actor, scores them against the spec, and
emits structured `issues[]` that feed `proposeGame` revise iterations.

Three-node StateGraph:

    analyze_render — Looks at low-level render signals (was the canvas
                     painted? are there console errors? was sceneLoad
                     within budget?). Pure-function, no LLM. Outputs
                     renderScore + renderIssues.
    analyze_match  — LLM scores how well the screenshots match the
                     spec.sceneJson description and the genre's expected
                     visual signature (e.g. platformer should show
                     ground+platforms+character). Multimodal-ready: when
                     vision lands at the LLM tier the same prompt gets
                     image attachments; until then degraded text-only
                     reasoning over the scene/genre signals.
    synthesize     — Combines render + match into visualScore + issues[].
                     Issues are structured so the proposeGame planner
                     consumes them as priorSpecs[*].issues in revise mode.

Input variables (Zeebe → state):
    specId          required
    artifactId      required
    iteration       int, 0 for first attempt
    sceneDescription text, from spec.scene_json
    genre           string
    title           string
    slug            string
    screenshotCids  list[str], B2 cids from playwright.screenshot
    screenshotUrls  list[str], B2 presigned URLs (vision-tier ready)
    consoleErrorCount int
    fpsP50, fpsP95   float, from in-page rAF probe
    sceneLoadMs     int, time from goto to first non-blank frame
    captureSucceeded bool
    threadId        BPMN process instance key

Output (state → Zeebe variables):
    visualScore     0.0-1.0
    perfScore       0.0-1.0
    combinedScore   0.7*visual + 0.3*perf
    publish         bool, combinedScore >= 0.7 AND no fatal issues
    outcome         "pass" | "revise" | "exhausted"
    issuesJson      JSON-serialised list[{category, severity, description}]
    criticModelId   LLM model id (or "degraded" when LLM unavailable)
    visualLatencyMs wall clock
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama import llm

log = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────────────────


PUBLISH_THRESHOLD = 0.7
VISUAL_WEIGHT = 0.7
PERF_WEIGHT = 0.3
MAX_ITERATION = 3   # >=3 stops the loop without revise

# Perf budgets (target: smooth on 2024 mid-range GPUs).
FPS_P50_TARGET = 55.0
FPS_P50_FLOOR = 25.0
SCENE_LOAD_BUDGET_MS = 4000


# ─── State ──────────────────────────────────────────────────────────────


class VisualState(TypedDict, total=False):
    # Input
    specId: str
    artifactId: str
    iteration: int
    sceneDescription: str
    genre: str
    title: str
    slug: str
    screenshotCids: list[str]
    screenshotUrls: list[str]
    consoleErrorCount: int
    fpsP50: float
    fpsP95: float
    sceneLoadMs: int
    captureSucceeded: bool
    threadId: str
    # Working
    renderScore: float
    renderIssues: list[dict[str, str]]
    matchScore: float
    matchIssues: list[dict[str, str]]
    # Output
    visualScore: float
    perfScore: float
    combinedScore: float
    publish: bool
    outcome: str
    issuesJson: str
    criticModelId: str
    visualLatencyMs: int


# ─── Prompt ─────────────────────────────────────────────────────────────


_MATCH_SYSTEM = """\
You are a senior game-art reviewer scoring a generated browser game
against its spec. The build runs on the kami-engine (wgpu / WebGPU,
Nintendo-style cream background #f0ead6, no Canvas2D).

Output ONE minified JSON object with this EXACT shape:
  {"matchScore": <float 0..1>,
   "issues": [{"category": "...", "severity": "...", "description": "..."}],
   "rationale": "<=200 chars"}

SCORING (0-1, weighted average → matchScore):
  scene_fidelity (0.40) — does the visual match the spec scene description?
  genre_signature (0.30) — does it look like the declared genre?
  craft_quality (0.20) — composition + readability + colour balance
  no_artifacts (0.10) — z-fight, clipping, missing textures, single-colour frame

ISSUE CATEGORIES (only emit when severity != "ok"):
  scene_mismatch | genre_mismatch | render_error | art_quality | ux_clarity

ISSUE SEVERITIES:
  blocker (publish=false), major (revise), minor (info-only)

HARD RULES:
  - matchScore is a NUMBER 0..1, never null, never NaN.
  - issues is an ARRAY (possibly empty). Each entry has all 3 keys.
  - description names a CONCRETE signal observable in the screenshots
    or the spec, <=160 chars.
  - Output ONLY the JSON. No preamble, no code fences.
"""


# ─── Helpers ────────────────────────────────────────────────────────────


def _safe_float(v: Any, default: float, lo: float, hi: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:
        return default
    return max(lo, min(f, hi))


def _safe_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _scale_perf(fps_p50: float, fps_p95: float, load_ms: int) -> float:
    """Linear scale fps_p50 against floor/target, penalise long sceneLoad."""
    # fps component
    fps_norm = (fps_p50 - FPS_P50_FLOOR) / max(FPS_P50_TARGET - FPS_P50_FLOOR, 1.0)
    fps_norm = max(0.0, min(fps_norm, 1.0))
    # load component
    load_norm = 1.0 - min(load_ms / SCENE_LOAD_BUDGET_MS, 1.0)
    load_norm = max(0.0, load_norm)
    # weighted
    return round(0.75 * fps_norm + 0.25 * load_norm, 3)


# ─── Nodes ──────────────────────────────────────────────────────────────


def _analyze_render(state: VisualState) -> VisualState:
    """Pure-function low-level render checks. No LLM."""
    issues: list[dict[str, str]] = []
    capture_ok = bool(state.get("captureSucceeded", False))
    cids = state.get("screenshotCids") or []
    err_count = _safe_int(state.get("consoleErrorCount"), 0)
    fps_p50 = _safe_float(state.get("fpsP50"), 0.0, 0.0, 240.0)
    load_ms = _safe_int(state.get("sceneLoadMs"), 0)

    score = 1.0
    if not capture_ok:
        issues.append({
            "category": "render_error",
            "severity": "blocker",
            "description": "headless playwright capture failed before any frame rendered",
        })
        score = 0.0
    if not cids:
        issues.append({
            "category": "render_error",
            "severity": "blocker",
            "description": "no screenshots captured (sessionOpen or goto failed)",
        })
        score = min(score, 0.0)
    elif len(cids) < 3:
        issues.append({
            "category": "render_error",
            "severity": "major",
            "description": f"expected 3 screenshots, captured {len(cids)} — likely a runtime panic",
        })
        score = min(score, 0.4)
    if err_count > 0:
        sev = "blocker" if err_count >= 5 else "major"
        issues.append({
            "category": "render_error",
            "severity": sev,
            "description": f"{err_count} console errors during runtime",
        })
        score = min(score, 0.6 if sev == "major" else 0.2)
    if fps_p50 > 0 and fps_p50 < FPS_P50_FLOOR:
        issues.append({
            "category": "render_error",
            "severity": "major",
            "description": f"fps_p50={fps_p50:.1f} below floor={FPS_P50_FLOOR}",
        })
        score = min(score, 0.5)
    if load_ms > SCENE_LOAD_BUDGET_MS:
        issues.append({
            "category": "render_error",
            "severity": "minor",
            "description": f"sceneLoad={load_ms}ms exceeds budget={SCENE_LOAD_BUDGET_MS}ms",
        })
        score = min(score, 0.85)

    return {**state, "renderScore": round(score, 3), "renderIssues": issues}


def _analyze_match(state: VisualState) -> VisualState:
    """LLM scores semantic fit. Multimodal-ready prompt — current text
    fallback embeds the screenshot URLs as references. When the LLM
    tier supports image input the same prompt receives attachments."""
    started = time.monotonic()

    # Skip the LLM entirely if render already shows the build is broken
    # — there's no point asking the model "is this a good game?" when
    # we know the canvas is empty.
    render_score = float(state.get("renderScore") or 0.0)
    if render_score < 0.2:
        return {
            **state,
            "matchScore": 0.0,
            "matchIssues": [],
            "criticModelId": "skipped-broken-render",
            "visualLatencyMs": 0,
        }

    urls = state.get("screenshotUrls") or []
    user = (
        f"Spec title: {state.get('title','')[:80]}\n"
        f"Genre: {state.get('genre','')[:24]}\n"
        f"Scene description: {state.get('sceneDescription','')[:300]}\n"
        f"Screenshots ({len(urls)} frames at t=1s, 3s, 5s):\n"
        f"{chr(10).join(urls[:3])}\n"
        f"console errors during run: {state.get('consoleErrorCount',0)}\n"
        f"fps_p50: {state.get('fpsP50',0):.1f}\n"
        "Score the visual fit and emit issues."
    )
    result = llm.call_tier_json(
        "vision",  # tier alias; falls back to default JSON tier when vision unbound
        system=_MATCH_SYSTEM,
        user=user,
        max_tokens=600,
        temperature=0.2,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    if not result.get("ok"):
        # Degraded mode — score conservatively as 0.5 so the build can
        # publish on render+perf alone if those are healthy. The
        # outcome rationale flags this so reviewers know.
        return {
            **state,
            "matchScore": 0.5,
            "matchIssues": [{
                "category": "art_quality",
                "severity": "minor",
                "description": f"visual critic LLM unavailable: {str(result.get('error') or '')[:80]} — degraded score",
            }],
            "criticModelId": "degraded-no-vision",
            "visualLatencyMs": latency_ms,
        }

    data = result.get("data") or {}
    return {
        **state,
        "matchScore": _safe_float(data.get("matchScore"), 0.5, 0.0, 1.0),
        "matchIssues": list(data.get("issues") or [])[:8],
        "criticModelId": str(result.get("model") or ""),
        "visualLatencyMs": latency_ms,
    }


def _synthesize(state: VisualState) -> VisualState:
    """Combine render + match → visualScore + perfScore + combinedScore +
    outcome. The outcome closes the loop:

      pass      — publish=true, derive publishGame
      revise    — publish=false, iteration<MAX, derive proposeGame
      exhausted — publish=false, iteration>=MAX, do not derive
    """
    render_score = float(state.get("renderScore") or 0.0)
    match_score = float(state.get("matchScore") or 0.0)
    visual_score = round(0.5 * render_score + 0.5 * match_score, 3)

    fps_p50 = _safe_float(state.get("fpsP50"), 0.0, 0.0, 240.0)
    fps_p95 = _safe_float(state.get("fpsP95"), 0.0, 0.0, 240.0)
    load_ms = _safe_int(state.get("sceneLoadMs"), 0)
    perf_score = _scale_perf(fps_p50, fps_p95, load_ms)

    combined = round(VISUAL_WEIGHT * visual_score + PERF_WEIGHT * perf_score, 3)

    issues = list(state.get("renderIssues") or []) + list(state.get("matchIssues") or [])
    # severity ladder per the critic prompt:
    #   blocker → publish=false (always)
    #   major   → publish=false (revise)
    #   minor   → info only, doesn't gate publish
    has_blocker = any(i.get("severity") == "blocker" for i in issues)
    has_major = any(i.get("severity") == "major" for i in issues)
    publish = (combined >= PUBLISH_THRESHOLD) and not has_blocker and not has_major

    iteration = int(state.get("iteration") or 0)
    if publish:
        outcome = "pass"
    elif iteration + 1 >= MAX_ITERATION:
        outcome = "exhausted"
    else:
        outcome = "revise"

    return {
        **state,
        "visualScore": visual_score,
        "perfScore": perf_score,
        "combinedScore": combined,
        "publish": publish,
        "outcome": outcome,
        "issuesJson": json.dumps(issues, ensure_ascii=False),
    }


# ─── Graph ──────────────────────────────────────────────────────────────


def _build_graph() -> Any:
    g = StateGraph(VisualState)
    g.add_node("analyze_render", _analyze_render)
    g.add_node("analyze_match", _analyze_match)
    g.add_node("synthesize", _synthesize)
    g.add_edge(START, "analyze_render")
    g.add_edge("analyze_render", "analyze_match")
    g.add_edge("analyze_match", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


visual_critic_graph = _build_graph()


# ─── LangServer task wrapper ───────────────────────────────────────────────


async def task_agent_gameka_visual_critic(
    specId: str = "",
    artifactId: str = "",
    iteration: int = 0,
    sceneDescription: str = "",
    genre: str = "",
    title: str = "",
    slug: str = "",
    screenshotCids: list[str] | None = None,
    screenshotUrls: list[str] | None = None,
    consoleErrorCount: int = 0,
    fpsP50: float = 0.0,
    fpsP95: float = 0.0,
    sceneLoadMs: int = 0,
    captureSucceeded: bool = True,
    threadId: str = "",
) -> dict:
    """Entry point registered as `com.etzhayyim.agent.gameka.visualCritic` in
    kotodama.zeebe_worker_main."""
    initial: VisualState = {
        "specId": specId,
        "artifactId": artifactId,
        "iteration": int(iteration or 0),
        "sceneDescription": sceneDescription or "",
        "genre": genre or "",
        "title": title or "",
        "slug": slug or "",
        "screenshotCids": screenshotCids or [],
        "screenshotUrls": screenshotUrls or [],
        "consoleErrorCount": int(consoleErrorCount or 0),
        "fpsP50": float(fpsP50 or 0.0),
        "fpsP95": float(fpsP95 or 0.0),
        "sceneLoadMs": int(sceneLoadMs or 0),
        "captureSucceeded": bool(captureSucceeded),
        "threadId": threadId or "",
    }
    try:
        final = await visual_critic_graph.ainvoke(initial)
    except Exception as e:  # noqa: BLE001
        log.warning("gameka.visualCritic graph error: %s", e)
        return {
            "visualScore": 0.0,
            "perfScore": 0.0,
            "combinedScore": 0.0,
            "publish": False,
            "outcome": "exhausted",
            "issuesJson": json.dumps([{
                "category": "render_error",
                "severity": "blocker",
                "description": f"critic-graph-error:{type(e).__name__}:{str(e)[:80]}",
            }]),
            "criticModelId": "",
            "visualLatencyMs": 0,
        }
    return {
        "visualScore": float(final.get("visualScore") or 0.0),
        "perfScore": float(final.get("perfScore") or 0.0),
        "combinedScore": float(final.get("combinedScore") or 0.0),
        "publish": bool(final.get("publish")),
        "outcome": final.get("outcome") or "exhausted",
        "issuesJson": final.get("issuesJson") or "[]",
        "criticModelId": final.get("criticModelId") or "",
        "visualLatencyMs": int(final.get("visualLatencyMs") or 0),
    }
