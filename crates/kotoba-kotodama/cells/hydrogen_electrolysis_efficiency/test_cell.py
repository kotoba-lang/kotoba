from __future__ import annotations

from .cell import solve


def test_solve_returns_actor_and_engine_boundary():
    out = solve()
    assert out["actor"] == "hydrogen_electrolysis"
    assert out["engine"] == "kami-hydrogen-electrolysis-sim"


def test_solve_recommends_low_temperature_hybrid():
    out = solve()
    assert out["best_low_temperature"]["name"] == "cfe-zero-gap-aem-high-pressure"


def test_solve_emits_kotoba_datoms_and_scene():
    out = solve()
    assert out["datoms"]
    assert out["scene"]["nodes"]


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"{len(tests)}/{len(tests)} passed")
