"""
GLEIF LEI lookup UDF (ADR-0049 Phase C).

Replaces the per-row `api.gleif.org/api/v1/lei-records?filter[entity.legalName]=...`
fetch loop in `70-tools/scripts/gleif-reconcile-repo-record.mjs` and
`70-tools/scripts/multi-country-direct-ingest.mjs`.

SQL usage
---------

    INSERT INTO vertex_legal_entity (vertex_id, lei, name, country, jurisdiction, ...)
    SELECT
      'at://did:web:legal-entity.etzhayyim.com/com.etzhayyim.apps.legalEntity.legalEntity/' || lower(m.lei) AS vertex_id,
      m.lei,
      m.legal_name,
      m.country,
      m.jurisdiction,
      ...
    FROM (
      SELECT
        v.vertex_id AS src_vertex_id,
        v.search_name,
        v.country_hint,
        gleif_lei_lookup(v.search_name, v.country_hint) AS payload
      FROM vertex_legal_entity_search_queue v
    ) s
    CROSS JOIN LATERAL jsonb_to_record(s.payload::jsonb)
      AS m(lei varchar, legal_name varchar, country varchar, jurisdiction varchar, ...)
    WHERE m.lei IS NOT NULL;

Surface
-------

    com.etzhayyim.apps.gleif.lookup(name, countryHint)     VARCHAR, VARCHAR → VARCHAR

Input: `name` = legal entity search term, `countryHint` = optional ISO-2
(`"US"`, `"JP"`, ...) that forces a best-match preference.

Output: single JSON object (string) with the best-match fields, or
`{"lei": null, "error": "..."}` envelope. Never raises — arrow-udf would
otherwise drop the whole row batch.

Behaviour (mirrors the BPMN `com.etzhayyim.apps.yabai.enrichLegalEntity` flow
so bulk ingest ≡ BPMN-triggered enrichment):

  - Empty `name` → `{"lei": null, "error": "name required"}`
  - GLEIF returns zero hits → `{"lei": null, "name": <input>, "hitCount": 0}`
  - Multiple hits + `countryHint` → pick first whose `legalAddress.country == hint`
  - Multiple hits + no hint → pick first
  - Transport error → `{"lei": null, "error": "fetch failed"}`

Throughput
----------

GLEIF is CloudFront-fronted, public, ~100-200ms per request. `io_threads=100`
lets ~100 concurrent lookups overlap per UDF replica; 3-replica steady-state
sustains ~3k concurrent at <1% of GLEIF's rate-limit ceiling (not advertised
but well beyond anything a single tenant would trigger).
"""

from __future__ import annotations

import json as _json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from kotodama import udf

log = logging.getLogger(__name__)

_GLEIF_URL = "https://api.gleif.org/api/v1/lei-records"
_TIMEOUT_SEC = 12
_UA = "etzhayyim-gleif-udf/1.0 (ops@etzhayyim.com)"
_PAGE_SIZE = 5  # match the legacy script; 5 is enough for country disambiguation


def _url_for(name: str) -> str:
    """URL-encode the `filter[entity.legalName]` param. `urlencode` handles
    spaces and `&` correctly; `page[size]` uses brackets that requests /
    CloudFront pass through unchanged."""
    q = urllib.parse.urlencode({"filter[entity.legalName]": name, "page[size]": _PAGE_SIZE})
    return f"{_GLEIF_URL}?{q}"


def _gleif_fetch(name: str) -> list[dict[str, Any]]:
    """One GLEIF GET. Returns a list of hits (possibly empty) or raises
    nothing — all failures collapse to an empty list with the caller
    distinguishing via `_last_error`."""
    req = urllib.request.Request(
        _url_for(name),
        headers={"Accept": "application/vnd.api+json", "User-Agent": _UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
            if resp.status != 200:
                return []
            raw = resp.read(2 * 1024 * 1024)  # 2 MB ceiling — GLEIF page[size]=5 < 10 KB typical
    except (urllib.error.URLError, OSError, TimeoutError):
        return []
    try:
        body = _json.loads(raw.decode("utf-8"))
    except (_json.JSONDecodeError, UnicodeDecodeError):
        return []
    hits = body.get("data") if isinstance(body, dict) else None
    return hits if isinstance(hits, list) else []


def _addr_line(addr: dict[str, Any] | None) -> str:
    if not isinstance(addr, dict):
        return ""
    parts: list[str] = []
    lines = addr.get("addressLines")
    if isinstance(lines, list):
        parts.append(" ".join(str(x) for x in lines if x))
    for key in ("city", "region", "postalCode", "country"):
        v = addr.get(key)
        if isinstance(v, str) and v:
            parts.append(v)
    return ", ".join(p for p in parts if p)


def _flatten_hit(hit: dict[str, Any]) -> dict[str, Any]:
    """Flatten a GLEIF `data[*]` entry into the caller-friendly shape.
    Returns {} for malformed entries; the caller checks `lei is None`."""
    if not isinstance(hit, dict):
        return {}
    attrs = hit.get("attributes") if isinstance(hit.get("attributes"), dict) else {}
    entity = attrs.get("entity") if isinstance(attrs.get("entity"), dict) else {}
    legal_addr = entity.get("legalAddress") if isinstance(entity.get("legalAddress"), dict) else {}
    legal_name = entity.get("legalName") if isinstance(entity.get("legalName"), dict) else {}
    creation = entity.get("creationDate")
    return {
        "lei": hit.get("id") or None,
        "legalName": legal_name.get("name"),
        "country": legal_addr.get("country"),
        "jurisdiction": entity.get("jurisdiction"),
        "registrationNumber": entity.get("registeredAs"),
        "status": entity.get("status"),
        "incorporationDate": creation[:10] if isinstance(creation, str) else None,
        "address": _addr_line(legal_addr),
    }


def _pick_best(hits: list[dict[str, Any]], country_hint: str) -> dict[str, Any]:
    """Apply the country-hint fallback used by enrichLegalEntity.bpmn:
    prefer the first hit whose legalAddress.country == hint, else first hit."""
    if not hits:
        return {}
    if country_hint:
        hint = country_hint.upper().strip()
        for hit in hits:
            attrs = hit.get("attributes") if isinstance(hit, dict) else None
            if not isinstance(attrs, dict):
                continue
            entity = attrs.get("entity") if isinstance(attrs.get("entity"), dict) else {}
            legal_addr = entity.get("legalAddress") if isinstance(entity.get("legalAddress"), dict) else {}
            if (legal_addr.get("country") or "").upper() == hint:
                return _flatten_hit(hit)
    return _flatten_hit(hits[0])


@udf(
    nsid="com.etzhayyim.apps.gleif.lookup",
    io_threads=100,
    input_types=["VARCHAR", "VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("gleif", "legal-entity", "lei"),
    agent_tool="Look up a legal entity by name in GLEIF; returns JSON with LEI + core fields.",
)
def lookup(name: str, country_hint: str) -> str:
    """Single best GLEIF match as JSON. Empty name / zero hits → envelope
    with `lei: null`. Never raises."""
    if not name:
        return _json.dumps({"lei": None, "error": "name required"})
    hits = _gleif_fetch(name.strip())
    if not hits:
        return _json.dumps({"lei": None, "name": name, "hitCount": 0})
    best = _pick_best(hits, country_hint or "")
    best["hitCount"] = len(hits)
    best["name"] = name
    return _json.dumps(best, ensure_ascii=False)
