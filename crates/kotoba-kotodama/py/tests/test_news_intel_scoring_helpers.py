"""Tests for pure scoring helpers in handlers/news_intel.py:
_clamp01, source_credibility, intel_priority."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_news_intel"
if _MOD_NAME in sys.modules:
    NI = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _nsid in [k for k in list(_reg._HANDLERS.keys()) if "news_source_credibility" in k or "news_intel_priority" in k]:
            del _reg._HANDLERS[_nsid]
    except Exception:
        pass

    def _load_mod(name: str, rel: str) -> types.ModuleType:
        path = _py_src / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    NI = _load_mod(_MOD_NAME, "kotodama/handlers/news_intel.py")


# ─── _clamp01 ────────────────────────────────────────────────────────────────

def test_clamp01_in_range() -> None:
    assert NI._clamp01(0.5) == 0.5


def test_clamp01_below_zero() -> None:
    assert NI._clamp01(-0.5) == 0.0


def test_clamp01_above_one() -> None:
    assert NI._clamp01(1.5) == 1.0


def test_clamp01_exactly_zero() -> None:
    assert NI._clamp01(0.0) == 0.0


def test_clamp01_exactly_one() -> None:
    assert NI._clamp01(1.0) == 1.0


# ─── source_credibility ──────────────────────────────────────────────────────

def test_source_credibility_returns_float() -> None:
    result = NI.source_credibility("government", False, False)
    assert isinstance(result, float)


def test_source_credibility_in_range() -> None:
    result = NI.source_credibility("media", False, False)
    assert 0.0 <= result <= 1.0


def test_source_credibility_government_higher_than_social() -> None:
    gov = NI.source_credibility("government", False, False)
    soc = NI.source_credibility("social", False, False)
    assert gov > soc


def test_source_credibility_official_flag_boosts_score() -> None:
    base = NI.source_credibility("media", False, False)
    boosted = NI.source_credibility("media", False, True)
    assert boosted > base


def test_source_credibility_primary_flag_boosts_score() -> None:
    base = NI.source_credibility("media", False, False)
    boosted = NI.source_credibility("media", True, False)
    assert boosted > base


def test_source_credibility_both_flags_boosted_most() -> None:
    base = NI.source_credibility("media", False, False)
    both = NI.source_credibility("media", True, True)
    official_only = NI.source_credibility("media", False, True)
    assert both >= official_only
    assert both > base


def test_source_credibility_unknown_type_defaults_to_midpoint() -> None:
    result = NI.source_credibility("unknown_type", False, False)
    assert 0.4 <= result <= 0.65


def test_source_credibility_regulator_is_highest_base() -> None:
    reg = NI.source_credibility("regulator", False, False)
    media = NI.source_credibility("media", False, False)
    assert reg > media


def test_source_credibility_capped_at_1() -> None:
    result = NI.source_credibility("regulator", True, True)
    assert result <= 1.0


def test_source_credibility_empty_type_uses_default() -> None:
    result = NI.source_credibility("", False, False)
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0


def test_source_credibility_type_case_insensitive() -> None:
    lower = NI.source_credibility("government", False, False)
    upper = NI.source_credibility("GOVERNMENT", False, False)
    assert lower == upper


def test_source_credibility_type_strips_whitespace() -> None:
    stripped = NI.source_credibility("  government  ", False, False)
    normal = NI.source_credibility("government", False, False)
    assert stripped == normal


# ─── intel_priority ──────────────────────────────────────────────────────────

def test_intel_priority_returns_float() -> None:
    result = NI.intel_priority(1, 1, 1, 0.0, 0.5)
    assert isinstance(result, float)


def test_intel_priority_in_range() -> None:
    result = NI.intel_priority(0, 0, 0, 0.0, 0.0)
    assert 0.0 <= result <= 1.0


def test_intel_priority_increases_with_evidence() -> None:
    low = NI.intel_priority(0, 0, 0, 0.0, 0.0)
    high = NI.intel_priority(4, 0, 0, 0.0, 0.0)
    assert high > low


def test_intel_priority_increases_with_official_count() -> None:
    low = NI.intel_priority(0, 0, 0, 0.0, 0.0)
    high = NI.intel_priority(0, 2, 0, 0.0, 0.0)
    assert high > low


def test_intel_priority_increases_with_corroboration() -> None:
    low = NI.intel_priority(0, 0, 0, 0.0, 0.0)
    high = NI.intel_priority(0, 0, 2, 0.0, 0.0)
    assert high > low


def test_intel_priority_decreases_with_higher_recency_hours() -> None:
    fresh = NI.intel_priority(0, 0, 0, 0.0, 0.0)
    stale = NI.intel_priority(0, 0, 0, 72.0, 0.0)
    assert fresh >= stale


def test_intel_priority_increases_with_impact() -> None:
    low = NI.intel_priority(0, 0, 0, 0.0, 0.0)
    high = NI.intel_priority(0, 0, 0, 0.0, 1.0)
    assert high > low


def test_intel_priority_capped_at_1() -> None:
    result = NI.intel_priority(100, 100, 100, 0.0, 1.0)
    assert result <= 1.0


def test_intel_priority_none_inputs_use_zero() -> None:
    result = NI.intel_priority(0, 0, 0, None, None)
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0


def test_intel_priority_negative_counts_clamped() -> None:
    result = NI.intel_priority(-5, -5, -5, 0.0, 0.0)
    assert isinstance(result, float)
    assert result >= 0.0


def test_intel_priority_rounded_to_4_decimals() -> None:
    result = NI.intel_priority(1, 1, 1, 1.0, 0.5)
    assert result == round(result, 4)
