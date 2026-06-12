"""
DNS-over-HTTPS resolver UDF (ADR-0049 Phase C).

Replaces the per-row DoH fetch loop in
`70-tools/scripts/hourly_collect.py` and `collect-dns-global.sh`.

Two surfaces, chosen to match how callers actually want to consume DNS:

    com.etzhayyim.apps.dns.resolve(domain, rtype)         VARCHAR, VARCHAR → VARCHAR
        Returns a comma-joined string of RRs for a single record type.
        Empty string on NXDOMAIN / upstream error (never raises).

    com.etzhayyim.apps.dns.resolveJson(domain, rtype)     VARCHAR, VARCHAR → VARCHAR
        Returns the raw Cloudflare DoH JSON body so callers can extract
        TTLs, authority sections, or SOA — useful for passive-DNS
        ingestion. `{"error": "..."}` envelope on failure.

SQL usage
---------

    INSERT INTO vertex_dns_resolution (domain, rtype, value, resolved_at)
    SELECT
      d.domain,
      r.rtype,
      dns_resolve(d.domain, r.rtype) AS value,
      NOW()::varchar AS resolved_at
    FROM vertex_dns_seed d
    CROSS JOIN (VALUES ('A'), ('AAAA'), ('MX'), ('NS'), ('TXT')) r(rtype)
    WHERE NOT EXISTS (
      SELECT 1 FROM vertex_dns_resolution
      WHERE domain = d.domain AND rtype = r.rtype
        AND resolved_at > NOW() - INTERVAL '24 hours'
    );

Throughput
----------

`io_threads=100` lets 100 concurrent DoH GETs overlap. Cloudflare's
1.1.1.1 DoH endpoint sustains ~1000 rps from a single IP before
rate-limiting, so a 3-replica pod pool caps at ~300 rps × 3 = ~900 rps
steady-state (well under the Cloudflare per-IP ceiling).

Error policy
------------

- Transport / JSON parse errors → empty string (resolve) or
  `{"error": "..."}` envelope (resolveJson).
- NXDOMAIN → empty string, same shape.
- 4xx/5xx → empty string + logged once per batch.

Never raises, so arrow-udf never drops a row batch.
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

_DOH_URL = "https://cloudflare-dns.com/dns-query"
_TIMEOUT_SEC = 8
_UA = "etzhayyim-dns-udf/1.0 (ops@etzhayyim.com)"
_ALLOWED_RTYPES = frozenset({
    "A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR", "SRV", "CAA",
})


def _doh_fetch(domain: str, rtype: str) -> dict[str, Any] | None:
    """One DoH GET. Returns parsed JSON or None on any failure."""
    if not domain:
        return None
    rt = (rtype or "").strip().upper()
    if rt not in _ALLOWED_RTYPES:
        return None
    params = urllib.parse.urlencode({"name": domain, "type": rt, "ct": "application/dns-json"})
    url = f"{_DOH_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/dns-json", "User-Agent": _UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
            if resp.status != 200:
                return None
            raw = resp.read(64 * 1024)
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    try:
        return _json.loads(raw.decode("utf-8"))
    except (_json.JSONDecodeError, UnicodeDecodeError):
        return None


def _answer_strings(body: dict[str, Any] | None) -> list[str]:
    """Extract `Answer[*].data` from a DoH JSON body, in response order.
    Empty list if the body is falsy, lacks Answer, or Status != 0
    (NOERROR)."""
    if not body or body.get("Status") != 0:
        return []
    out: list[str] = []
    for entry in body.get("Answer") or []:
        val = entry.get("data") if isinstance(entry, dict) else None
        if isinstance(val, str) and val:
            out.append(val)
    return out


@udf(
    nsid="com.etzhayyim.apps.dns.resolve",
    io_threads=100,
    input_types=["VARCHAR", "VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("dns", "network-intel", "doh"),
    agent_tool="Resolve DNS records via Cloudflare DoH (A/AAAA/MX/NS/TXT/...).",
)
def resolve(domain: str, rtype: str) -> str:
    """Comma-joined RR values for one (domain, rtype). Empty on any failure.

    Example: resolve('etzhayyim.com', 'A') → '104.21.25.30,172.67.222.17'
    """
    if not domain:
        return ""
    body = _doh_fetch(domain, rtype)
    answers = _answer_strings(body)
    # Comma-join with no surrounding whitespace so SQL can `STRING_TO_ARRAY(..., ',')`
    # without extra trim() calls.
    return ",".join(answers)


@udf(
    nsid="com.etzhayyim.apps.dns.resolveJson",
    io_threads=100,
    input_types=["VARCHAR", "VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("dns", "network-intel", "doh", "raw"),
    agent_tool="Resolve DNS records via Cloudflare DoH and return raw JSON body (TTL / SOA / authority).",
)
def resolve_json(domain: str, rtype: str) -> str:
    """Raw DoH JSON as string. `{"error": "..."}` envelope on failure so
    callers can `->>'Answer'` without crashing on NULL."""
    if not domain:
        return _json.dumps({"error": "domain required"})
    rt = (rtype or "").strip().upper()
    if rt not in _ALLOWED_RTYPES:
        return _json.dumps({"error": f"rtype not allowed: {rtype!r}"})
    body = _doh_fetch(domain, rt)
    if body is None:
        return _json.dumps({"error": "fetch failed", "domain": domain, "rtype": rt})
    # Return body as-is so callers can extract Status / Answer / Authority.
    try:
        return _json.dumps(body, ensure_ascii=False)
    except (TypeError, ValueError):
        return _json.dumps({"error": "serialise failed", "domain": domain, "rtype": rt})
