"""Tests for pure helper functions in business_person.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import business_person as BP


# ─── _slug ───────────────────────────────────────────────────────────────────

def test_bp_slug_lowercases() -> None:
    assert BP._slug("HELLO") == "hello"


def test_bp_slug_replaces_special_chars() -> None:
    result = BP._slug("hello world!")
    assert " " not in result
    assert "!" not in result
    assert "hello" in result and "world" in result


def test_bp_slug_empty_returns_unknown() -> None:
    assert BP._slug("") == "unknown"
    assert BP._slug(None) == "unknown"


def test_bp_slug_collapses_dashes() -> None:
    result = BP._slug("a--b")
    assert "--" not in result


def test_bp_slug_truncates_at_96() -> None:
    result = BP._slug("a" * 200)
    assert len(result) <= 96


# ─── _stable_id ──────────────────────────────────────────────────────────────

def test_bp_stable_id_deterministic() -> None:
    a = BP._stable_id("person", "John", "Doe")
    b = BP._stable_id("person", "John", "Doe")
    assert a == b


def test_bp_stable_id_starts_with_prefix() -> None:
    result = BP._stable_id("company", "Acme")
    assert result.startswith("company-")


def test_bp_stable_id_varies_by_parts() -> None:
    a = BP._stable_id("p", "John")
    b = BP._stable_id("p", "Jane")
    assert a != b


def test_bp_stable_id_hash_length() -> None:
    result = BP._stable_id("pfx", "val")
    hex_part = result[len("pfx-"):]
    assert len(hex_part) == 20


# ─── _as_rows ────────────────────────────────────────────────────────────────

def test_bp_as_rows_list_of_dicts() -> None:
    result = BP._as_rows([{"a": 1}, {"b": 2}])
    assert len(result) == 2


def test_bp_as_rows_filters_non_dicts() -> None:
    result = BP._as_rows([{"a": 1}, "string", 42])
    assert len(result) == 1


def test_bp_as_rows_empty_list() -> None:
    assert BP._as_rows([]) == []


def test_bp_as_rows_json_string() -> None:
    import json
    result = BP._as_rows(json.dumps([{"x": 1}]))
    assert len(result) == 1
    assert result[0] == {"x": 1}


def test_bp_as_rows_empty_string() -> None:
    assert BP._as_rows("") == []


def test_bp_as_rows_none() -> None:
    assert BP._as_rows(None) == []


# ─── _as_json ────────────────────────────────────────────────────────────────

def test_bp_as_json_dict_passthrough() -> None:
    d = {"a": 1}
    assert BP._as_json(d) == d


def test_bp_as_json_list_passthrough() -> None:
    lst = [1, 2, 3]
    assert BP._as_json(lst) == lst


def test_bp_as_json_json_string() -> None:
    assert BP._as_json('{"key": "val"}') == {"key": "val"}


def test_bp_as_json_empty_returns_none() -> None:
    assert BP._as_json("") is None
    assert BP._as_json(None) is None


# ─── _as_text ────────────────────────────────────────────────────────────────

def test_bp_as_text_strips() -> None:
    assert BP._as_text("  hello  ") == "hello"


def test_bp_as_text_none_returns_empty() -> None:
    assert BP._as_text(None) == ""


def test_bp_as_text_integer() -> None:
    assert BP._as_text(42) == "42"


# ─── _is_public_http_url ─────────────────────────────────────────────────────

def test_bp_is_public_http_url_valid_http() -> None:
    assert BP._is_public_http_url("http://example.com") is True


def test_bp_is_public_http_url_valid_https() -> None:
    assert BP._is_public_http_url("https://example.com/path") is True


def test_bp_is_public_http_url_non_http() -> None:
    assert BP._is_public_http_url("ftp://files.example.com") is False


def test_bp_is_public_http_url_empty() -> None:
    assert BP._is_public_http_url("") is False


def test_bp_is_public_http_url_none() -> None:
    assert BP._is_public_http_url(None) is False


# ─── _compact_cik ────────────────────────────────────────────────────────────

def test_bp_compact_cik_pads_to_10() -> None:
    result = BP._compact_cik("12345")
    assert len(result) == 10
    assert result == "0000012345"


def test_bp_compact_cik_strips_non_digits() -> None:
    result = BP._compact_cik("CIK-0001234567")
    assert result.isdigit()


def test_bp_compact_cik_empty_returns_empty() -> None:
    assert BP._compact_cik("") == ""
    assert BP._compact_cik(None) == ""


# ─── _bounded_page_size ──────────────────────────────────────────────────────

def test_bp_bounded_page_size_default() -> None:
    assert BP._bounded_page_size(None) == 100


def test_bp_bounded_page_size_capped_at_1000() -> None:
    assert BP._bounded_page_size(5000) == 1000


def test_bp_bounded_page_size_zero_treated_as_default() -> None:
    # 0 is falsy, so `0 or 100` = 100 — clamped to default
    assert BP._bounded_page_size(0) == 100


def test_bp_bounded_page_size_normal_value() -> None:
    assert BP._bounded_page_size(50) == 50


# ─── _with_query ─────────────────────────────────────────────────────────────

def test_bp_with_query_adds_param() -> None:
    result = BP._with_query("https://api.example.com/search", q="hello")
    assert "q=hello" in result


def test_bp_with_query_merges_existing_params() -> None:
    result = BP._with_query("https://api.example.com/?page=1", limit=10)
    assert "page=1" in result
    assert "limit=10" in result


def test_bp_with_query_none_value_not_added() -> None:
    result = BP._with_query("https://example.com/", q=None)
    assert "q=" not in result


def test_bp_with_query_preserves_base_url() -> None:
    result = BP._with_query("https://api.example.com/path", q="test")
    assert result.startswith("https://api.example.com/path")


# ─── _first_text ─────────────────────────────────────────────────────────────

def test_first_text_returns_first_non_empty() -> None:
    rec = {"a": "", "b": "hello", "c": "world"}
    assert BP._first_text(rec, "a", "b", "c") == "hello"


def test_first_text_returns_empty_when_all_missing() -> None:
    assert BP._first_text({}, "x", "y") == ""


def test_first_text_skips_none_values() -> None:
    rec = {"a": None, "b": "found"}
    assert BP._first_text(rec, "a", "b") == "found"


def test_first_text_single_key_match() -> None:
    assert BP._first_text({"name": "Alice"}, "name") == "Alice"


def test_first_text_strips_whitespace() -> None:
    rec = {"name": "  Bob  "}
    assert BP._first_text(rec, "name") == "Bob"


# ─── _first_nested_text ──────────────────────────────────────────────────────

def test_first_nested_text_simple_path() -> None:
    rec = {"org": {"name": "Acme"}}
    assert BP._first_nested_text(rec, "org.name") == "Acme"


def test_first_nested_text_fallback_path() -> None:
    rec = {"org": {"name": ""}, "company": "Globex"}
    assert BP._first_nested_text(rec, "org.name", "company") == "Globex"


def test_first_nested_text_missing_path_returns_empty() -> None:
    assert BP._first_nested_text({}, "a.b.c") == ""


def test_first_nested_text_non_dict_intermediate_returns_empty() -> None:
    rec = {"org": "not-a-dict"}
    assert BP._first_nested_text(rec, "org.name") == ""


def test_first_nested_text_deep_path() -> None:
    rec = {"a": {"b": {"c": "deep"}}}
    assert BP._first_nested_text(rec, "a.b.c") == "deep"


# ─── _assign_faction ─────────────────────────────────────────────────────────

def test_assign_faction_softbank() -> None:
    assert BP._assign_faction({"org_name": "SoftBank Group"}) == "SoftBank派"


def test_assign_faction_kddi() -> None:
    assert BP._assign_faction({"org_name": "KDDI Corporation"}) == "KDDI派"


def test_assign_faction_au_brand() -> None:
    assert BP._assign_faction({"org_name": "au by KDDI"}) == "KDDI派"


def test_assign_faction_ntt() -> None:
    assert BP._assign_faction({"org_name": "NTT Communications"}) == "NTT派"


def test_assign_faction_docomo() -> None:
    assert BP._assign_faction({"org_name": "NTT docomo"}) == "NTT派"


def test_assign_faction_high_bridge_score() -> None:
    person = {"org_name": "Unknown Co", "hub_score": 1, "bridge_score": 3}
    assert BP._assign_faction(person) == "cross-industry-bridge"


def test_assign_faction_high_hub_score() -> None:
    person = {"org_name": "Unknown Co", "hub_score": 5, "bridge_score": 0}
    assert BP._assign_faction(person) == "hub-high"


def test_assign_faction_independent() -> None:
    person = {"org_name": "Unknown Co", "hub_score": 0, "bridge_score": 0}
    assert BP._assign_faction(person) == "independent"


def test_assign_faction_empty_dict_returns_independent() -> None:
    assert BP._assign_faction({}) == "independent"


# ─── _news_url_for_person ────────────────────────────────────────────────────

def test_news_url_for_person_returns_url() -> None:
    url = BP._news_url_for_person("山田太郎", "トヨタ自動車")
    assert url.startswith("https://news.google.com/")


def test_news_url_for_person_contains_encoded_name() -> None:
    url = BP._news_url_for_person("田中一郎", "ソニー")
    assert "%" in url  # URL-encoded Japanese chars


def test_news_url_for_person_empty_inputs_ok() -> None:
    url = BP._news_url_for_person("", "")
    assert url.startswith("https://")


def test_news_url_for_person_deterministic() -> None:
    a = BP._news_url_for_person("名前", "会社")
    b = BP._news_url_for_person("名前", "会社")
    assert a == b


# ─── _news_url_for_pair ──────────────────────────────────────────────────────

def test_news_url_for_pair_returns_rss_url() -> None:
    url = BP._news_url_for_pair("鈴木", "田中")
    assert "news.google.com" in url


def test_news_url_for_pair_includes_both_names() -> None:
    url = BP._news_url_for_pair("鈴木", "田中")
    assert "鈴木" in url or "%E9%88%B4%E6%9C%A8" in url  # encoded or literal


def test_news_url_for_pair_with_orgs_includes_org_filter() -> None:
    url = BP._news_url_for_pair("A", "B", org1="Toyota", org2="Honda")
    assert "Toyota" in url or "OR" in url


def test_news_url_for_pair_without_orgs_no_or_clause() -> None:
    url = BP._news_url_for_pair("A", "B")
    assert "OR" not in url


def test_news_url_for_pair_deterministic() -> None:
    a = BP._news_url_for_pair("X", "Y", org1="Org1")
    b = BP._news_url_for_pair("X", "Y", org1="Org1")
    assert a == b


# ─── _role_from_row ──────────────────────────────────────────────────────────

def _make_role_row(**kwargs: object) -> dict:
    base: dict = {
        "fullName": "Tanaka Taro",
        "orgName": "Acme Corp",
        "title": "CEO",
    }
    base.update(kwargs)
    return base


def test_role_from_row_returns_dict() -> None:
    result = BP._role_from_row(
        _make_role_row(),
        source_id="gleif",
        source_url="https://example.com",
        jurisdiction="JPN",
    )
    assert isinstance(result, dict)


def test_role_from_row_vertex_id_starts_with_at() -> None:
    result = BP._role_from_row(
        _make_role_row(),
        source_id="gleif",
        source_url="https://example.com",
        jurisdiction="JPN",
    )
    assert result["vertex_id"].startswith("at://")


def test_role_from_row_display_name_set() -> None:
    result = BP._role_from_row(
        _make_role_row(fullName="Yamada Hanako"),
        source_id="gleif",
        source_url="",
        jurisdiction="JPN",
    )
    assert result["display_name"] == "Yamada Hanako"


def test_role_from_row_falls_back_to_display_name_key() -> None:
    row = {"displayName": "Bob Smith", "orgName": "Corp"}
    result = BP._role_from_row(
        row,
        source_id="edgar",
        source_url="",
        jurisdiction="USA",
    )
    assert result["display_name"] == "Bob Smith"


def test_role_from_row_title_field() -> None:
    result = BP._role_from_row(
        _make_role_row(title="CFO"),
        source_id="gleif",
        source_url="",
        jurisdiction="DEU",
    )
    assert result["title"] == "CFO"


def test_role_from_row_country_lowercased() -> None:
    result = BP._role_from_row(
        _make_role_row(),
        source_id="gleif",
        source_url="",
        jurisdiction="JPN",
    )
    assert result["country"] == "jpn"


def test_role_from_row_uses_jurisdiction_when_no_country_in_row() -> None:
    row = {"fullName": "Alice"}
    result = BP._role_from_row(
        row,
        source_id="gleif",
        source_url="",
        jurisdiction="GBR",
    )
    assert result["country"] == "gbr"


def test_role_from_row_deterministic() -> None:
    row = _make_role_row()
    a = BP._role_from_row(row, source_id="gleif", source_url="https://x.com", jurisdiction="JPN")
    b = BP._role_from_row(row, source_id="gleif", source_url="https://x.com", jurisdiction="JPN")
    assert a["vertex_id"] == b["vertex_id"]


def test_role_from_row_org_name_field() -> None:
    result = BP._role_from_row(
        _make_role_row(orgName="Toyota Motor"),
        source_id="gleif",
        source_url="",
        jurisdiction="JPN",
    )
    assert result["org_name"] == "Toyota Motor"


# ─── _fetch_headers_for_source ────────────────────────────────────────────────

import os as _os


def test_fetch_headers_returns_dict() -> None:
    result = BP._fetch_headers_for_source("gleif")
    assert isinstance(result, dict)


def test_fetch_headers_always_has_user_agent() -> None:
    result = BP._fetch_headers_for_source("gleif")
    assert "User-Agent" in result


def test_fetch_headers_sec_edgar_uses_sec_agent(monkeypatch) -> None:
    monkeypatch.setenv("SEC_USER_AGENT", "MyBot/1.0 admin@example.com")
    result = BP._fetch_headers_for_source("sec-edgar")
    assert result["User-Agent"] == "MyBot/1.0 admin@example.com"


def test_fetch_headers_gbizinfo_adds_token_when_set(monkeypatch) -> None:
    monkeypatch.setenv("GBIZINFO_API_TOKEN", "test-token-abc")
    result = BP._fetch_headers_for_source("gbizinfo")
    assert result.get("X-hojinInfo-api-token") == "test-token-abc"


def test_fetch_headers_gbizinfo_no_token_key_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("GBIZINFO_API_TOKEN", raising=False)
    monkeypatch.delenv("G_BIZINFO_API_TOKEN", raising=False)
    result = BP._fetch_headers_for_source("gbizinfo")
    assert "X-hojinInfo-api-token" not in result


def test_fetch_headers_unknown_source_returns_basic_headers() -> None:
    result = BP._fetch_headers_for_source("unknown-source")
    assert "User-Agent" in result
    assert len(result) == 1  # only User-Agent for unknown sources


def test_fetch_headers_env_override_user_agent(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESS_PERSON_FETCH_USER_AGENT", "CustomAgent/2.0")
    result = BP._fetch_headers_for_source("gleif")
    assert result["User-Agent"] == "CustomAgent/2.0"


# ─── _handelsregister_records ────────────────────────────────────────────────

def test_handelsregister_records_items_key() -> None:
    payload = {"items": [{"name": "Alice"}, {"name": "Bob"}]}
    result = BP._handelsregister_records(payload)
    assert len(result) == 2
    assert result[0]["name"] == "Alice"


def test_handelsregister_records_officers_key() -> None:
    payload = {"officers": [{"name": "CEO"}, {"name": "CFO"}]}
    result = BP._handelsregister_records(payload)
    assert len(result) == 2


def test_handelsregister_records_list_input() -> None:
    payload = [{"name": "X"}, {"name": "Y"}, "skip-me"]
    result = BP._handelsregister_records(payload)
    assert len(result) == 2


def test_handelsregister_records_bare_dict_wraps_in_list() -> None:
    payload = {"name": "Sole Person", "title": "Director"}
    result = BP._handelsregister_records(payload)
    assert len(result) == 1
    assert result[0]["name"] == "Sole Person"


def test_handelsregister_records_json_string_input() -> None:
    import json
    payload = json.dumps({"results": [{"name": "Alice"}]})
    result = BP._handelsregister_records(payload)
    assert len(result) == 1


def test_handelsregister_records_empty_dict_returns_singleton() -> None:
    result = BP._handelsregister_records({})
    assert result == [{}]


def test_handelsregister_records_empty_list_returns_empty() -> None:
    result = BP._handelsregister_records([])
    assert result == []


def test_handelsregister_records_none_returns_empty() -> None:
    result = BP._handelsregister_records(None)
    assert result == []


def test_handelsregister_records_persons_key() -> None:
    payload = {"persons": [{"name": "Tanaka"}, {"name": "Yamada"}]}
    result = BP._handelsregister_records(payload)
    assert len(result) == 2


def test_handelsregister_records_dict_value_wrapped() -> None:
    payload = {"entries": {"name": "Single Dict Entry"}}
    result = BP._handelsregister_records(payload)
    assert len(result) == 1
    assert result[0]["name"] == "Single Dict Entry"


# ─── _person_rows_from_companies_house ───────────────────────────────────────

def _ch_kwargs(**extra) -> dict:
    base: dict = {
        "source_url": "https://api.company-information.service.gov.uk/company/12345678/officers",
        "jurisdiction": "GBR",
        "fallback_org_name": "Acme Ltd",
        "company_number": "12345678",
        "limit": 50,
    }
    base.update(extra)
    return base


def test_person_rows_from_companies_house_happy_path() -> None:
    payload = {"items": [
        {"name": "SMITH, John", "officer_role": "director", "appointed_on": "2020-01-01"}
    ]}
    rows = BP._person_rows_from_companies_house(payload, **_ch_kwargs())
    assert len(rows) == 1
    assert "SMITH" in str(rows[0])


def test_person_rows_from_companies_house_empty_items_returns_empty() -> None:
    rows = BP._person_rows_from_companies_house({"items": []}, **_ch_kwargs())
    assert rows == []


def test_person_rows_from_companies_house_no_name_skipped() -> None:
    payload = {"items": [{"officer_role": "director", "appointed_on": "2020-01-01"}]}
    rows = BP._person_rows_from_companies_house(payload, **_ch_kwargs())
    assert rows == []


def test_person_rows_from_companies_house_returns_list() -> None:
    rows = BP._person_rows_from_companies_house({}, **_ch_kwargs())
    assert isinstance(rows, list)


def test_person_rows_from_companies_house_respects_limit() -> None:
    payload = {"items": [{"name": f"Officer {i}", "officer_role": "director"} for i in range(20)]}
    rows = BP._person_rows_from_companies_house(payload, **_ch_kwargs(limit=5))
    assert len(rows) <= 5


# ─── _person_rows_from_gbizinfo ──────────────────────────────────────────────

def _gbiz_kwargs(**extra) -> dict:
    base: dict = {
        "source_url": "https://info.gbiz.go.jp/hojin/v1/hojin/1234567890123",
        "jurisdiction": "JPN",
        "fallback_org_name": "株式会社テスト",
        "limit": 50,
    }
    base.update(extra)
    return base


def test_person_rows_from_gbizinfo_happy_path() -> None:
    payload = {"representativeName": "田中太郎", "name": "株式会社サンプル",
               "representativePosition": "代表取締役"}
    rows = BP._person_rows_from_gbizinfo(payload, **_gbiz_kwargs())
    assert len(rows) == 1
    assert "田中太郎" in str(rows[0])


def test_person_rows_from_gbizinfo_no_rep_name_skipped() -> None:
    payload = {"name": "株式会社テスト"}
    rows = BP._person_rows_from_gbizinfo(payload, **_gbiz_kwargs())
    assert rows == []


def test_person_rows_from_gbizinfo_empty_returns_empty() -> None:
    rows = BP._person_rows_from_gbizinfo({}, **_gbiz_kwargs())
    assert rows == []


def test_person_rows_from_gbizinfo_list_payload() -> None:
    payload = [
        {"representativeName": "山田花子", "name": "会社A"},
        {"representativeName": "佐藤次郎", "name": "会社B"},
    ]
    rows = BP._person_rows_from_gbizinfo(payload, **_gbiz_kwargs())
    assert len(rows) == 2


# ─── _person_rows_from_sec_edgar ─────────────────────────────────────────────

def _edgar_kwargs(**extra) -> dict:
    base: dict = {
        "source_url": "https://data.sec.gov/submissions/CIK0000012345.json",
        "jurisdiction": "USA",
        "fallback_org_name": "Acme Corp Inc",
        "cik": "0000012345",
        "limit": 50,
    }
    base.update(extra)
    return base


def test_person_rows_from_sec_edgar_happy_path() -> None:
    payload = {"items": [{"name": "Jane Doe", "officerTitle": "CEO", "issuerName": "Acme Corp"}]}
    rows = BP._person_rows_from_sec_edgar(payload, **_edgar_kwargs())
    assert len(rows) == 1
    assert "Jane Doe" in str(rows[0])


def test_person_rows_from_sec_edgar_no_name_skipped() -> None:
    payload = {"items": [{"officerTitle": "CFO"}]}
    rows = BP._person_rows_from_sec_edgar(payload, **_edgar_kwargs())
    assert rows == []


def test_person_rows_from_sec_edgar_empty_returns_empty() -> None:
    rows = BP._person_rows_from_sec_edgar({}, **_edgar_kwargs())
    assert rows == []


# ─── _person_rows_from_handelsregister ───────────────────────────────────────

def _hr_kwargs(**extra) -> dict:
    base: dict = {
        "source_url": "https://www.handelsregister.de/rp_web/ergebnisse.xhtml",
        "jurisdiction": "DEU",
        "fallback_org_name": "GmbH Example",
        "register_number": "HRB 12345",
        "limit": 50,
    }
    base.update(extra)
    return base


def test_person_rows_from_handelsregister_happy_path() -> None:
    payload = {"items": [{"name": "Müller, Hans", "role": "Geschäftsführer"}]}
    rows = BP._person_rows_from_handelsregister(payload, **_hr_kwargs())
    assert len(rows) == 1
    assert "Müller" in str(rows[0])


def test_person_rows_from_handelsregister_no_name_skipped() -> None:
    payload = {"items": [{"role": "Geschäftsführer"}]}
    rows = BP._person_rows_from_handelsregister(payload, **_hr_kwargs())
    assert rows == []


def test_person_rows_from_handelsregister_empty_returns_empty() -> None:
    rows = BP._person_rows_from_handelsregister({}, **_hr_kwargs())
    assert rows == []


def test_person_rows_from_handelsregister_managing_director_title() -> None:
    payload = {"items": [{"geschaeftsfuehrer": "Schmidt GmbH", "name": "Schmidt, Hans"}]}
    rows = BP._person_rows_from_handelsregister(payload, **_hr_kwargs())
    assert len(rows) == 1


# ─── _person_rows_from_text ──────────────────────────────────────────────────

def _text_kwargs(**extra) -> dict:
    base: dict = {
        "source_url": "https://example.com/about",
        "jurisdiction": "USA",
        "fallback_org_name": "Acme Corp",
        "limit": 50,
    }
    base.update(extra)
    return base


def test_person_rows_from_text_parses_name_title() -> None:
    text = "John Smith - Chief Executive Officer\nJane Doe - Chief Financial Officer\n"
    rows = BP._person_rows_from_text(text, **_text_kwargs())
    assert len(rows) == 2
    names = [r["fullName"] for r in rows]
    assert "John Smith" in names


def test_person_rows_from_text_empty_returns_empty() -> None:
    rows = BP._person_rows_from_text("", **_text_kwargs())
    assert rows == []


def test_person_rows_from_text_no_matching_lines_returns_empty() -> None:
    text = "Some random text\nwith no names or titles\n"
    rows = BP._person_rows_from_text(text, **_text_kwargs())
    assert rows == []


def test_person_rows_from_text_deduplicates_same_name_title() -> None:
    text = "John Smith - CEO\nJohn Smith - CEO\n"
    rows = BP._person_rows_from_text(text, **_text_kwargs())
    assert len(rows) == 1


def test_person_rows_from_text_respects_limit() -> None:
    lines = "\n".join(f"Person{i:02d} Name - Director Role" for i in range(20))
    rows = BP._person_rows_from_text(lines, **_text_kwargs(limit=5))
    assert len(rows) <= 5


def test_person_rows_from_text_sets_org_name() -> None:
    text = "Alice Brown - President\n"
    rows = BP._person_rows_from_text(text, **_text_kwargs(fallback_org_name="MyCompany"))
    if rows:
        assert rows[0]["orgName"] == "MyCompany"


# ─── _person_rows_from_edinet ────────────────────────────────────────────────

def _edinet_kwargs(**extra) -> dict:
    base: dict = {
        "source_url": "https://disclosure.edinet-fsa.go.jp/api/v2/documents.json",
        "jurisdiction": "JPN",
        "fallback_org_name": "株式会社サンプル",
        "limit": 50,
    }
    base.update(extra)
    return base


def test_person_rows_from_edinet_happy_path() -> None:
    payload = [{"representativeName": "鈴木一郎", "filerName": "株式会社テスト",
                "title": "代表取締役"}]
    rows = BP._person_rows_from_edinet(payload, **_edinet_kwargs())
    assert len(rows) == 1
    assert "鈴木一郎" in str(rows[0])


def test_person_rows_from_edinet_no_name_skipped() -> None:
    payload = [{"filerName": "株式会社テスト"}]
    rows = BP._person_rows_from_edinet(payload, **_edinet_kwargs())
    assert rows == []


def test_person_rows_from_edinet_empty_returns_empty() -> None:
    rows = BP._person_rows_from_edinet([], **_edinet_kwargs())
    assert rows == []


def test_person_rows_from_edinet_returns_list() -> None:
    rows = BP._person_rows_from_edinet({}, **_edinet_kwargs())
    assert isinstance(rows, list)


# ─── _insert_ignore / _update_by_pk (cursor-accepting) ───────────────────────

class _FakeCursorBP:
    def __init__(self, rowcount: int = 1) -> None:
        self.rowcount = rowcount
        self.last_sql: str = ""
        self.last_params: tuple = ()

    def execute(self, sql: str, params: tuple) -> None:
        self.last_sql = sql
        self.last_params = params


def test_insert_ignore_executes_select_not_exists() -> None:
    cur = _FakeCursorBP()
    BP._insert_ignore(cur, "vertex_person", "vertex_id", {
        "vertex_id": "at://did/col/rkey",
        "name": "Alice",
    })
    assert "WHERE NOT EXISTS" in cur.last_sql
    assert "vertex_person" in cur.last_sql


def test_insert_ignore_returns_rowcount() -> None:
    cur = _FakeCursorBP(rowcount=1)
    result = BP._insert_ignore(cur, "vertex_person", "vertex_id", {
        "vertex_id": "at://did/col/rkey", "name": "Bob",
    })
    assert result == 1


def test_insert_ignore_filters_none_values() -> None:
    cur = _FakeCursorBP()
    BP._insert_ignore(cur, "vertex_person", "vertex_id", {
        "vertex_id": "at://x", "name": None, "title": "CEO",
    })
    # None values should be filtered out; 'name' not in SQL
    assert "name" not in cur.last_sql


def test_update_by_pk_returns_zero_when_no_non_pk_values() -> None:
    cur = _FakeCursorBP()
    result = BP._update_by_pk(cur, "vertex_person", "vertex_id", {
        "vertex_id": "at://x",
        "_seq": 1,
        "created_date": "2024-01-01",
    })
    assert result == 0


def test_update_by_pk_builds_set_clause() -> None:
    cur = _FakeCursorBP(rowcount=1)
    result = BP._update_by_pk(cur, "vertex_person", "vertex_id", {
        "vertex_id": "at://x", "display_name": "Alice Updated",
    })
    assert "UPDATE vertex_person SET" in cur.last_sql
    assert "display_name" in cur.last_sql
    assert result == 1


def test_update_by_pk_filters_none_non_pk_values() -> None:
    cur = _FakeCursorBP()
    result = BP._update_by_pk(cur, "vertex_person", "vertex_id", {
        "vertex_id": "at://x", "display_name": None,
    })
    # Only None non-pk values; nothing to update
    assert result == 0
