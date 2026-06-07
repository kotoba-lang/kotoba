"""Tests for additional pure helpers in business_person.py (JSON-LD, parsing, URL)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import business_person as BP


# ─── _today ──────────────────────────────────────────────────────────────────

def test_today_returns_string() -> None:
    assert isinstance(BP._today(), str)


def test_today_matches_date_format() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", BP._today())


def test_today_no_time_component() -> None:
    assert "T" not in BP._today()


# ─── _source_id ──────────────────────────────────────────────────────────────

def test_source_id_valid_known_source() -> None:
    result = BP._source_id("companies-house")
    assert result == "companies-house"


def test_source_id_unknown_returns_corporate_hp() -> None:
    assert BP._source_id("unknown-source") == "corporate-hp"


def test_source_id_none_returns_corporate_hp() -> None:
    assert BP._source_id(None) == "corporate-hp"


def test_source_id_empty_returns_corporate_hp() -> None:
    assert BP._source_id("") == "corporate-hp"


def test_source_id_gbizinfo() -> None:
    assert BP._source_id("gbizinfo") == "gbizinfo"


# ─── _source_request_url ─────────────────────────────────────────────────────

def test_source_request_url_uses_explicit_url() -> None:
    url = BP._source_request_url(
        source="companies-house",
        source_url="https://example.com/custom",
        company_number="12345",
        corporate_number="",
        doc_id="",
        cik="",
        register_number="",
    )
    assert url.startswith("https://example.com/custom")


def test_source_request_url_companies_house() -> None:
    url = BP._source_request_url(
        source="companies-house",
        source_url="",
        company_number="09876543",
        corporate_number="",
        doc_id="",
        cik="",
        register_number="",
    )
    assert "09876543" in url
    assert "company-information.service.gov.uk" in url


def test_source_request_url_sec_edgar() -> None:
    url = BP._source_request_url(
        source="sec-edgar",
        source_url="",
        company_number="",
        corporate_number="",
        doc_id="",
        cik="0001234567",
        register_number="",
    )
    assert "sec.gov" in url
    assert "CIK" in url


def test_source_request_url_no_params_returns_empty() -> None:
    url = BP._source_request_url(
        source="companies-house",
        source_url="",
        company_number="",
        corporate_number="",
        doc_id="",
        cik="",
        register_number="",
    )
    assert url == ""


# ─── _payload_target_for_source ──────────────────────────────────────────────

def test_payload_target_companies_house() -> None:
    key, body = BP._payload_target_for_source("companies-house", "application/json", {"items": []})
    assert key == "companiesHouseJson"


def test_payload_target_gbizinfo() -> None:
    key, _ = BP._payload_target_for_source("gbizinfo", "application/json", {})
    assert key == "gbizInfoJson"


def test_payload_target_sec_edgar() -> None:
    key, _ = BP._payload_target_for_source("sec-edgar", "application/json", {})
    assert key == "secEdgarJson"


def test_payload_target_html_content() -> None:
    key, _ = BP._payload_target_for_source("corporate-hp", "text/html", "<html><body>test</body></html>")
    assert key == "htmlText"


def test_payload_target_html_string_detection() -> None:
    key, _ = BP._payload_target_for_source("corporate-hp", "text/plain", "<html>test</html>")
    assert key == "htmlText"


def test_payload_target_plain_text() -> None:
    key, _ = BP._payload_target_for_source("corporate-hp", "text/plain", "some plain text")
    assert key == "text"


# ─── _next_page_for_source ───────────────────────────────────────────────────

def test_next_page_companies_house_has_more() -> None:
    body = {"total_results": 200, "start_index": 0, "items_per_page": 50}
    cursor, url = BP._next_page_for_source("companies-house", "https://api.example.com", body, 50)
    assert cursor == "50"
    assert "start_index=50" in url


def test_next_page_companies_house_at_end() -> None:
    body = {"total_results": 50, "start_index": 0, "items_per_page": 50}
    cursor, url = BP._next_page_for_source("companies-house", "https://api.example.com", body, 50)
    assert cursor == ""
    assert url == ""


def test_next_page_gbizinfo_with_token() -> None:
    body = {"nextPageToken": "token123", "items": []}
    cursor, url = BP._next_page_for_source("gbizinfo", "https://info.gbiz.go.jp", body, 50)
    assert cursor == "token123"
    assert "pageToken=token123" in url


def test_next_page_gbizinfo_no_token() -> None:
    body = {"items": []}
    cursor, url = BP._next_page_for_source("gbizinfo", "https://info.gbiz.go.jp", body, 50)
    assert cursor == ""
    assert url == ""


def test_next_page_non_dict_returns_empty() -> None:
    cursor, url = BP._next_page_for_source("companies-house", "https://api.example.com", [], 50)
    assert cursor == "" and url == ""


# ─── _flatten_jsonld ─────────────────────────────────────────────────────────

def test_flatten_jsonld_single_dict() -> None:
    node = {"@type": "Person", "name": "John"}
    result = BP._flatten_jsonld(node)
    assert node in result


def test_flatten_jsonld_list() -> None:
    nodes = [{"@type": "Person"}, {"@type": "Organization"}]
    result = BP._flatten_jsonld(nodes)
    assert len(result) >= 2


def test_flatten_jsonld_with_graph() -> None:
    doc = {"@context": "http://schema.org", "@graph": [{"@type": "Person", "name": "Alice"}]}
    result = BP._flatten_jsonld(doc)
    assert any(n.get("@type") == "Person" for n in result)


def test_flatten_jsonld_empty_list() -> None:
    assert BP._flatten_jsonld([]) == []


def test_flatten_jsonld_non_dict_non_list() -> None:
    assert BP._flatten_jsonld("not a dict") == []


# ─── _jsonld_nodes ───────────────────────────────────────────────────────────

def test_jsonld_nodes_extracts_from_script_tag() -> None:
    html = """<html><head>
    <script type="application/ld+json">{"@type": "Person", "name": "Test"}</script>
    </head></html>"""
    nodes = BP._jsonld_nodes(html)
    assert len(nodes) >= 1
    assert any(n.get("name") == "Test" for n in nodes)


def test_jsonld_nodes_empty_html() -> None:
    assert BP._jsonld_nodes("<html><body>no scripts</body></html>") == []


def test_jsonld_nodes_invalid_json_skipped() -> None:
    html = '<script type="application/ld+json">{invalid json}</script>'
    nodes = BP._jsonld_nodes(html)
    assert nodes == []


def test_jsonld_nodes_multiple_scripts() -> None:
    html = """
    <script type="application/ld+json">{"@type": "Person", "name": "A"}</script>
    <script type="application/ld+json">{"@type": "Organization", "name": "B"}</script>
    """
    nodes = BP._jsonld_nodes(html)
    assert len(nodes) >= 2


# ─── _node_type ──────────────────────────────────────────────────────────────

def test_node_type_string() -> None:
    types = BP._node_type({"@type": "Person"})
    assert "person" in types


def test_node_type_list() -> None:
    types = BP._node_type({"@type": ["Person", "Employee"]})
    assert "person" in types
    assert "employee" in types


def test_node_type_lowercase() -> None:
    types = BP._node_type({"@type": "Organization"})
    assert "organization" in types


def test_node_type_missing_returns_empty_set() -> None:
    types = BP._node_type({})
    assert types == set()


def test_node_type_uses_type_fallback() -> None:
    types = BP._node_type({"type": "Person"})
    assert "person" in types


# ─── _org_name ───────────────────────────────────────────────────────────────

def test_org_name_from_string() -> None:
    assert BP._org_name("Acme Corp") == "Acme Corp"


def test_org_name_from_dict_with_name() -> None:
    assert BP._org_name({"name": "Acme Corp"}) == "Acme Corp"


def test_org_name_from_list() -> None:
    result = BP._org_name([{"name": "First Corp"}, {"name": "Second Corp"}])
    assert result == "First Corp"


def test_org_name_none_returns_empty() -> None:
    assert BP._org_name(None) == ""


def test_org_name_empty_dict_returns_empty() -> None:
    assert BP._org_name({}) == ""


# ─── _person_row_from_jsonld ─────────────────────────────────────────────────

def test_person_row_from_jsonld_valid() -> None:
    node = {
        "@type": "Person",
        "name": "Alice Smith",
        "jobTitle": "CEO",
        "worksFor": {"name": "Acme Corp"},
    }
    row = BP._person_row_from_jsonld(node, source_url="https://example.com", jurisdiction="USA", fallback_org_name="")
    assert row is not None
    assert row["fullName"] == "Alice Smith"
    assert row["title"] == "CEO"
    assert row["orgName"] == "Acme Corp"


def test_person_row_from_jsonld_non_person_returns_none() -> None:
    node = {"@type": "Organization", "name": "Acme Corp"}
    result = BP._person_row_from_jsonld(node, source_url="", jurisdiction="", fallback_org_name="")
    assert result is None


def test_person_row_from_jsonld_missing_title_returns_none() -> None:
    node = {"@type": "Person", "name": "Bob"}
    result = BP._person_row_from_jsonld(node, source_url="", jurisdiction="", fallback_org_name="")
    assert result is None


def test_person_row_from_jsonld_uses_fallback_org() -> None:
    node = {"@type": "Person", "name": "Carol", "jobTitle": "CTO"}
    row = BP._person_row_from_jsonld(node, source_url="", jurisdiction="JPN", fallback_org_name="FallbackOrg")
    assert row is not None
    assert row["orgName"] == "FallbackOrg"


# ─── _strip_html ─────────────────────────────────────────────────────────────

def test_strip_html_removes_tags() -> None:
    result = BP._strip_html("<p>Hello <b>World</b></p>")
    assert "<p>" not in result
    assert "<b>" not in result
    assert "Hello" in result and "World" in result


def test_strip_html_removes_script() -> None:
    result = BP._strip_html("<script>alert('x')</script>")
    assert "alert" not in result


def test_strip_html_removes_style() -> None:
    result = BP._strip_html("<style>.foo{color:red}</style>text")
    assert ".foo" not in result
    assert "text" in result


def test_strip_html_unescape_entities() -> None:
    result = BP._strip_html("AT&amp;T")
    assert "AT&T" in result


def test_strip_html_empty_returns_empty() -> None:
    assert BP._strip_html("").strip() == ""


# ─── _looks_like_role ────────────────────────────────────────────────────────

def test_looks_like_role_ceo() -> None:
    assert BP._looks_like_role("Chief Executive Officer") is True


def test_looks_like_role_director() -> None:
    assert BP._looks_like_role("Executive Director of Finance") is True


def test_looks_like_role_random_text() -> None:
    assert BP._looks_like_role("The quick brown fox jumps") is False


def test_looks_like_role_president() -> None:
    assert BP._looks_like_role("Company President") is True


# ─── _companies_house_items ──────────────────────────────────────────────────

def test_companies_house_items_dict_with_items() -> None:
    payload = {"items": [{"name": "Alice"}, {"name": "Bob"}], "total_results": 2}
    result = BP._companies_house_items(payload)
    assert len(result) == 2
    assert result[0]["name"] == "Alice"


def test_companies_house_items_list() -> None:
    payload = [{"name": "Alice"}, {"name": "Bob"}]
    result = BP._companies_house_items(payload)
    assert len(result) == 2


def test_companies_house_items_empty_items() -> None:
    payload = {"items": [], "total_results": 0}
    result = BP._companies_house_items(payload)
    assert result == []


def test_companies_house_items_no_items_key() -> None:
    payload = {"total_results": 0}
    result = BP._companies_house_items(payload)
    assert result == []


def test_companies_house_items_none() -> None:
    result = BP._companies_house_items(None)
    assert result == []


# ─── _companies_house_role ───────────────────────────────────────────────────

def test_companies_house_role_director() -> None:
    result = BP._companies_house_role("director")
    assert "director" in result.lower()


def test_companies_house_role_with_dashes() -> None:
    result = BP._companies_house_role("llp-designated-member")
    assert "-" not in result


def test_companies_house_role_empty_returns_officer() -> None:
    assert BP._companies_house_role("") == "officer"
    assert BP._companies_house_role(None) == "officer"


# ─── _gbizinfo_records ───────────────────────────────────────────────────────

def test_gbizinfo_records_hojin_infos_key() -> None:
    payload = {"hojin-infos": [{"gbizid": "123"}, {"gbizid": "456"}]}
    result = BP._gbizinfo_records(payload)
    assert len(result) == 2


def test_gbizinfo_records_items_key() -> None:
    payload = {"items": [{"name": "Company A"}]}
    result = BP._gbizinfo_records(payload)
    assert len(result) == 1


def test_gbizinfo_records_list() -> None:
    payload = [{"gbizid": "1"}, {"gbizid": "2"}]
    result = BP._gbizinfo_records(payload)
    assert len(result) == 2


def test_gbizinfo_records_empty() -> None:
    result = BP._gbizinfo_records(None)
    assert result == []


# ─── _edinet_records ─────────────────────────────────────────────────────────

def test_edinet_records_results_key() -> None:
    payload = {"results": [{"docID": "S100X0001"}, {"docID": "S100X0002"}]}
    result = BP._edinet_records(payload)
    assert len(result) == 2


def test_edinet_records_list() -> None:
    payload = [{"docID": "S100X0001"}]
    result = BP._edinet_records(payload)
    assert len(result) == 1


def test_edinet_records_empty() -> None:
    result = BP._edinet_records(None)
    assert result == []


# ─── _sec_edgar_records ──────────────────────────────────────────────────────

def test_sec_edgar_records_officers_key() -> None:
    payload = {"officers": [{"name": "John Doe", "title": "CEO"}]}
    result = BP._sec_edgar_records(payload)
    assert any(r.get("name") == "John Doe" for r in result)


def test_sec_edgar_records_list() -> None:
    payload = [{"name": "Alice", "title": "CFO"}]
    result = BP._sec_edgar_records(payload)
    assert len(result) == 1


def test_sec_edgar_records_dict_without_officers_returns_dict() -> None:
    payload = {"companyName": "Acme Corp", "cik": "0001234567"}
    result = BP._sec_edgar_records(payload)
    assert len(result) >= 1


def test_sec_edgar_records_empty() -> None:
    result = BP._sec_edgar_records(None)
    assert result == []
