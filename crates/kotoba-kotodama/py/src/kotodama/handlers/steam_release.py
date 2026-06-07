"""
Steam appdetails release-date UDF (ADR-0049 Phase C).

Replaces the per-row `store.steampowered.com/api/appdetails` fetch loop
used by `70-tools/scripts/media_gamers_enrich_sources.py --steam-backfill`
and `70-tools/scripts/media_gamers_backfill_release_year.py`.

SQL usage
---------

    SELECT vertex_id,
           steam_release_date(appid) AS release_json
    FROM (
      SELECT vertex_id,
             -- extract the Steam appid claim populated by wikidata_entity_claims
             claims::jsonb ->> 'steamAppIds'[0] AS appid
      FROM vertex_game_title
      WHERE release_year IS NULL
    ) s
    WHERE s.appid IS NOT NULL;

Surface
-------

    com.etzhayyim.apps.steam.releaseDate(appid)    VARCHAR → VARCHAR

Output JSON:
    { "appid": "123", "releaseDate": "2021-08-10", "releaseYear": 2021,
      "comingSoon": false, "raw": "10 Aug, 2021" }

`{"releaseDate": null, "appid": "...", "reason": "..."}` on any failure
(coming_soon, non-success flag, HTTP 4xx/5xx, parse error, empty appid).

Never raises.
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import logging
import re as _re
import urllib.error
import urllib.parse
import urllib.request

from kotodama import udf

log = logging.getLogger(__name__)

_STEAM_URL = "https://store.steampowered.com/api/appdetails"
_TIMEOUT_SEC = 12
_UA = "etzhayyim-steam-udf/1.0 (ops@etzhayyim.com)"
_YEAR_RE = _re.compile(r"(19\d{2}|20\d{2})")
_FORMATS = ("%d %b, %Y", "%b %d, %Y", "%d %B, %Y", "%B %d, %Y")


def _fetch(appid: str) -> dict | None:
    """One appdetails GET. Returns the raw top-level JSON object or None
    on any transport / parse failure."""
    params = urllib.parse.urlencode({"appids": appid, "l": "english"})
    url = f"{_STEAM_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
            if resp.status != 200:
                return None
            raw = resp.read(512 * 1024)
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    try:
        body = _json.loads(raw.decode("utf-8"))
    except (_json.JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _parse_date(raw: str) -> tuple[str | None, int | None]:
    """Steam release-date strings are free-form. Try the four common
    locale-specific formats, then fall back to extracting the year.
    Returns (iso-date, year) or (None, None) if nothing parses."""
    s = (raw or "").strip()
    if not s:
        return None, None
    for fmt in _FORMATS:
        try:
            d = _dt.datetime.strptime(s, fmt).date()
            return d.isoformat(), d.year
        except ValueError:
            continue
    m = _YEAR_RE.search(s)
    if m:
        y = int(m.group(1))
        return f"{y}-01-01", y
    return None, None


@udf(
    nsid="com.etzhayyim.apps.steam.releaseDate",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("steam", "media-gamers", "release-date"),
    agent_tool="Look up a Steam AppID's release date via appdetails; returns JSON.",
)
def release_date(appid: str) -> str:
    """Release date for one Steam app. Callers dedup by vertex_id before
    invoking — Steam ratelimits per IP (~200/5min)."""
    if not appid:
        return _json.dumps({"appid": appid, "releaseDate": None,
                            "reason": "appid required"})
    body = _fetch(appid)
    if body is None:
        return _json.dumps({"appid": appid, "releaseDate": None,
                            "reason": "fetch failed"})
    item = body.get(str(appid)) if isinstance(body, dict) else None
    if not isinstance(item, dict) or not item.get("success"):
        return _json.dumps({"appid": appid, "releaseDate": None,
                            "reason": "steam-not-success"})
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    rd = data.get("release_date") if isinstance(data.get("release_date"), dict) else {}
    if rd.get("coming_soon"):
        return _json.dumps({"appid": appid, "releaseDate": None,
                            "comingSoon": True, "raw": rd.get("date")})
    iso, year = _parse_date(str(rd.get("date") or ""))
    return _json.dumps({
        "appid": appid,
        "releaseDate": iso,
        "releaseYear": year,
        "comingSoon": False,
        "raw": rd.get("date"),
    }, ensure_ascii=False)
