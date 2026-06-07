"""Tests for pure helpers in handlers/steam_release.py (_parse_date)
and handlers/actor_embed.py (_compose)."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))


def _load_handler(mod_name: str, rel: str) -> types.ModuleType:
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    try:
        from kotodama import registry as _reg
        for _k in [k for k in list(_reg._HANDLERS.keys()) if any(x in k.lower() for x in rel.split("/")[-1].replace(".py","").split("_"))]:
            del _reg._HANDLERS[_k]
    except Exception:
        pass
    path = _py_src / rel
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = types.ModuleType(mod_name)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


SR = _load_handler("_handler_steam_release", "kotodama/handlers/steam_release.py")
AE = _load_handler("_handler_actor_embed", "kotodama/handlers/actor_embed.py")


# ─── _parse_date ─────────────────────────────────────────────────────────────

def test_parse_date_none_returns_none() -> None:
    assert SR._parse_date(None) == (None, None)


def test_parse_date_empty_returns_none() -> None:
    assert SR._parse_date("") == (None, None)


def test_parse_date_whitespace_returns_none() -> None:
    assert SR._parse_date("   ") == (None, None)


def test_parse_date_dd_mon_yyyy() -> None:
    date, year = SR._parse_date("15 Jan, 2022")
    assert date == "2022-01-15"
    assert year == 2022


def test_parse_date_mon_dd_yyyy() -> None:
    date, year = SR._parse_date("Jan 15, 2022")
    assert date == "2022-01-15"
    assert year == 2022


def test_parse_date_dd_month_yyyy() -> None:
    date, year = SR._parse_date("15 January, 2022")
    assert date == "2022-01-15"
    assert year == 2022


def test_parse_date_month_dd_yyyy() -> None:
    date, year = SR._parse_date("January 15, 2022")
    assert date == "2022-01-15"
    assert year == 2022


def test_parse_date_december() -> None:
    date, year = SR._parse_date("31 Dec, 2020")
    assert date == "2020-12-31"
    assert year == 2020


def test_parse_date_year_only_fallback() -> None:
    date, year = SR._parse_date("Q4 2019")
    assert year == 2019
    assert date == "2019-01-01"


def test_parse_date_year_only_with_text() -> None:
    date, year = SR._parse_date("Coming 2025")
    assert year == 2025


def test_parse_date_no_recognizable_date_returns_none() -> None:
    assert SR._parse_date("TBD") == (None, None)


def test_parse_date_returns_iso_string() -> None:
    date, _ = SR._parse_date("5 Mar, 2023")
    assert date == "2023-03-05"


def test_parse_date_year_range_gives_first() -> None:
    _, year = SR._parse_date("2018-2020")
    assert year == 2018


def test_parse_date_early_year() -> None:
    _, year = SR._parse_date("Sep 1, 1998")
    assert year == 1998


def test_parse_date_2000s() -> None:
    date, year = SR._parse_date("1 Jan, 2000")
    assert year == 2000
    assert date == "2000-01-01"


# ─── _compose ────────────────────────────────────────────────────────────────

def test_compose_query_mode_prefix() -> None:
    result = AE._compose("Foo", "A description", "tool", "query")
    assert result.startswith("query: ")


def test_compose_passage_mode_prefix() -> None:
    result = AE._compose("Foo", "A description", "tool", "passage")
    assert result.startswith("passage: ")


def test_compose_non_query_mode_uses_passage_prefix() -> None:
    result = AE._compose("Foo", "desc", "tool", "index")
    assert result.startswith("passage: ")


def test_compose_includes_display_name() -> None:
    result = AE._compose("ActorName", "some description", None, "query")
    assert "ActorName" in result


def test_compose_includes_description() -> None:
    result = AE._compose("Name", "my description", None, "query")
    assert "my description" in result


def test_compose_includes_kind() -> None:
    result = AE._compose("Name", "desc", "tool", "query")
    assert "kind=tool" in result


def test_compose_none_display_name_excluded() -> None:
    result = AE._compose(None, "desc", "tool", "query")
    assert "None" not in result


def test_compose_none_description_excluded() -> None:
    result = AE._compose("Name", None, "tool", "query")
    assert "None" not in result


def test_compose_none_kind_excluded() -> None:
    result = AE._compose("Name", "desc", None, "query")
    assert "kind=" not in result


def test_compose_all_none_returns_empty_body() -> None:
    result = AE._compose(None, None, None, "query")
    assert "(empty)" in result


def test_compose_parts_joined_by_pipe() -> None:
    result = AE._compose("Name", "Desc", "tool", "query")
    assert " | " in result


def test_compose_truncates_at_2000() -> None:
    long_desc = "x" * 3000
    result = AE._compose("A", long_desc, None, "query")
    # total length <= len("query: ") + 2000
    assert len(result) <= len("query: ") + 2000


def test_compose_strips_whitespace_from_parts() -> None:
    result = AE._compose("  Name  ", "  Desc  ", "  tool  ", "query")
    assert "  " not in result.replace("query: ", "")


def test_compose_empty_string_display_name_excluded() -> None:
    result = AE._compose("", "desc", None, "query")
    body = result.replace("query: ", "")
    assert body.startswith("desc")


def test_compose_empty_string_kind_excluded() -> None:
    result = AE._compose("Name", "desc", "", "query")
    assert "kind=" not in result
