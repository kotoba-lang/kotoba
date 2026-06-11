from __future__ import annotations

import pathlib
import sys
from typing import Any


def _root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "20-actors").exists() and (parent / "40-engine").exists():
            return parent
    raise RuntimeError("etzhayyim root not found")


def _load_actor() -> None:
    methods = _root() / "20-actors" / "hydrogen_electrolysis" / "methods"
    if str(methods) not in sys.path:
        sys.path.insert(0, str(methods))


def solve(input: dict[str, Any] | None = None) -> dict[str, Any]:
    _load_actor()
    from electrolysis import kotoba_datoms, run_comparison

    payload = input or {}
    active_area_cm2 = float(payload.get("active_area_cm2", 10_000.0))
    comparison = run_comparison(active_area_cm2=active_area_cm2)
    return {
        "cell": "hydrogen_electrolysis_efficiency",
        "actor": comparison["actor"],
        "engine": comparison["engine"],
        "best_low_temperature": comparison["best_low_temperature"],
        "best_electrical": comparison["best_electrical"],
        "results": comparison["results"],
        "datoms": kotoba_datoms(comparison),
        "scene": comparison["scene"],
    }
