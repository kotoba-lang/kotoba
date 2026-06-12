"""
Wikidata entity claims UDF (ADR-0049 Phase C).

Replaces the Wikidata `wbgetentities` batch fetch in
`70-tools/scripts/media_gamers_enrich_sources.py` which does per-QID
claim extraction for game titles (IGDB id P5794, Steam AppID P1733,
official URL P856, publication date P577).

SQL usage
---------

    SELECT
      vertex_id,
      wikidata_entity_claims(substring(vertex_id FROM 'did:wikidata:(Q[0-9]+)')) AS claims
    FROM vertex_game_title
    WHERE vertex_id LIKE 'did:wikidata:Q%'
      AND release_year IS NULL
    LIMIT 1000;

Surface
-------

    com.etzhayyim.apps.wikidata.entityClaims(qid)    VARCHAR → VARCHAR

Input: `qid` = a Wikidata Q-identifier (`"Q10757"`).
Output: JSON object string:
    {
      "qid":              "Q10757",
      "igdbIds":          ["..."],      // P5794 values
      "steamAppIds":      ["..."],      // P1733
      "officialUrls":     ["..."],      // P856
      "publicationDate":  "2011-08-03",  // P577 best (earliest) or null
      "publicationYear":  2011,
      "error":            null
    }

Never raises. Transport error → `{"qid": qid, "error": "fetch failed"}`.
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import logging
import re as _re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from kotodama import udf

log = logging.getLogger(__name__)

_WBG_URL = "https://www.wikidata.org/w/api.php"
_TIMEOUT_SEC = 20
_UA = "etzhayyim-wikidata-udf/1.0 (ops@etzhayyim.com)"
_QID_RE = _re.compile(r"^Q\d+$")
# "+2011-08-03T00:00:00Z" — Wikidata's canonical time format
_TIME_RE = _re.compile(r"^\+?(\d{1,9})-(\d{2})-(\d{2})T")


def _fetch_entity(qid: str) -> dict[str, Any] | None:
    """One wbgetentities call. Returns the entity dict or None on failure."""
    params = urllib.parse.urlencode({
        "action": "wbgetentities",
        "format": "json",
        "props": "claims",
        "ids": qid,
    })
    url = f"{_WBG_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
            if resp.status != 200:
                return None
            raw = resp.read(4 * 1024 * 1024)  # 4 MB ceiling — a single entity's claims
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    try:
        body = _json.loads(raw.decode("utf-8"))
    except (_json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    entities = body.get("entities") if isinstance(body.get("entities"), dict) else None
    if not isinstance(entities, dict):
        return None
    ent = entities.get(qid)
    return ent if isinstance(ent, dict) else None


def _claim_string_values(entity: dict[str, Any], prop: str) -> list[str]:
    """Extract string / entity-id values from a property's claim list.
    Mirrors `first_claim_values` in the legacy script but only keeps
    JSON-serialisable scalars (no dicts, no NaN)."""
    out: list[str] = []
    seen: set[str] = set()
    claims = (entity.get("claims") or {}).get(prop)
    if not isinstance(claims, list):
        return out
    for c in claims:
        if not isinstance(c, dict):
            continue
        dv = c.get("mainsnak", {}).get("datavalue") if isinstance(c.get("mainsnak"), dict) else None
        if not isinstance(dv, dict):
            continue
        v = dv.get("value")
        val: str | None = None
        if isinstance(v, str):
            val = v
        elif isinstance(v, dict):
            if isinstance(v.get("id"), str):
                val = v["id"]
            elif "numeric-id" in v:
                try:
                    val = str(v["numeric-id"])
                except Exception:  # noqa: BLE001
                    val = None
        elif isinstance(v, (int, float)):
            val = str(v)
        if val and val not in seen:
            seen.add(val)
            out.append(val)
    return out


def _best_publication_date(entity: dict[str, Any]) -> tuple[str | None, int | None]:
    """Earliest P577 date as (iso-string, year). The 'best' (earliest) pick
    mirrors the legacy script's `best_p577`."""
    claims = (entity.get("claims") or {}).get("P577")
    if not isinstance(claims, list):
        return None, None
    best_date: _dt.date | None = None
    for c in claims:
        if not isinstance(c, dict):
            continue
        dv = c.get("mainsnak", {}).get("datavalue") if isinstance(c.get("mainsnak"), dict) else None
        if not isinstance(dv, dict):
            continue
        val = dv.get("value") if isinstance(dv.get("value"), dict) else None
        if not isinstance(val, dict):
            continue
        m = _TIME_RE.match(str(val.get("time") or ""))
        if not m:
            continue
        try:
            y, mo, d = int(m.group(1)), max(1, int(m.group(2))), max(1, int(m.group(3)))
            if y <= 0 or y > 9999:
                continue
            cand = _dt.date(y, mo, d)
        except ValueError:
            continue
        if best_date is None or cand < best_date:
            best_date = cand
    if best_date is None:
        return None, None
    return best_date.isoformat(), best_date.year


@udf(
    nsid="com.etzhayyim.apps.wikidata.entityClaims",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("wikidata", "media-gamers", "enrich"),
    agent_tool="Fetch a Wikidata entity's IGDB / Steam / official-site / P577 claims; returns JSON.",
)
def entity_claims(qid: str) -> str:
    """Extract the claims the media_gamers enrichment script cared about
    (IGDB id, Steam app id, official URL, earliest publication date).
    Empty / malformed qid → envelope with `error`."""
    if not qid or not _QID_RE.match(qid):
        return _json.dumps({"qid": qid, "error": "invalid qid", "igdbIds": [],
                            "steamAppIds": [], "officialUrls": [],
                            "publicationDate": None, "publicationYear": None})
    ent = _fetch_entity(qid)
    if ent is None:
        return _json.dumps({"qid": qid, "error": "fetch failed", "igdbIds": [],
                            "steamAppIds": [], "officialUrls": [],
                            "publicationDate": None, "publicationYear": None})
    pub_date, pub_year = _best_publication_date(ent)
    return _json.dumps({
        "qid": qid,
        "igdbIds": _claim_string_values(ent, "P5794"),
        "steamAppIds": _claim_string_values(ent, "P1733"),
        "officialUrls": _claim_string_values(ent, "P856"),
        "publicationDate": pub_date,
        "publicationYear": pub_year,
        "error": None,
    }, ensure_ascii=False)
