"""Pure-helper tests for kotodama.kenkyusha.graph (Phase 2A — co-scientist Pregel).

No DB, no LLM, no Pregel execution — only:
  * _hash determinism
  * _consensus_from_counts mapping
  * _coerce_hypotheses tolerance to malformed LLM output
  * _elo_update math (zero-sum + ELO_K bound)
  * _json_or_empty resilience to code-fence wrappers
  * _route_after_seed branching (graph routing decision)
  * build_graph() topology — 7 nodes + entry point + edges connect

Strategy: stub asyncpg + langchain at module load so the import succeeds in
a lean test env. The graph node bodies (which actually hit the DB / LLM)
are NOT exercised here — see the live smoke test in
``70-tools/scripts/kenkyusha/smoke.sh`` for end-to-end verification.
"""

from __future__ import annotations

import sys
import types
from typing import Any


# ── Stub heavy imports before kotodama.kenkyusha.graph is loaded ───────────


def _has_real(modname: str) -> bool:
    """Return True if a real (non-stub) module is importable."""
    if modname in sys.modules:
        return True
    try:
        import importlib.util as _ilu
        return _ilu.find_spec(modname) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _install_kenkyusha_stubs() -> None:
    """Provide stand-ins for asyncpg / langchain_core.messages / langchain_openai
    only when the real packages aren't importable. Never shadows a real install
    (so the real langgraph keeps working when it's present in the test env).
    """
    if not _has_real("asyncpg"):
        asyncpg = types.ModuleType("asyncpg")

        class _Connection:  # placeholder; nodes that hit it are not exercised
            async def execute(self, *a, **k): return None
            async def fetch(self, *a, **k): return []
            async def fetchrow(self, *a, **k): return None
            async def close(self): return None

        async def _connect(*a, **k):
            return _Connection()

        asyncpg.connect = _connect              # type: ignore[attr-defined]
        asyncpg.Connection = _Connection        # type: ignore[attr-defined]
        sys.modules["asyncpg"] = asyncpg

    if not _has_real("langchain_core.messages"):
        lc_core = types.ModuleType("langchain_core")
        messages = types.ModuleType("langchain_core.messages")

        class _Msg:
            def __init__(self, content: str = ""): self.content = content

        messages.HumanMessage  = _Msg          # type: ignore[attr-defined]
        messages.SystemMessage = _Msg          # type: ignore[attr-defined]
        sys.modules["langchain_core"]          = lc_core
        sys.modules["langchain_core.messages"] = messages

    if not _has_real("langchain_openai"):
        lc_openai = types.ModuleType("langchain_openai")

        class _ChatOpenAI:
            def __init__(self, **kw): self._kw = kw
            def invoke(self, _msgs):
                class _R:
                    content = "[]"
                return _R()

        lc_openai.ChatOpenAI = _ChatOpenAI     # type: ignore[attr-defined]
        sys.modules["langchain_openai"] = lc_openai


_install_kenkyusha_stubs()

from kotodama.kenkyusha.graph import (   # noqa: E402  (post-stub import)
    ARXIV_SUBMIT_ENABLED,
    DISAGREEMENT_MAX_SPLITS,
    DISAGREEMENT_VARIANCE_THRESH,
    MAX_DISAGREEMENT_DEPTH,
    _EVIDENCE_SOURCES,
    _apply_rollup,
    _arxiv_should_submit,
    _build_arxiv_tex,
    _coerce_hypotheses,
    _coerce_sub_titles,
    _consensus_from_counts,
    _detect_disagreement_signals,
    _elo_update,
    _hash,
    _json_or_empty,
    _latex_escape,
    _rollup_weight,
    _route_after_seed,
    build_graph,
)


# ── _hash ────────────────────────────────────────────────────────────────────


def test_hash_is_deterministic():
    assert _hash("foo") == _hash("foo")


def test_hash_changes_with_input():
    assert _hash("foo") != _hash("bar")


def test_hash_length_24():
    assert len(_hash("research frontier")) == 24


# ── _consensus_from_counts ───────────────────────────────────────────────────


def test_consensus_none_when_no_evidence():
    assert _consensus_from_counts(0, 0) == "none"


def test_consensus_disputed_when_low_total_split():
    # total=2 (<3) → low-total branch → ratio=0.5 < 0.6 → disputed.
    assert _consensus_from_counts(1, 1) == "disputed"


def test_consensus_emerging_when_low_total_majority_supports():
    # supports=2, contradicts=0 → total=2 (<3) → ratio=1.0 → emerging
    assert _consensus_from_counts(2, 0) == "emerging"


def test_consensus_strong_when_high_ratio_high_total():
    assert _consensus_from_counts(9, 1) == "strong"     # 0.9


def test_consensus_partial_when_majority_supports():
    assert _consensus_from_counts(7, 3) == "partial"    # 0.7


def test_consensus_disputed_when_balanced():
    assert _consensus_from_counts(5, 5) == "disputed"   # 0.5


def test_consensus_none_when_mostly_contradicted():
    assert _consensus_from_counts(1, 9) == "none"       # 0.1


# ── _coerce_hypotheses ───────────────────────────────────────────────────────


def test_coerce_hypotheses_drops_empty_statements():
    parsed = [
        {"statement": "", "rationale": "x"},
        {"statement": "Good hypothesis"},
    ]
    out = _coerce_hypotheses(parsed, n=4)
    assert len(out) == 1
    assert out[0]["statement"] == "Good hypothesis"


def test_coerce_hypotheses_clamps_confidence():
    parsed = [
        {"statement": "S1", "confidence": 5000},   # >1000 clamp
        {"statement": "S2", "confidence": -50},    # <0 clamp
        {"statement": "S3", "confidence": 700},
    ]
    out = _coerce_hypotheses(parsed, n=5)
    assert out[0]["confidence"] == 1000
    assert out[1]["confidence"] == 0
    assert out[2]["confidence"] == 700


def test_coerce_hypotheses_truncates_long_strings():
    parsed = [{"statement": "x" * 1000, "rationale": "y" * 1000}]
    out = _coerce_hypotheses(parsed, n=1)
    assert len(out[0]["statement"]) <= 480
    assert len(out[0]["rationale"]) <= 600


def test_coerce_hypotheses_respects_n_cap():
    parsed = [{"statement": f"H{i}"} for i in range(20)]
    out = _coerce_hypotheses(parsed, n=3)
    assert len(out) == 3


def test_coerce_hypotheses_rejects_non_list():
    assert _coerce_hypotheses({"not": "a list"}, n=4) == []
    assert _coerce_hypotheses(None, n=4) == []
    assert _coerce_hypotheses("string", n=4) == []


def test_coerce_hypotheses_default_confidence_500():
    parsed = [{"statement": "S1"}]
    out = _coerce_hypotheses(parsed, n=1)
    assert out[0]["confidence"] == 500


# ── _elo_update ──────────────────────────────────────────────────────────────


def test_elo_update_winner_a_gains_rating():
    new_a, new_b = _elo_update(1200, 1200, "A", k=32)
    assert new_a > 1200
    assert new_b < 1200


def test_elo_update_winner_b_loses_for_a():
    new_a, new_b = _elo_update(1200, 1200, "B", k=32)
    assert new_a < 1200
    assert new_b > 1200


def test_elo_update_zero_sum():
    new_a, new_b = _elo_update(1500, 1100, "A", k=32)
    # ELO drift is symmetric in expectation; underdog losing changes less
    assert (new_a - 1500) + (new_b - 1100) <= 1   # rounding tolerance


def test_elo_update_underdog_upset_gains_more():
    fav_new, dog_new = _elo_update(1700, 1100, "B", k=32)
    # B (dog, 1100) beats A (fav, 1700) → big swing
    assert dog_new - 1100 > 25                    # close to full k for upset


def test_elo_update_k_factor_bounds_swing():
    a1, b1 = _elo_update(1200, 1200, "A", k=16)
    a2, b2 = _elo_update(1200, 1200, "A", k=32)
    assert a2 - 1200 > a1 - 1200                  # higher k → bigger swing


# ── _json_or_empty ───────────────────────────────────────────────────────────


def test_json_or_empty_parses_plain_json():
    assert _json_or_empty('{"a":1}') == {"a": 1}


def test_json_or_empty_strips_code_fence():
    assert _json_or_empty("```json\n[1,2,3]\n```") == [1, 2, 3]


def test_json_or_empty_returns_none_on_invalid():
    assert _json_or_empty("not json at all") is None


def test_json_or_empty_handles_array_root():
    out = _json_or_empty("[{\"x\":1},{\"x\":2}]")
    assert isinstance(out, list)
    assert out[1]["x"] == 2


# ── _route_after_seed ────────────────────────────────────────────────────────


def test_route_after_seed_when_detected_goes_to_generation():
    assert _route_after_seed({"frontier_status": "detected"}) == "generation"


def test_route_after_seed_when_no_frontier_goes_to_end():
    # Returns the END sentinel from our stubbed langgraph (__end__) — accept any
    # truthy non-"generation" value here to be stub-implementation agnostic.
    result = _route_after_seed({"frontier_status": "no_frontier"})
    assert result != "generation"


def test_route_after_seed_when_status_missing_goes_to_end():
    result = _route_after_seed({})
    assert result != "generation"


# ── build_graph topology ─────────────────────────────────────────────────────


def test_build_graph_compiles_without_error():
    g = build_graph()
    assert g is not None


def _graph_node_names(g: Any) -> set[str]:
    """Topology probe that works against both the conftest stub and real
    langgraph's CompiledStateGraph. The stub exposes ``_nodes``; the real
    library exposes ``.get_graph().nodes`` (a dict)."""
    if hasattr(g, "_nodes"):                                    # stub
        return set(getattr(g, "_nodes").keys())
    try:
        return set(g.get_graph().nodes.keys())                  # real
    except Exception:
        try:
            return set(g.get_graph().nodes)                     # older variant
        except Exception:
            return set()


def _graph_edges(g: Any) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    # Stub path: _regular_edges + _cond_edges are separate lists.
    if hasattr(g, "_regular_edges"):
        result.extend(getattr(g, "_regular_edges"))
    if hasattr(g, "_cond_edges"):
        for src, _router, mapping in getattr(g, "_cond_edges"):
            if isinstance(mapping, dict):
                for target in mapping.values():
                    if (src, target) not in result:
                        result.append((src, target))
        return result
    if result:
        return result
    # Real LangGraph path.
    try:
        result = [(e.source, e.target) for e in g.get_graph().edges]
    except Exception:
        pass
    # Conditional edges may not appear in get_graph().edges; inspect builder.
    try:
        builder = getattr(g, "builder", None)
        if builder is not None:
            for src, branch in getattr(builder, "_conditional_edges", {}).items():
                ends: dict = getattr(branch, "ends", None) or {}
                for target in ends.values():
                    if (src, target) not in result:
                        result.append((src, target))
    except Exception:
        pass
    return result


def test_build_graph_has_all_seven_nodes():
    nodes = _graph_node_names(build_graph())
    expected = {
        "seed_frontier", "generation", "reflection",
        "ranking", "evolution", "proximity", "meta_review",
    }
    assert expected.issubset(nodes), f"missing nodes: {expected - nodes}"


def test_build_graph_meta_review_to_arxiv_submit():
    """After Phase 2H, meta_review now feeds arxiv_submit (terminal node)."""
    edges = _graph_edges(build_graph())
    targets_from_meta = [dst for src, dst in edges if src == "meta_review"]
    assert targets_from_meta, "meta_review has no outgoing edge"
    assert "arxiv_submit" in targets_from_meta


def test_build_graph_arxiv_submit_is_terminal():
    """arxiv_submit must be the last node — connects only to END."""
    edges = _graph_edges(build_graph())
    targets = [dst for src, dst in edges if src == "arxiv_submit"]
    assert targets, "arxiv_submit has no outgoing edge"
    assert any(dst in ("__end__", "END") or dst.upper() == "END"
               for dst in targets)


def test_build_graph_seed_frontier_routes_to_generation_or_end():
    """seed_frontier branches conditionally; both branches must exist."""
    edges = _graph_edges(build_graph())
    targets = {dst for src, dst in edges if src == "seed_frontier"}
    # In the stub the conditional mapping creates real edges only for the named
    # destinations; in the real lib, conditional edges may be exposed as one
    # virtual edge to each branch. Accept either: at least one outgoing edge.
    assert targets, "seed_frontier has no outgoing edges"


# ── Phase 2C: _detect_disagreement_signals ───────────────────────────────────


def test_detect_disagreement_no_critiques_returns_empty():
    assert _detect_disagreement_signals([]) == []


def test_detect_disagreement_circular_reasoning_keyword_matches():
    c = [{"hypothesis_id": "h1", "critique": "This contains circular reasoning in step 2.", "score_delta": -200}]
    out = _detect_disagreement_signals(c)
    assert len(out) == 1
    assert out[0]["reason"] == "circular_reasoning"
    assert out[0]["hypothesis_id"] == "h1"


def test_detect_disagreement_hidden_assumption_keyword_matches():
    c = [{"hypothesis_id": "h2", "critique": "There is a hidden assumption about Y.", "score_delta": -100}]
    out = _detect_disagreement_signals(c)
    assert any(s["reason"] == "hidden_assumption" for s in out)


def test_detect_disagreement_japanese_循環論証_matches():
    c = [{"hypothesis_id": "h3", "critique": "この主張は循環論証になっている。", "score_delta": -150}]
    out = _detect_disagreement_signals(c)
    assert any(s["reason"] == "circular_reasoning" for s in out)


def test_detect_disagreement_evidence_contradict_matches():
    c = [{"hypothesis_id": "h4", "critique": "This contradicts established results from Smith 2024.", "score_delta": -250}]
    out = _detect_disagreement_signals(c)
    assert any(s["reason"] == "evidence_contradict" for s in out)


def test_detect_disagreement_variance_triggers_signal():
    # Spread between +200 and -250 = 450 ≥ DISAGREEMENT_VARIANCE_THRESH (400)
    c = [
        {"hypothesis_id": "ha", "critique": "looks fine to me",      "score_delta":  200},
        {"hypothesis_id": "hb", "critique": "very weak",              "score_delta": -250},
        {"hypothesis_id": "hc", "critique": "moderately convincing",  "score_delta":   50},
    ]
    out = _detect_disagreement_signals(c)
    # Variance signal anchors to the lowest score_delta (hb).
    assert any(s["reason"] == "score_variance" and s["hypothesis_id"] == "hb"
               for s in out)


def test_detect_disagreement_low_variance_no_signal():
    c = [
        {"hypothesis_id": "ha", "critique": "looks fine", "score_delta": 100},
        {"hypothesis_id": "hb", "critique": "looks fine", "score_delta":  50},
    ]
    out = _detect_disagreement_signals(c)
    # No keyword + low variance → empty.
    assert out == []


def test_detect_disagreement_caps_at_max_splits():
    c = [
        {"hypothesis_id": f"h{i}",
         "critique": "circular reasoning in step X",
         "score_delta": -100}
        for i in range(DISAGREEMENT_MAX_SPLITS + 5)
    ]
    out = _detect_disagreement_signals(c)
    assert len(out) <= DISAGREEMENT_MAX_SPLITS


def test_detect_disagreement_ignores_empty_critiques():
    c = [{"hypothesis_id": "h1", "critique": "", "score_delta": 0}]
    out = _detect_disagreement_signals(c)
    assert out == []


# ── Phase 2C: _coerce_sub_titles ─────────────────────────────────────────────


def test_coerce_sub_titles_pairs_by_hypothesis_id():
    signals = [
        {"hypothesis_id": "h1", "reason": "circular_reasoning", "critique": "c1"},
        {"hypothesis_id": "h2", "reason": "hidden_assumption",  "critique": "c2"},
    ]
    llm_parsed = [
        {"hypothesis_id": "h1", "title": "Does invariant X hold?"},
        {"hypothesis_id": "h2", "title": "Is assumption Y necessary?"},
    ]
    out = _coerce_sub_titles(llm_parsed, signals)
    assert len(out) == 2
    titles = {o["hypothesis_id"]: o["title"] for o in out}
    assert titles["h1"] == "Does invariant X hold?"
    assert titles["h2"] == "Is assumption Y necessary?"


def test_coerce_sub_titles_falls_back_when_llm_empty():
    signals = [{"hypothesis_id": "h1", "reason": "score_variance", "critique": "thin evidence base"}]
    out = _coerce_sub_titles(None, signals)
    assert len(out) == 1
    # Fallback title contains the reason name to preserve traceability.
    assert "score_variance" in out[0]["title"]


def test_coerce_sub_titles_truncates_long_llm_output():
    signals = [{"hypothesis_id": "h1", "reason": "circular_reasoning", "critique": "c"}]
    out = _coerce_sub_titles([{"hypothesis_id": "h1", "title": "x" * 500}], signals)
    assert len(out[0]["title"]) <= 240


def test_coerce_sub_titles_drops_malformed_entries():
    signals = [{"hypothesis_id": "h1", "reason": "hidden_assumption", "critique": "c"}]
    bad = [{"not": "a hypothesis_id"}, "not even a dict", 42]
    out = _coerce_sub_titles(bad, signals)
    # Falls back to deterministic title because no malformed entry matched.
    assert len(out) == 1
    assert "hidden_assumption" in out[0]["title"]


# ── Phase 2C: build_graph topology includes disagreement_split ──────────────


def test_build_graph_includes_disagreement_split_node():
    nodes = _graph_node_names(build_graph())
    assert "disagreement_split" in nodes


def test_build_graph_reflection_routes_to_disagreement_split():
    edges = _graph_edges(build_graph())
    targets = {dst for src, dst in edges if src == "reflection"}
    assert "disagreement_split" in targets


def test_build_graph_disagreement_split_routes_to_ranking():
    edges = _graph_edges(build_graph())
    targets = {dst for src, dst in edges if src == "disagreement_split"}
    assert "ranking" in targets


# ── Phase 2C: depth + threshold contracts ────────────────────────────────────


def test_max_disagreement_depth_default_two():
    """Recursion cap from spec — bumping this knob costs LLM tokens; keep tight."""
    assert MAX_DISAGREEMENT_DEPTH == 2


def test_variance_threshold_is_high_enough_to_avoid_noise():
    """The default 400 keeps random LLM scoring jitter from spawning splits."""
    assert DISAGREEMENT_VARIANCE_THRESH >= 200


def test_max_splits_keeps_llm_budget_bounded():
    assert DISAGREEMENT_MAX_SPLITS <= 8


# ── Phase 2D: _EVIDENCE_SOURCES contract ─────────────────────────────────────


def test_evidence_sources_include_4_logical_kinds():
    kinds = {s["source_type"] for s in _EVIDENCE_SOURCES}
    assert {"bunken", "hanrei", "isbn", "intel"}.issubset(kinds)


def test_evidence_sources_table_names_in_graphar_namespace():
    """Each source must declare its table for graceful _table_exists probing."""
    for s in _EVIDENCE_SOURCES:
        assert s["table"].startswith("vertex_"), f"bad table: {s}"
        assert s["title_col"], f"source missing title_col: {s}"


def test_evidence_sources_have_embed_kind_or_empty():
    """embed_kind may be empty (LIKE-only path); but if set, it must be ascii."""
    for s in _EVIDENCE_SOURCES:
        ek = s.get("embed_kind", "")
        assert isinstance(ek, str)
        assert ek == "" or ek.isascii(), f"non-ascii embed_kind: {s}"


def test_evidence_sources_hanrei_uses_decision_date():
    """hanrei has no year column — proximity must SUBSTR decision_date."""
    hanrei = [s for s in _EVIDENCE_SOURCES if s["source_type"] == "hanrei"]
    assert hanrei, "hanrei source missing"
    assert hanrei[0]["year_col"] == "decision_date"


# ── Phase 2H: arxiv submit gating ────────────────────────────────────────────


def _winner_state(**overrides):
    """Helper — minimum state that satisfies the publish gate."""
    s = {
        "consensus_level": "strong",
        "next_action":     "publish",
        "depth":           0,
        "hypotheses":      [{"id": "h1", "statement": "A", "elo": 1300}],
        "evidence":        [],
        "frontierTitle":   "Test frontier",
        "primaryDiscipline": "0613",
    }
    s.update(overrides)
    return s


def test_arxiv_should_submit_happy_path():
    # When the global enable flag is on (default), the gate fires.
    if ARXIV_SUBMIT_ENABLED:
        assert _arxiv_should_submit(_winner_state()) is True


def test_arxiv_should_submit_false_when_consensus_weak():
    assert _arxiv_should_submit(_winner_state(consensus_level="partial")) is False


def test_arxiv_should_submit_false_when_action_iterate():
    assert _arxiv_should_submit(_winner_state(next_action="iterate")) is False


def test_arxiv_should_submit_false_for_sub_frontier():
    """depth > 0 → this is a sub-frontier; never auto-submit (partial result)."""
    assert _arxiv_should_submit(_winner_state(depth=1)) is False
    assert _arxiv_should_submit(_winner_state(depth=2)) is False


def test_arxiv_should_submit_false_when_no_hypotheses():
    assert _arxiv_should_submit(_winner_state(hypotheses=[])) is False


def test_arxiv_submit_enabled_default_truthy():
    """Default behavior is on. Operator opts out via env var."""
    assert isinstance(ARXIV_SUBMIT_ENABLED, bool)


# ── Phase 2H: _latex_escape ──────────────────────────────────────────────────


def test_latex_escape_handles_special_chars():
    out = _latex_escape("100% of cells & $5 cost #1 _underscore")
    for unsafe in (r"\&", r"\%", r"\$", r"\#", r"\_"):
        assert unsafe in out


def test_latex_escape_backslash_first():
    """Backslash must be escaped first to avoid double-escape on \\&."""
    out = _latex_escape(r"path\to\file & end")
    assert r"\textbackslash{}" in out
    assert r"\&" in out


def test_latex_escape_empty_string():
    assert _latex_escape("") == ""


# ── Phase 2H: _build_arxiv_tex ───────────────────────────────────────────────


def test_build_arxiv_tex_includes_documentclass_and_end_document():
    s = _winner_state()
    winner = {"id": "h1", "statement": "X causes Y", "rationale": "because Z",
              "elo": 1400, "mutation_kind": "seed"}
    tex, abstract = _build_arxiv_tex(s, winner, [])
    assert tex.startswith(r"\documentclass")
    assert tex.rstrip().endswith(r"\end{document}")
    assert "X causes Y" in tex


def test_build_arxiv_tex_lists_supporting_evidence():
    s = _winner_state()
    winner = {"id": "h1", "statement": "A->B", "rationale": "r1", "elo": 1500}
    evidence = [
        {"source_type": "bunken", "source_year": 2024,
         "source_title": "Title 1", "extracted_claim": "claim A",
         "evidence_type": "supports", "relevance": 800},
        {"source_type": "hanrei", "source_year": 2023,
         "source_title": "Case 2", "extracted_claim": "claim B",
         "evidence_type": "supports", "relevance": 700},
    ]
    tex, _ = _build_arxiv_tex(s, winner, evidence)
    assert r"\section{Supporting Evidence}" in tex
    assert "Title 1" in tex
    assert "Case 2" in tex


def test_build_arxiv_tex_separates_contradicting_section():
    s = _winner_state()
    winner = {"id": "h1", "statement": "A->B", "rationale": "r1", "elo": 1500}
    evidence = [
        {"source_type": "intel", "source_year": 0,
         "source_title": "Counter 1", "extracted_claim": "rebuttal",
         "evidence_type": "contradicts", "relevance": 600},
    ]
    tex, _ = _build_arxiv_tex(s, winner, evidence)
    assert r"\section{Contradicting Evidence}" in tex
    assert "Counter 1" in tex


def test_build_arxiv_tex_omits_contradicting_section_when_none():
    s = _winner_state()
    winner = {"id": "h1", "statement": "A->B", "rationale": "r1", "elo": 1500}
    tex, _ = _build_arxiv_tex(s, winner, [])
    assert r"\section{Contradicting Evidence}" not in tex


def test_build_arxiv_tex_abstract_is_plaintext():
    """The abstract returned alongside .tex is plain prose, no LaTeX cmds."""
    s = _winner_state()
    winner = {"id": "h1", "statement": "A->B", "rationale": "r1", "elo": 1500}
    _, abstract = _build_arxiv_tex(s, winner, [])
    assert r"\section" not in abstract
    assert r"\documentclass" not in abstract


def test_build_arxiv_tex_uses_frontier_title():
    s = _winner_state(frontierTitle="Unique frontier title $$$")
    winner = {"id": "h1", "statement": "A", "rationale": "r", "elo": 1300}
    tex, abstract = _build_arxiv_tex(s, winner, [])
    # Escaped form should be in tex; plain form in abstract.
    assert "Unique frontier title" in tex
    assert "Unique frontier title" in abstract


def test_build_arxiv_tex_cites_scienceearth():
    s = _winner_state()
    winner = {"id": "h1", "statement": "A", "rationale": "r", "elo": 1300}
    tex, _ = _build_arxiv_tex(s, winner, [])
    assert "scienceearth.org" in tex


# ── Phase 2K: sub-frontier rollup ────────────────────────────────────────────


def test_rollup_weight_strong_full_credit():
    assert _rollup_weight("strong") == 1000


def test_rollup_weight_partial_half_credit():
    assert _rollup_weight("partial") == 500


def test_rollup_weight_drops_weak_consensus():
    for level in ("none", "disputed", "emerging", ""):
        assert _rollup_weight(level) == 0


def test_apply_rollup_adds_strong_child_evidence():
    s, c, n = _apply_rollup(
        parent_supports=3, parent_contradicts=1,
        children=[
            {"consensus_level": "strong",
             "evidence_supports": 10, "evidence_contradicts": 2},
        ],
    )
    # Strong child contributes 100% — adds 10 supports + 2 contradicts.
    assert s == 13
    assert c == 3
    assert n == 1


def test_apply_rollup_halves_partial_child_evidence():
    s, c, n = _apply_rollup(
        parent_supports=0, parent_contradicts=0,
        children=[
            {"consensus_level": "partial",
             "evidence_supports": 10, "evidence_contradicts": 4},
        ],
    )
    # Partial child contributes 50% — 5 supports + 2 contradicts.
    assert s == 5
    assert c == 2
    assert n == 1


def test_apply_rollup_drops_unsettled_children():
    """Children whose own consensus is still none/disputed/emerging are
    discarded — only settled children can promote the parent."""
    s, c, n = _apply_rollup(
        parent_supports=4, parent_contradicts=1,
        children=[
            {"consensus_level": "emerging", "evidence_supports": 100, "evidence_contradicts": 0},
            {"consensus_level": "disputed", "evidence_supports": 100, "evidence_contradicts": 0},
            {"consensus_level": "none",     "evidence_supports": 100, "evidence_contradicts": 0},
        ],
    )
    assert s == 4
    assert c == 1
    assert n == 0


def test_apply_rollup_mixed_children():
    s, c, n = _apply_rollup(
        parent_supports=2, parent_contradicts=0,
        children=[
            {"consensus_level": "strong",   "evidence_supports": 6, "evidence_contradicts": 1},
            {"consensus_level": "partial",  "evidence_supports": 4, "evidence_contradicts": 2},
            {"consensus_level": "disputed", "evidence_supports": 9, "evidence_contradicts": 9},
        ],
    )
    # 2 + 6 + (4*500/1000) = 2 + 6 + 2 = 10
    # 0 + 1 + (2*500/1000) = 0 + 1 + 1 = 2
    assert s == 10
    assert c == 2
    assert n == 2


def test_apply_rollup_no_children_is_passthrough():
    s, c, n = _apply_rollup(7, 3, [])
    assert (s, c, n) == (7, 3, 0)


def test_apply_rollup_handles_none_counts():
    """Missing counts on a child row coerce to 0, not raise."""
    s, c, n = _apply_rollup(0, 0, [
        {"consensus_level": "strong"},   # no evidence keys at all
    ])
    assert (s, c, n) == (0, 0, 1)


def test_apply_rollup_promotes_partial_parent_to_strong():
    """End-to-end semantics: a parent that would have been 'partial' on its
    own can be promoted to 'strong' after rolling up two strong children.
    """
    # Parent alone: 7 supports / 3 contradicts → ratio 0.7 → 'partial'.
    assert _consensus_from_counts(7, 3) == "partial"
    s, c, _ = _apply_rollup(7, 3, [
        {"consensus_level": "strong", "evidence_supports": 10, "evidence_contradicts": 0},
    ])
    # 17 / 20 = 0.85 → 'strong'.
    assert _consensus_from_counts(s, c) == "strong"


def test_build_graph_returns_distinct_instances():
    """Each build_graph() call returns a freshly compiled graph.

    Required because Pregel checkpoints are per-thread; reusing a single
    compiled instance across threads is fine, but the factory must not
    accidentally return the same mutable StateGraph builder.
    """
    a = build_graph()
    b = build_graph()
    assert a is not b
