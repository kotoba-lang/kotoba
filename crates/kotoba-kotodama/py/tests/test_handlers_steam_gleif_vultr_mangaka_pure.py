"""Pure helper tests for steam_release, gleif_lookup, vultr_inference, and
mangaka_storyboard handlers.

Covers pure functions with no DB/HTTP/LLM dependencies:
- steam_release: _parse_date / _YEAR_RE / _FORMATS
- gleif_lookup:  _url_for / _addr_line / _flatten_hit / _pick_best
- vultr_inference: _err / _ENDPOINT / _KEY_ENV
- mangaka_storyboard: constants (_VALID_STYLES / _DEFAULT_PAGES etc.)
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf so @udf() decorators work without the runtime dep.
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub


def _load(name: str) -> types.ModuleType:
    """Load a handler module by file path (bypasses handlers/__init__)."""
    mod_key = f"_handler_{name}"
    if mod_key in sys.modules:
        return sys.modules[mod_key]
    src = _py_src / "kotodama" / "handlers" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(mod_key, src)
    assert spec is not None and spec.loader is not None
    mod = types.ModuleType(mod_key)
    sys.modules[mod_key] = mod
    try:
        from kotodama import registry as _reg  # noqa: PLC0415
        to_del = [
            k for k, v in _reg._HANDLERS.items()
            if getattr(getattr(v, "fn", None), "__code__", None)
            and str(src) in v.fn.__code__.co_filename
        ]
        for k in to_del:
            del _reg._HANDLERS[k]
    except Exception:
        pass
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


SR = _load("steam_release")
GL = _load("gleif_lookup")
VI = _load("vultr_inference")
MS = _load("mangaka_storyboard")


# ─── steam_release — _parse_date ─────────────────────────────────────────────

def test_sr_parse_date_dd_mon_yyyy():
    iso, year = SR._parse_date("10 Aug, 2021")
    assert iso == "2021-08-10"
    assert year == 2021


def test_sr_parse_date_mon_dd_yyyy():
    iso, year = SR._parse_date("Aug 10, 2021")
    assert iso == "2021-08-10"
    assert year == 2021


def test_sr_parse_date_full_month():
    iso, year = SR._parse_date("10 August, 2021")
    assert iso == "2021-08-10"
    assert year == 2021


def test_sr_parse_date_empty_returns_none_none():
    iso, year = SR._parse_date("")
    assert iso is None
    assert year is None


def test_sr_parse_date_none_like_returns_none_none():
    iso, year = SR._parse_date(None)  # type: ignore[arg-type]
    assert iso is None
    assert year is None


def test_sr_parse_date_year_fallback():
    iso, year = SR._parse_date("Q1 2019")
    assert year == 2019
    assert iso == "2019-01-01"


def test_sr_parse_date_unrecognized_returns_none():
    iso, year = SR._parse_date("Coming Soon")
    assert iso is None
    assert year is None


def test_sr_parse_date_returns_tuple():
    result = SR._parse_date("1 Jan, 2020")
    assert isinstance(result, tuple)
    assert len(result) == 2


# ─── steam_release — constants ────────────────────────────────────────────────

def test_sr_year_re_matches_4_digit_year():
    m = SR._YEAR_RE.search("Released in 2024 globally")
    assert m is not None
    assert m.group(1) == "2024"


def test_sr_year_re_no_match_on_3_digits():
    m = SR._YEAR_RE.search("abc 999 def")
    assert m is None


def test_sr_formats_is_tuple():
    assert isinstance(SR._FORMATS, tuple)


def test_sr_formats_not_empty():
    assert len(SR._FORMATS) > 0


# ─── gleif_lookup — _url_for ──────────────────────────────────────────────────

def test_gl_url_for_returns_string():
    result = GL._url_for("Acme Corp")
    assert isinstance(result, str)


def test_gl_url_for_contains_encoded_name():
    result = GL._url_for("Acme Corp")
    assert "Acme" in result or "Acme+Corp" in result or "Acme%20Corp" in result


def test_gl_url_for_starts_with_gleif_base():
    result = GL._url_for("Test")
    assert result.startswith("https://api.gleif.org")


def test_gl_url_for_contains_filter_param():
    result = GL._url_for("Test Company")
    assert "legalName" in result or "filter" in result


# ─── gleif_lookup — _addr_line ────────────────────────────────────────────────

def test_gl_addr_line_full_address():
    addr = {
        "addressLines": ["123 Main St"],
        "city": "Tokyo",
        "region": "Tokyo-to",
        "postalCode": "100-0001",
        "country": "JP",
    }
    result = GL._addr_line(addr)
    assert "123 Main St" in result
    assert "Tokyo" in result
    assert "JP" in result


def test_gl_addr_line_empty_dict_returns_empty():
    result = GL._addr_line({})
    assert result == ""


def test_gl_addr_line_none_returns_empty():
    result = GL._addr_line(None)
    assert result == ""


def test_gl_addr_line_non_dict_returns_empty():
    result = GL._addr_line("not a dict")  # type: ignore[arg-type]
    assert result == ""


def test_gl_addr_line_returns_string():
    result = GL._addr_line({"city": "Paris", "country": "FR"})
    assert isinstance(result, str)


def test_gl_addr_line_city_only():
    result = GL._addr_line({"city": "Osaka"})
    assert "Osaka" in result


# ─── gleif_lookup — _flatten_hit ─────────────────────────────────────────────

def test_gl_flatten_hit_non_dict_returns_empty():
    result = GL._flatten_hit("not a dict")  # type: ignore[arg-type]
    assert result == {}


def test_gl_flatten_hit_empty_dict_returns_dict():
    result = GL._flatten_hit({})
    assert isinstance(result, dict)


def test_gl_flatten_hit_has_expected_keys():
    result = GL._flatten_hit({})
    for key in ("lei", "legalName", "country", "jurisdiction", "status"):
        assert key in result


def test_gl_flatten_hit_extracts_id():
    hit = {"id": "LEI123456789", "attributes": {}}
    result = GL._flatten_hit(hit)
    assert result["lei"] == "LEI123456789"


def test_gl_flatten_hit_missing_id_lei_is_none():
    hit = {"attributes": {}}
    result = GL._flatten_hit(hit)
    assert result["lei"] is None


def test_gl_flatten_hit_full_structure():
    hit = {
        "id": "ABC123",
        "attributes": {
            "entity": {
                "legalName": {"name": "Acme Corp"},
                "legalAddress": {"country": "US", "addressLines": ["1 Broadway"]},
                "jurisdiction": "US-NY",
                "registeredAs": "REG001",
                "status": "ACTIVE",
                "creationDate": "2010-05-01T00:00:00Z",
            }
        },
    }
    result = GL._flatten_hit(hit)
    assert result["lei"] == "ABC123"
    assert result["legalName"] == "Acme Corp"
    assert result["country"] == "US"
    assert result["jurisdiction"] == "US-NY"
    assert result["status"] == "ACTIVE"
    assert result["incorporationDate"] == "2010-05-01"


# ─── gleif_lookup — _pick_best ────────────────────────────────────────────────

def test_gl_pick_best_empty_hits_returns_empty():
    result = GL._pick_best([], "US")
    assert result == {}


def test_gl_pick_best_no_hint_returns_first():
    hits = [
        {"id": "LEI001", "attributes": {"entity": {"legalAddress": {"country": "JP"}, "legalName": {}}}},
        {"id": "LEI002", "attributes": {"entity": {"legalAddress": {"country": "US"}, "legalName": {}}}},
    ]
    result = GL._pick_best(hits, "")
    assert result["lei"] == "LEI001"


def test_gl_pick_best_hint_selects_matching_country():
    hits = [
        {"id": "LEI001", "attributes": {"entity": {"legalAddress": {"country": "JP"}, "legalName": {}}}},
        {"id": "LEI002", "attributes": {"entity": {"legalAddress": {"country": "US"}, "legalName": {}}}},
    ]
    result = GL._pick_best(hits, "US")
    assert result["lei"] == "LEI002"


def test_gl_pick_best_hint_case_insensitive():
    hits = [
        {"id": "LEI001", "attributes": {"entity": {"legalAddress": {"country": "JP"}, "legalName": {}}}},
        {"id": "LEI002", "attributes": {"entity": {"legalAddress": {"country": "US"}, "legalName": {}}}},
    ]
    result = GL._pick_best(hits, "us")
    assert result["lei"] == "LEI002"


def test_gl_pick_best_no_match_falls_back_to_first():
    hits = [
        {"id": "LEI001", "attributes": {"entity": {"legalAddress": {"country": "JP"}, "legalName": {}}}},
    ]
    result = GL._pick_best(hits, "DE")
    assert result["lei"] == "LEI001"


# ─── vultr_inference — _err ───────────────────────────────────────────────────

def test_vi_err_returns_string():
    result = VI._err("something went wrong")
    assert isinstance(result, str)


def test_vi_err_is_json():
    import json
    result = VI._err("test error")
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


def test_vi_err_contains_error_key():
    import json
    result = VI._err("fail")
    parsed = json.loads(result)
    assert "error" in parsed
    assert parsed["error"] == "fail"


def test_vi_err_extra_kwargs_included():
    import json
    result = VI._err("oops", code=503, retry=True)
    parsed = json.loads(result)
    assert parsed["code"] == 503
    assert parsed["retry"] is True


def test_vi_err_empty_message():
    import json
    result = VI._err("")
    parsed = json.loads(result)
    assert parsed["error"] == ""


# ─── vultr_inference — constants ─────────────────────────────────────────────

def test_vi_endpoint_is_string():
    assert isinstance(VI._ENDPOINT, str)


def test_vi_endpoint_starts_with_https():
    assert VI._ENDPOINT.startswith("https://")


def test_vi_key_env_is_string():
    assert isinstance(VI._KEY_ENV, str)


def test_vi_key_env_not_empty():
    assert len(VI._KEY_ENV) > 0


# ─── mangaka_storyboard — constants ──────────────────────────────────────────

def test_ms_valid_styles_is_set():
    assert isinstance(MS._VALID_STYLES, set)


def test_ms_valid_styles_contains_shonen():
    assert "shonen" in MS._VALID_STYLES


def test_ms_valid_styles_contains_seinen():
    assert "seinen" in MS._VALID_STYLES


def test_ms_valid_styles_not_empty():
    assert len(MS._VALID_STYLES) >= 4


def test_ms_default_pages_is_int():
    assert isinstance(MS._DEFAULT_PAGES, int)


def test_ms_default_pages_positive():
    assert MS._DEFAULT_PAGES > 0


def test_ms_max_pages_gte_default():
    assert MS._MAX_PAGES >= MS._DEFAULT_PAGES


def test_ms_default_panels_per_page_is_int():
    assert isinstance(MS._DEFAULT_PANELS_PER_PAGE, int)


def test_ms_max_panels_gte_default():
    assert MS._MAX_PANELS_PER_PAGE >= MS._DEFAULT_PANELS_PER_PAGE


def test_ms_default_style_in_valid_styles():
    assert MS._DEFAULT_STYLE in MS._VALID_STYLES


def test_ms_default_max_tokens_is_int():
    assert isinstance(MS._DEFAULT_MAX_TOKENS, int)


def test_ms_default_max_tokens_positive():
    assert MS._DEFAULT_MAX_TOKENS > 0
