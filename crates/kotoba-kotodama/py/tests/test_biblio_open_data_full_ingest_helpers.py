from __future__ import annotations

import json
import urllib.parse

from kotodama.primitives import biblio_open_data as biblio


def test_static_catalog_crawl_emits_internal_links(monkeypatch):
    html = b"""
    <html>
      <head><title>Catalog Home</title></head>
      <body>
        <a href="/catalog/one">First record</a>
        <a href="https://crlindia.gov.in/catalog/two">Second record</a>
        <a href="https://elsewhere.example/skip">External</a>
      </body>
    </html>
    """

    monkeypatch.setattr(biblio, "_source_by_id", lambda _source_id: {
        "api_base_url": "https://crlindia.gov.in/",
        "service_name": "CRL",
    })
    monkeypatch.setattr(biblio, "_http_get", lambda *_args, **_kwargs: html)

    records = biblio._fetch_static_catalog_records("ind-crl-inb", 10)

    assert [record["_schema"] for record in records] == [
        "html-portal-root",
        "html-portal-link",
        "html-portal-link",
    ]
    assert records[1]["url"] == "https://crlindia.gov.in/catalog/one"
    assert records[2]["url"] == "https://crlindia.gov.in/catalog/two"


def test_koha_adapter_paginates_offsets_and_detail_records(monkeypatch):
    def fake_http_get(url: str, **_kwargs) -> bytes:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.path.endswith("opac-search.pl"):
            offset = query.get("offset", ["0"])[0]
            if offset == "0":
                return b'<a href="/cgi-bin/koha/opac-detail.pl?biblionumber=101">A</a>'
            return b'<a href="/cgi-bin/koha/opac-detail.pl?biblionumber=102">B</a>'
        bib = query["biblionumber"][0]
        return f"<html><title>Record {bib}</title><img src='/covers/{bib}.jpg'></html>".encode()

    monkeypatch.setattr(biblio, "_http_get", fake_http_get)

    records = biblio._fetch_koha_opac_records("ind-nli-opac", 51)

    assert [record["koha_biblionumber"] for record in records[:2]] == ["101", "102"]
    assert records[0]["imageUrls"] == ["https://nationallibraryopac.nvli.in/covers/101.jpg"]


def test_lod_adapter_uses_limit_offset(monkeypatch):
    seen_queries: list[str] = []

    def fake_http_get(url: str, **_kwargs) -> bytes:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["query"][0]
        seen_queries.append(query)
        if "OFFSET 0" in query:
            bindings = [
                {"s": {"value": "https://lod.nl.go.kr/book/1"}, "title": {"value": "One"}},
                {"s": {"value": "https://lod.nl.go.kr/book/2"}, "title": {"value": "Two"}},
            ]
        else:
            bindings = []
        return json.dumps({"results": {"bindings": bindings}}).encode()

    monkeypatch.setattr(biblio, "_http_get", fake_http_get)

    records = biblio._fetch_lod_records("kor-nlk-lod", 2)

    assert [record["title"] for record in records] == ["One", "Two"]
    assert "LIMIT 2 OFFSET 0" in seen_queries[0]


def test_assert_run_visible_polls_until_visible(monkeypatch):
    attempts = {"count": 0}

    def fake_execute_one(*_args, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return None
        return {"run_id": "run-1"}

    monkeypatch.setenv("BIBLIO_RUN_VISIBILITY_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("BIBLIO_RUN_VISIBILITY_POLL_SECONDS", "1")
    monkeypatch.setattr(biblio, "sa_execute_one", fake_execute_one)
    monkeypatch.setattr(biblio.time, "sleep", lambda _seconds: None)

    biblio._assert_run_visible("run-1")

    assert attempts["count"] == 3
