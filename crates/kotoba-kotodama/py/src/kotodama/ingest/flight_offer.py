"""Flight offer ingest tasks (Skyscanner-equivalent, ADR-0056 BPMN-as-actor).

Provides LangServer task handlers behind `com.etzhayyim.apps.flightOffer.*` BPMN
processes. Writes the existing `vertex_flight_offer` table created by
30-graph/graph-schema/migrations/20260416110000_vertex_flight_offer.ts.

Provider strategy:
  - `provider="stub"` (default when no credentials) returns deterministic
    fixtures so the BPMN dispatch path is exercisable in dev.
  - `provider="amadeus"` calls Amadeus Self-Service Flight Offers Search
    (https://test.api.amadeus.com/v2/shopping/flight-offers). Requires
    AMADEUS_CLIENT_ID + AMADEUS_CLIENT_SECRET in env (per CLAUDE.md
    Keychain rule, populate via `etzhayyim.flightoffer` service).
  - `provider="duffel"` placeholder; not yet implemented.

Real provider integration is gated on credential provisioning; the task
falls back to stub mode when env is not configured.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


FLIGHT_OFFER_DID = "did:web:flight-offer.etzhayyim.com"
OFFER_TABLE = "vertex_flight_offer"
ALERT_TABLE = "vertex_flight_offer_alert"
WATCH_TABLE = "vertex_flight_offer_watch"
SOURCE_TABLE = "vertex_flight_offer_source"
SOURCE_RUN_TABLE = "vertex_flight_offer_source_run"
SOURCE_HEALTH_MV = "mv_flight_offer_source_health"
ALERT_COLLECTION = "com.etzhayyim.apps.flightOffer.alert"
WATCH_COLLECTION = "com.etzhayyim.apps.flightOffer.watch"
SOURCE_RUN_COLLECTION = "com.etzhayyim.apps.flightOffer.sourceRun"

AMADEUS_TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
AMADEUS_SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"
DUFFEL_OFFER_REQUEST_URL = "https://api.duffel.com/air/offer_requests"
DUFFEL_API_VERSION = "v2"
KIWI_SEARCH_URL = "https://api.tequila.kiwi.com/v2/search"
TRAVELPAYOUTS_SEARCH_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
_AMADEUS_TOKEN_CACHE: dict[str, Any] = {"token": None, "exp": 0.0}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _hash8(*parts: Any) -> str:
    payload = "|".join(_clean(p) for p in parts)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=6).hexdigest()


def _vertex_id(provider: str, offer_id: str) -> str:
    return f"at://{FLIGHT_OFFER_DID}/com.etzhayyim.apps.flightOffer.offer/{provider}-{offer_id}"


def _http_post_form(url: str, form: dict[str, str], timeout: float = 10.0) -> dict[str, Any]:
    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_get_json(url: str, headers: dict[str, str], timeout: float = 15.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _amadeus_token() -> str:
    cid = os.environ.get("AMADEUS_CLIENT_ID", "").strip()
    sec = os.environ.get("AMADEUS_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        raise RuntimeError("AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET not set")
    now = time.time()
    cached = _AMADEUS_TOKEN_CACHE.get("token")
    if cached and float(_AMADEUS_TOKEN_CACHE.get("exp", 0)) - 60 > now:
        return str(cached)
    body = _http_post_form(
        AMADEUS_TOKEN_URL,
        {"grant_type": "client_credentials", "client_id": cid, "client_secret": sec},
    )
    token = _clean(body.get("access_token"))
    if not token:
        raise RuntimeError(f"amadeus token missing: {body}")
    expires_in = float(body.get("expires_in") or 1700)
    _AMADEUS_TOKEN_CACHE["token"] = token
    _AMADEUS_TOKEN_CACHE["exp"] = now + expires_in
    return token


def _amadeus_search(
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    max_offers: int,
) -> list[dict[str, Any]]:
    token = _amadeus_token()
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": outbound_date[:10],
        "adults": "1",
        "max": str(max(1, min(int(max_offers or 20), 50))),
    }
    if return_date:
        params["returnDate"] = return_date[:10]
    if currency:
        params["currencyCode"] = currency
    url = AMADEUS_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    body = _http_get_json(url, {"Authorization": f"Bearer {token}"})
    out: list[dict[str, Any]] = []
    for raw in body.get("data") or []:
        offer_id = _clean(raw.get("id"))
        if not offer_id:
            continue
        price = raw.get("price") or {}
        itineraries = raw.get("itineraries") or []
        first_seg = ((itineraries[0] or {}).get("segments") or [{}])[0] if itineraries else {}
        carrier = _clean(first_seg.get("carrierCode"))
        flight_no = carrier + _clean(first_seg.get("number"))
        out.append({
            "offerId": offer_id,
            "airline": carrier,
            "flightNumber": flight_no,
            "basePrice": float(price.get("base") or 0) or None,
            "taxes": None,
            "totalPrice": float(price.get("grandTotal") or price.get("total") or 0) or None,
            "currency": _clean(price.get("currency")) or currency,
            "bookingUrl": "",
            "deeplinkUrl": "",
            "sourceUrl": AMADEUS_SEARCH_URL,
            "props": json.dumps({"validatingAirlineCodes": raw.get("validatingAirlineCodes")}),
        })
    return out


def _http_post_json(
    url: str, headers: dict[str, str], body: dict[str, Any], timeout: float = 15.0
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _duffel_search(
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    max_offers: int,
) -> list[dict[str, Any]]:
    token = os.environ.get("DUFFEL_API_KEY", "").strip()
    if not token:
        raise RuntimeError("DUFFEL_API_KEY not set")
    slices = [{"origin": origin, "destination": destination, "departure_date": outbound_date[:10]}]
    if return_date:
        slices.append({
            "origin": destination,
            "destination": origin,
            "departure_date": return_date[:10],
        })
    payload = {"data": {"slices": slices, "passengers": [{"type": "adult"}],
                        "cabin_class": "economy"}}
    headers = {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": DUFFEL_API_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = _http_post_json(DUFFEL_OFFER_REQUEST_URL + "?return_offers=true", headers, payload)
    offers = ((body.get("data") or {}).get("offers")) or []
    cap = max(1, min(int(max_offers or 20), 50))
    out: list[dict[str, Any]] = []
    for raw in offers[:cap]:
        offer_id = _clean(raw.get("id"))
        if not offer_id:
            continue
        slices_data = raw.get("slices") or []
        first_seg = ((slices_data[0] or {}).get("segments") or [{}])[0] if slices_data else {}
        marketing = (first_seg.get("marketing_carrier") or {}) if first_seg else {}
        airline = _clean(marketing.get("iata_code"))
        flight_no = airline + _clean(first_seg.get("marketing_carrier_flight_number"))
        out.append({
            "offerId": offer_id,
            "airline": airline,
            "flightNumber": flight_no,
            "basePrice": float(raw.get("base_amount") or 0) or None,
            "taxes": float(raw.get("tax_amount") or 0) or None,
            "totalPrice": float(raw.get("total_amount") or 0) or None,
            "currency": _clean(raw.get("total_currency") or raw.get("base_currency")) or currency,
            "bookingUrl": "",
            "deeplinkUrl": "",
            "sourceUrl": DUFFEL_OFFER_REQUEST_URL,
            "props": json.dumps({"owner": (raw.get("owner") or {}).get("iata_code")}),
        })
    return out


def _kiwi_search(
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    max_offers: int,
) -> list[dict[str, Any]]:
    token = os.environ.get("KIWI_TEQUILA_API_KEY", "").strip()
    if not token:
        raise RuntimeError("KIWI_TEQUILA_API_KEY not set")
    dep_yyyymmdd = outbound_date[:10].replace("-", "/")
    dep_iso = "/".join(reversed(dep_yyyymmdd.split("/")))  # dd/mm/yyyy required by Tequila
    params = {
        "fly_from": origin,
        "fly_to": destination,
        "date_from": dep_iso,
        "date_to": dep_iso,
        "curr": currency or "USD",
        "limit": max(1, min(int(max_offers or 20), 50)),
    }
    if return_date:
        ret_yyyymmdd = return_date[:10].replace("-", "/")
        ret_iso = "/".join(reversed(ret_yyyymmdd.split("/")))
        params["return_from"] = ret_iso
        params["return_to"] = ret_iso
    url = KIWI_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    body = _http_get_json(url, {"apikey": token})
    out: list[dict[str, Any]] = []
    for raw in body.get("data") or []:
        offer_id = _clean(str(raw.get("id") or raw.get("booking_token") or ""))
        if not offer_id:
            continue
        first_route = (raw.get("route") or [{}])[0] if raw.get("route") else {}
        out.append({
            "offerId": offer_id,
            "airline": _clean(first_route.get("airline")),
            "flightNumber": _clean(str(first_route.get("airline") or "")) + _clean(str(first_route.get("flight_no") or "")),
            "basePrice": None,
            "taxes": None,
            "totalPrice": float(raw.get("price") or 0) or None,
            "currency": _clean(currency) or "USD",
            "bookingUrl": _clean(raw.get("deep_link") or ""),
            "deeplinkUrl": _clean(raw.get("deep_link") or ""),
            "sourceUrl": KIWI_SEARCH_URL,
            "props": json.dumps({"availability": raw.get("availability"),
                                 "virtual_interlining": raw.get("virtual_interlining")}),
        })
    return out


def _travelpayouts_search(
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    max_offers: int,
) -> list[dict[str, Any]]:
    token = os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TRAVELPAYOUTS_TOKEN not set")
    params = {
        "origin": origin,
        "destination": destination,
        "departure_at": outbound_date[:10],
        "currency": (currency or "usd").lower(),
        "limit": max(1, min(int(max_offers or 20), 30)),
        "token": token,
    }
    if return_date:
        params["return_at"] = return_date[:10]
    url = TRAVELPAYOUTS_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    body = _http_get_json(url, {"Accept": "application/json"})
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(body.get("data") or []):
        offer_id = _clean(
            str(raw.get("flight_number") or "") + "-" + str(raw.get("departure_at") or "") + f"-{idx}"
        )
        airline = _clean(raw.get("airline"))
        out.append({
            "offerId": offer_id,
            "airline": airline,
            "flightNumber": airline + _clean(str(raw.get("flight_number") or "")),
            "basePrice": None,
            "taxes": None,
            "totalPrice": float(raw.get("price") or 0) or None,
            "currency": _clean(currency) or "USD",
            "bookingUrl": _clean(raw.get("link") or ""),
            "deeplinkUrl": "",
            "sourceUrl": TRAVELPAYOUTS_SEARCH_URL,
            "props": json.dumps({"transfers": raw.get("transfers"),
                                 "duration": raw.get("duration")}),
        })
    return out


def _stub_search(
    origin: str,
    destination: str,
    outbound_date: str,
    currency: str,
) -> list[dict[str, Any]]:
    seed = _hash8(origin, destination, outbound_date, currency)
    base = 100 + (int(seed[:4], 16) % 900)
    return [
        {
            "offerId": f"stub-{seed}-{idx}",
            "airline": ["NH", "JL", "SQ"][idx % 3],
            "flightNumber": f"{['NH','JL','SQ'][idx % 3]}{100 + idx}",
            "basePrice": float(base + idx * 27),
            "taxes": float(40 + idx * 3),
            "totalPrice": float(base + idx * 27 + 40 + idx * 3),
            "currency": currency or "USD",
            "bookingUrl": f"https://flight-offer.etzhayyim.com/stub/book/{seed}-{idx}",
            "deeplinkUrl": "",
            "sourceUrl": "https://flight-offer.etzhayyim.com/stub",
            "props": json.dumps({"stub": True}),
        }
        for idx in range(3)
    ]


def _insert_offer(cur: Any, row: dict[str, Any]) -> int:
    _res = client.q(
        f"""
        INSERT INTO {OFFER_TABLE} (
            vertex_id, offer_id, provider, airline, flight_number,
            origin_iata, destination_iata, outbound_date, return_date,
            base_price, taxes, total_price, currency,
            booking_url, deeplink_url, observed_at, source_url, props
        )
        SELECT
            %s::varchar, %s::varchar, %s::varchar, %s::varchar, %s::varchar,
            %s::varchar, %s::varchar, %s::varchar, %s::varchar,
            %s::double precision, %s::double precision, %s::double precision, %s::varchar,
            %s::varchar, %s::varchar, %s::varchar, %s::varchar, %s::varchar
        WHERE NOT EXISTS (SELECT 1 FROM {OFFER_TABLE} WHERE vertex_id = %s::varchar)
        """,
        (
            row["vertex_id"], row["offer_id"], row["provider"], row["airline"], row["flight_number"],
            row["origin_iata"], row["destination_iata"], row["outbound_date"], row["return_date"],
            row["base_price"], row["taxes"], row["total_price"], row["currency"],
            row["booking_url"], row["deeplink_url"], row["observed_at"], row["source_url"], row["props"],
            row["vertex_id"],
        ),
    )
    return int((len(_res) if isinstance(_res, list) else 1) or 0)


def _persist_offers(
    raw_offers: list[dict[str, Any]],
    *,
    provider: str,
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    observed_at: str,
) -> int:
    written = 0
    if True:
        client = get_kotoba_client()
        for raw in raw_offers:
            row = {
                "vertex_id": _vertex_id(provider, _clean(raw.get("offerId"))),
                "offer_id": _clean(raw.get("offerId")),
                "provider": provider,
                "airline": _clean(raw.get("airline")),
                "flight_number": _clean(raw.get("flightNumber")),
                "origin_iata": origin,
                "destination_iata": destination,
                "outbound_date": outbound_date,
                "return_date": return_date,
                "base_price": raw.get("basePrice"),
                "taxes": raw.get("taxes"),
                "total_price": raw.get("totalPrice"),
                "currency": _clean(raw.get("currency")) or currency,
                "booking_url": _clean(raw.get("bookingUrl")),
                "deeplink_url": _clean(raw.get("deeplinkUrl")),
                "observed_at": observed_at,
                "source_url": _clean(raw.get("sourceUrl")),
                "props": _clean(raw.get("props")),
            }
            written += _insert_offer(cur, row)
    return written


def _adapter_amadeus(origin, destination, outbound_date, return_date, currency, max_offers):
    return _amadeus_search(origin, destination, outbound_date, return_date, currency, max_offers)


def _adapter_duffel(origin, destination, outbound_date, return_date, currency, max_offers):
    return _duffel_search(origin, destination, outbound_date, return_date, currency, max_offers)


def _adapter_kiwi(origin, destination, outbound_date, return_date, currency, max_offers):
    return _kiwi_search(origin, destination, outbound_date, return_date, currency, max_offers)


def _adapter_travelpayouts(origin, destination, outbound_date, return_date, currency, max_offers):
    return _travelpayouts_search(origin, destination, outbound_date, return_date, currency, max_offers)


def _adapter_stub(origin, destination, outbound_date, return_date, currency, max_offers):
    return _stub_search(origin, destination, outbound_date, currency)


# Source registry. Each row in vertex_flight_offer_source.adapter_key MUST map
# to a key in this dict. Adding a new ingester = add an `_adapter_<name>` fn
# and register it here. `flight.offer.fetchFromSource` looks up by source_id
# (which the seed migration sets equal to adapter_key for built-in sources).
_SOURCE_ADAPTERS: dict[str, Any] = {
    "amadeus": _adapter_amadeus,
    "duffel": _adapter_duffel,
    "kiwi-tequila": _adapter_kiwi,
    "travelpayouts-aviasales": _adapter_travelpayouts,
    "stub": _adapter_stub,
    # Single-carrier direct NDC sources are intentionally unset until the
    # airline approves us as a partner. They appear in vertex_flight_offer_source
    # with status='planned'; resolving them via _resolve_provider falls back to
    # 'stub' until the credentials + adapter ship.
}

_SOURCE_ENV_REQ: dict[str, list[str]] = {
    "amadeus": ["AMADEUS_CLIENT_ID", "AMADEUS_CLIENT_SECRET"],
    "duffel": ["DUFFEL_API_KEY"],
    "kiwi-tequila": ["KIWI_TEQUILA_API_KEY"],
    "travelpayouts-aviasales": ["TRAVELPAYOUTS_TOKEN"],
    "stub": [],
}


def _has_credentials(source_id: str) -> bool:
    keys = _SOURCE_ENV_REQ.get(source_id) or []
    return all(bool(os.environ.get(k)) for k in keys) if keys else True


def _resolve_provider(requested: str) -> str:
    """Legacy resolver kept for searchOffers compatibility. Returns a source_id
    that exists in _SOURCE_ADAPTERS and has credentials provisioned."""
    requested = _clean(requested).lower()
    # Accept short aliases used in earlier phases.
    alias_map = {"kiwi": "kiwi-tequila", "travelpayouts": "travelpayouts-aviasales"}
    requested = alias_map.get(requested, requested)
    if requested in _SOURCE_ADAPTERS and _has_credentials(requested):
        return requested
    if requested:  # explicit but missing creds → stub
        return "stub"
    # auto-pick: amadeus > duffel > kiwi > travelpayouts > stub
    for fallback in ("amadeus", "duffel", "kiwi-tequila", "travelpayouts-aviasales"):
        if _has_credentials(fallback):
            return fallback
    return "stub"


def _do_search(
    *,
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    provider: str,
    max_offers: int,
) -> dict[str, Any]:
    if not origin or not destination or not outbound_date:
        return {"status": "error", "error": "originIata, destinationIata, outboundDate required",
                "offersWritten": 0, "offersFetched": 0}
    chosen = _resolve_provider(provider)
    observed_at = _now_iso()
    adapter = _SOURCE_ADAPTERS.get(chosen) or _adapter_stub
    raw = adapter(origin, destination, outbound_date, return_date, currency, max_offers)
    written = _persist_offers(
        raw,
        provider=chosen,
        origin=origin,
        destination=destination,
        outbound_date=outbound_date,
        return_date=return_date,
        currency=currency,
        observed_at=observed_at,
    )
    return {
        "status": "ok",
        "provider": chosen,
        "offersFetched": len(raw),
        "offersWritten": written,
        "providerObservedAt": observed_at,
    }


async def task_flight_offer_fetch(
    originIata: str = "",
    destinationIata: str = "",
    outboundDate: str = "",
    returnDate: str = "",
    currency: str = "USD",
    provider: str = "",
    maxOffers: int = 20,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_search,
            origin=_clean(originIata).upper(),
            destination=_clean(destinationIata).upper(),
            outbound_date=_clean(outboundDate),
            return_date=_clean(returnDate),
            currency=_clean(currency).upper() or "USD",
            provider=_clean(provider),
            max_offers=int(maxOffers or 20),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.fetch failed: {e}",
                "offersWritten": 0, "offersFetched": 0}


def _query_cheapest(
    cur: Any, origin: str, destination: str, outbound_date: str, currency: str
) -> dict[str, Any] | None:
    _res = client.q(
        """
        SELECT cheapest_total_price, cheapest_provider, cheapest_booking_url, cheapest_observed_at
        FROM mv_flight_offer_cheapest_by_route_date
        WHERE origin_iata = %s AND destination_iata = %s
          AND outbound_date = %s AND currency = %s
        LIMIT 1
        """,
        (origin, destination, outbound_date, currency),
    )
    row = (_res[0] if _res else None)
    if not row:
        return None
    return {
        "cheapestTotalPrice": float(row[0]) if row[0] is not None else None,
        "cheapestProvider": row[1] or "",
        "cheapestBookingUrl": row[2] or "",
        "cheapestObservedAt": row[3] or "",
    }


def _last_alert_price(
    cur: Any, origin: str, destination: str, outbound_date: str, currency: str
) -> float | None:
    _res = client.q(
        f"""
        SELECT new_price FROM {ALERT_TABLE}
        WHERE origin_iata = %s AND destination_iata = %s
          AND outbound_date = %s AND currency = %s
        ORDER BY observed_at DESC LIMIT 1
        """,
        (origin, destination, outbound_date, currency),
    )
    row = (_res[0] if _res else None)
    if not row or row[0] is None:
        return None
    return float(row[0])


def _insert_alert(cur: Any, alert: dict[str, Any]) -> int:
    _res = client.q(
        f"""
        INSERT INTO {ALERT_TABLE} (
            vertex_id, origin_iata, destination_iata, outbound_date, currency,
            previous_price, new_price, drop_pct, provider, booking_url,
            observed_at, sensitivity_ord, org_id, user_id, actor_id
        )
        SELECT
            %s::varchar, %s::varchar, %s::varchar, %s::varchar, %s::varchar,
            %s::double precision, %s::double precision, %s::double precision,
            %s::varchar, %s::varchar, %s::varchar,
            1::bigint, %s::varchar, %s::varchar, %s::varchar
        WHERE NOT EXISTS (SELECT 1 FROM {ALERT_TABLE} WHERE vertex_id = %s::varchar)
        """,
        (
            alert["vertex_id"], alert["origin_iata"], alert["destination_iata"],
            alert["outbound_date"], alert["currency"],
            alert["previous_price"], alert["new_price"], alert["drop_pct"],
            alert["provider"], alert["booking_url"], alert["observed_at"],
            FLIGHT_OFFER_DID, FLIGHT_OFFER_DID, "sys.bpmn.flight-offer.alert",
            alert["vertex_id"],
        ),
    )
    return int((len(_res) if isinstance(_res, list) else 1) or 0)


def _do_check_drop(
    *,
    origin: str,
    destination: str,
    outbound_date: str,
    currency: str,
    threshold_pct: float,
) -> dict[str, Any]:
    if not origin or not destination or not outbound_date:
        return {"status": "error", "error": "originIata, destinationIata, outboundDate required",
                "alerted": False}
    if True:
        client = get_kotoba_client()
        cheapest = _query_cheapest(cur, origin, destination, outbound_date, currency)
        if not cheapest or cheapest.get("cheapestTotalPrice") is None:
            return {"status": "ok", "alerted": False, "reason": "no offers"}
        new_price = float(cheapest["cheapestTotalPrice"])
        previous = _last_alert_price(cur, origin, destination, outbound_date, currency)
        if previous is None:
            previous = new_price
        drop_pct = 0.0 if previous <= 0 else (previous - new_price) / previous * 100.0
        if drop_pct < float(threshold_pct):
            return {"status": "ok", "alerted": False, "newPrice": new_price,
                    "previousPrice": previous, "dropPct": drop_pct}
        observed_at = _clean(cheapest.get("cheapestObservedAt")) or _now_iso()
        vertex_id = (
            f"at://{FLIGHT_OFFER_DID}/{ALERT_COLLECTION}/"
            f"{origin}-{destination}-{outbound_date[:10]}-{currency}-{_hash8(observed_at, new_price)}"
        )
        _insert_alert(cur, {
            "vertex_id": vertex_id,
            "origin_iata": origin,
            "destination_iata": destination,
            "outbound_date": outbound_date,
            "currency": currency,
            "previous_price": previous,
            "new_price": new_price,
            "drop_pct": drop_pct,
            "provider": cheapest.get("cheapestProvider") or "",
            "booking_url": cheapest.get("cheapestBookingUrl") or "",
            "observed_at": observed_at,
        })
    return {
        "status": "ok",
        "alerted": True,
        "vertexId": vertex_id,
        "newPrice": new_price,
        "previousPrice": previous,
        "dropPct": drop_pct,
        "bookingUrl": cheapest.get("cheapestBookingUrl") or "",
        "provider": cheapest.get("cheapestProvider") or "",
    }


async def task_flight_offer_check_drop(
    originIata: str = "",
    destinationIata: str = "",
    outboundDate: str = "",
    currency: str = "USD",
    thresholdPct: float = 10.0,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_check_drop,
            origin=_clean(originIata).upper(),
            destination=_clean(destinationIata).upper(),
            outbound_date=_clean(outboundDate),
            currency=_clean(currency).upper() or "USD",
            threshold_pct=float(thresholdPct or 10.0),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.checkDrop failed: {e}", "alerted": False}


def _watch_vertex_id(origin: str, destination: str, outbound_date: str, currency: str) -> str:
    return (
        f"at://{FLIGHT_OFFER_DID}/{WATCH_COLLECTION}/"
        f"{origin}-{destination}-{outbound_date[:10]}-{currency}"
    )


def _do_add_watch(
    *,
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    threshold_pct: float,
    cadence_minutes: int,
    provider_hint: str,
    max_offers: int,
    notify_did: str,
) -> dict[str, Any]:
    if not origin or not destination or not outbound_date:
        return {"status": "error", "error": "originIata, destinationIata, outboundDate required"}
    vertex_id = _watch_vertex_id(origin, destination, outbound_date, currency)
    now = _now_iso()
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"SELECT vertex_id FROM {WATCH_TABLE} WHERE vertex_id = %s LIMIT 1",
            (vertex_id,),
        )
        existed = (_res[0] if _res else None) is not None
        if existed:
            _res = client.q(
                f"""
                UPDATE {WATCH_TABLE}
                   SET return_date = %s, threshold_pct = %s::double precision,
                       cadence_minutes = %s::bigint, provider_hint = %s,
                       max_offers = %s::bigint, notify_did = %s, status = 'active'
                 WHERE vertex_id = %s
                """,
                (return_date, threshold_pct, cadence_minutes, provider_hint,
                 max_offers, notify_did, vertex_id),
            )
        else:
            _res = client.q(
                f"""
                INSERT INTO {WATCH_TABLE} (
                    vertex_id, origin_iata, destination_iata, outbound_date, return_date,
                    currency, threshold_pct, cadence_minutes, provider_hint, max_offers,
                    notify_did, status, last_polled_at, next_due_at, created_at,
                    sensitivity_ord, org_id, user_id, actor_id
                ) VALUES (
                    %s::varchar, %s::varchar, %s::varchar, %s::varchar, %s::varchar,
                    %s::varchar, %s::double precision, %s::bigint, %s::varchar, %s::bigint,
                    %s::varchar, %s::varchar, %s::varchar, %s::varchar, %s::varchar,
                    1::bigint, %s::varchar, %s::varchar, %s::varchar
                )
                """,
                (
                    vertex_id, origin, destination, outbound_date, return_date,
                    currency, threshold_pct, cadence_minutes, provider_hint, max_offers,
                    notify_did, "active", "", now, now,
                    FLIGHT_OFFER_DID, FLIGHT_OFFER_DID, "sys.bpmn.flight-offer.watch",
                ),
            )
    return {"status": "ok", "vertexId": vertex_id, "created": not existed}


async def task_flight_offer_add_watch(
    originIata: str = "",
    destinationIata: str = "",
    outboundDate: str = "",
    returnDate: str = "",
    currency: str = "USD",
    thresholdPct: float = 10.0,
    cadenceMinutes: int = 360,
    providerHint: str = "",
    maxOffers: int = 20,
    notifyDid: str = "",
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_add_watch,
            origin=_clean(originIata).upper(),
            destination=_clean(destinationIata).upper(),
            outbound_date=_clean(outboundDate),
            return_date=_clean(returnDate),
            currency=_clean(currency).upper() or "USD",
            threshold_pct=float(thresholdPct or 10.0),
            cadence_minutes=int(cadenceMinutes or 360),
            provider_hint=_clean(providerHint),
            max_offers=int(maxOffers or 20),
            notify_did=_clean(notifyDid) or FLIGHT_OFFER_DID,
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.addWatch failed: {e}"}


def _select_due_watches(cur: Any, limit: int, force: bool) -> list[tuple[Any, ...]]:
    if force:
        _res = client.q(
            f"""
            SELECT origin_iata, destination_iata, outbound_date, return_date, currency,
                   threshold_pct, provider_hint, max_offers, notify_did
              FROM {WATCH_TABLE}
             WHERE status = 'active'
             LIMIT {int(limit)}
            """,
        )
    else:
        now = _now_iso()
        _res = client.q(
            f"""
            SELECT origin_iata, destination_iata, outbound_date, return_date, currency,
                   threshold_pct, provider_hint, max_offers, notify_did
              FROM {WATCH_TABLE}
             WHERE status = 'active'
               AND (next_due_at IS NULL OR next_due_at = '' OR next_due_at <= %s)
             LIMIT {int(limit)}
            """,
            (now,),
        )
    return list(_res or [])


def _mark_watch_polled(
    cur: Any, origin: str, destination: str, outbound_date: str, currency: str,
    cadence_minutes: int = 360,
) -> None:
    polled_at = _now_iso()
    next_due_epoch = time.time() + max(60, int(cadence_minutes)) * 60
    next_due_at = datetime.fromtimestamp(next_due_epoch, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    _res = client.q(
        f"""
        UPDATE {WATCH_TABLE}
           SET last_polled_at = %s, next_due_at = %s
         WHERE vertex_id = %s
        """,
        (polled_at, next_due_at, _watch_vertex_id(origin, destination, outbound_date, currency)),
    )


def _do_poll_watchlist(*, limit: int, force: bool) -> dict[str, Any]:
    """Multi-source fan-out poll. Each watch row triggers fetchFromSource
    against every active+credentialed source (filtered by provider_hint
    allowlist if set), then a single drop check against the unified MV."""
    offers_written_total = 0
    alerts_fired_total = 0
    errors_total = 0
    sources_invoked_total = 0
    per_source_stats: dict[str, dict[str, int]] = {}
    drop_alerts: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        rows = _select_due_watches(cur, limit, force)
        active_sources_all = _select_active_sources_for_route(cur, "", "")
    for row in rows:
        (origin, destination, outbound_date, return_date, currency,
         threshold_pct, provider_hint, max_offers, notify_did) = row
        org = _clean(origin).upper()
        dst = _clean(destination).upper()
        out_date = _clean(outbound_date)
        ret_date = _clean(return_date)
        ccy = _clean(currency).upper() or "USD"
        max_o = int(max_offers or 20)
        threshold = float(threshold_pct or 10.0)
        notify = _clean(notify_did) or FLIGHT_OFFER_DID

        allowlist = _parse_source_filter(provider_hint)
        sources = (
            [s for s in active_sources_all if s in allowlist]
            if allowlist else active_sources_all
        )
        if not sources:
            sources = ["stub"]
        for source_id in sources:
            try:
                fetched = _do_fetch_from_source(
                    source_id=source_id, origin=org, destination=dst,
                    outbound_date=out_date, return_date=ret_date,
                    currency=ccy, max_offers=max_o,
                )
                stat = per_source_stats.setdefault(
                    source_id, {"runs": 0, "ok": 0, "error": 0, "offersWritten": 0}
                )
                stat["runs"] += 1
                if fetched.get("status") == "ok":
                    stat["ok"] += 1
                    written = int(fetched.get("offersWritten") or 0)
                    stat["offersWritten"] += written
                    offers_written_total += written
                else:
                    stat["error"] += 1
                    errors_total += 1
                sources_invoked_total += 1
            except Exception:  # noqa: BLE001
                errors_total += 1
        try:
            drop = _do_check_drop(
                origin=org, destination=dst, outbound_date=out_date,
                currency=ccy, threshold_pct=threshold,
            )
            if drop.get("alerted"):
                alerts_fired_total += 1
                drop_alerts.append({
                    "origin": org, "destination": dst,
                    "outboundDate": out_date, "currency": ccy,
                    "newPrice": drop.get("newPrice"),
                    "previousPrice": drop.get("previousPrice"),
                    "dropPct": drop.get("dropPct"),
                    "bookingUrl": drop.get("bookingUrl") or "",
                    "provider": drop.get("provider") or "",
                    "notifyDid": notify,
                })
        except Exception:  # noqa: BLE001
            errors_total += 1
        try:
            if True:
                client = get_kotoba_client()
                _mark_watch_polled(cur2, org, dst, out_date, ccy)
        except Exception:  # noqa: BLE001
            pass
    return {
        "status": "ok",
        "watchesRead": len(rows),
        "sourcesInvoked": sources_invoked_total,
        "offersWritten": offers_written_total,
        "alertsFired": alerts_fired_total,
        "errors": errors_total,
        "perSourceStats": per_source_stats,
        "dropAlerts": drop_alerts,
    }


def _do_get_cheapest(
    *, origin: str, destination: str, outbound_date: str, currency: str
) -> dict[str, Any]:
    if not origin or not destination or not outbound_date or not currency:
        return {"status": "error",
                "error": "originIata, destinationIata, outboundDate, currency required",
                "found": False}
    if True:
        client = get_kotoba_client()
        row = _query_cheapest(cur, origin, destination, outbound_date, currency)
    if not row:
        return {"status": "ok", "found": False,
                "originIata": origin, "destinationIata": destination,
                "outboundDate": outbound_date, "currency": currency}
    return {"status": "ok", "found": True,
            "originIata": origin, "destinationIata": destination,
            "outboundDate": outbound_date, "currency": currency, **row}


async def task_flight_offer_get_cheapest(
    originIata: str = "",
    destinationIata: str = "",
    outboundDate: str = "",
    currency: str = "USD",
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_get_cheapest,
            origin=_clean(originIata).upper(),
            destination=_clean(destinationIata).upper(),
            outbound_date=_clean(outboundDate),
            currency=_clean(currency).upper() or "USD",
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.getCheapest failed: {e}",
                "found": False}


def _do_remove_watch(
    *, origin: str, destination: str, outbound_date: str, currency: str, hard: bool
) -> dict[str, Any]:
    if not origin or not destination or not outbound_date:
        return {"status": "error", "error": "originIata, destinationIata, outboundDate required",
                "removed": False}
    vertex_id = _watch_vertex_id(origin, destination, outbound_date, currency)
    if True:
        client = get_kotoba_client()
        if hard:
            _res = client.q(f"DELETE FROM {WATCH_TABLE} WHERE vertex_id = %s", (vertex_id,))
        else:
            _res = client.q(
                f"UPDATE {WATCH_TABLE} SET status = 'archived' WHERE vertex_id = %s",
                (vertex_id,),
            )
        affected = int((len(_res) if isinstance(_res, list) else 1) or 0)
    return {"status": "ok", "removed": affected > 0, "vertexId": vertex_id, "hard": hard}


async def task_flight_offer_remove_watch(
    originIata: str = "",
    destinationIata: str = "",
    outboundDate: str = "",
    currency: str = "USD",
    hard: bool = False,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_remove_watch,
            origin=_clean(originIata).upper(),
            destination=_clean(destinationIata).upper(),
            outbound_date=_clean(outboundDate),
            currency=_clean(currency).upper() or "USD",
            hard=bool(hard),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.removeWatch failed: {e}",
                "removed": False}


def _do_list_watch(*, status: str, limit: int) -> dict[str, Any]:
    if True:
        client = get_kotoba_client()
        if status:
            _res = client.q(
                f"""
                SELECT vertex_id, origin_iata, destination_iata, outbound_date, return_date,
                       currency, threshold_pct, cadence_minutes, provider_hint, max_offers,
                       notify_did, status, last_polled_at, next_due_at, created_at
                  FROM {WATCH_TABLE}
                 WHERE status = %s
                 LIMIT {int(limit)}
                """,
                (status,),
            )
        else:
            _res = client.q(
                f"""
                SELECT vertex_id, origin_iata, destination_iata, outbound_date, return_date,
                       currency, threshold_pct, cadence_minutes, provider_hint, max_offers,
                       notify_did, status, last_polled_at, next_due_at, created_at
                  FROM {WATCH_TABLE}
                 LIMIT {int(limit)}
                """,
            )
        rows = _res or []
    items = [
        {
            "vertexId": r[0], "originIata": r[1], "destinationIata": r[2],
            "outboundDate": r[3], "returnDate": r[4], "currency": r[5],
            "thresholdPct": float(r[6]) if r[6] is not None else None,
            "cadenceMinutes": int(r[7]) if r[7] is not None else None,
            "providerHint": r[8], "maxOffers": int(r[9]) if r[9] is not None else None,
            "notifyDid": r[10], "status": r[11],
            "lastPolledAt": r[12], "nextDueAt": r[13], "createdAt": r[14],
        }
        for r in rows
    ]
    return {"status": "ok", "items": items, "count": len(items)}


async def task_flight_offer_list_watch(
    status: str = "active",
    limit: int = 100,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_list_watch,
            status=_clean(status),
            limit=max(1, min(int(limit or 100), 500)),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.listWatch failed: {e}",
                "items": [], "count": 0}


async def task_flight_offer_poll_watchlist(
    limit: int = 50,
    force: bool = False,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_poll_watchlist,
            limit=int(limit or 50),
            force=bool(force),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.pollWatchlist failed: {e}",
                "watchesRead": 0, "offersWritten": 0, "alertsFired": 0, "errors": 1}


# ─────────────────────────────────────────────────────────────────────────────
# Source-registry-driven ingest (multi-source, multi-airline). Source rows live
# in vertex_flight_offer_source; the adapter dispatch is _SOURCE_ADAPTERS above.
# ─────────────────────────────────────────────────────────────────────────────


def _log_source_run(
    cur: Any,
    *,
    source_id: str,
    resolved_source: str,
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    status: str,
    error_class: str,
    error_message: str,
    offers_fetched: int,
    offers_written: int,
    latency_ms: int,
    observed_at: str,
) -> None:
    run_id = _hash8(source_id, origin, destination, outbound_date, observed_at, latency_ms)
    vertex_id = (
        f"at://{FLIGHT_OFFER_DID}/{SOURCE_RUN_COLLECTION}/{source_id}-{run_id}"
    )
    _res = client.q(
        f"""
        INSERT INTO {SOURCE_RUN_TABLE} (
            vertex_id, run_id, source_id, resolved_source,
            origin_iata, destination_iata, outbound_date, return_date, currency,
            status, error_class, error_message,
            offers_fetched, offers_written, latency_ms, observed_at,
            sensitivity_ord, org_id, user_id, actor_id
        ) VALUES (
            %s::varchar, %s::varchar, %s::varchar, %s::varchar,
            %s::varchar, %s::varchar, %s::varchar, %s::varchar, %s::varchar,
            %s::varchar, %s::varchar, %s::varchar,
            %s::bigint, %s::bigint, %s::bigint, %s::varchar,
            1::bigint, %s::varchar, %s::varchar, %s::varchar
        )
        """,
        (
            vertex_id, run_id, source_id, resolved_source,
            origin, destination, outbound_date, return_date, currency,
            status, error_class, error_message[:500] if error_message else "",
            offers_fetched, offers_written, latency_ms, observed_at,
            FLIGHT_OFFER_DID, FLIGHT_OFFER_DID, "sys.bpmn.flight-offer.run",
        ),
    )


def _resolve_source_for_fetch(source_id: str) -> str:
    """Validate the requested source against the registry + adapter dict + creds."""
    chosen = source_id
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"SELECT source_id, status, adapter_key FROM {SOURCE_TABLE} WHERE source_id = %s LIMIT 1",
            (source_id,),
        )
        row = (_res[0] if _res else None)
    if row is not None:
        registry_status = (row[1] or "").lower()
        adapter_key = (row[2] or "").lower()
        if registry_status not in {"active", "stub"}:
            chosen = adapter_key or "stub"
    if chosen not in _SOURCE_ADAPTERS or not _has_credentials(chosen):
        chosen = "stub"
    return chosen


def _do_fetch_from_source(
    *,
    source_id: str,
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    currency: str,
    max_offers: int,
) -> dict[str, Any]:
    if not source_id:
        return {"status": "error", "error": "sourceId required",
                "offersWritten": 0, "offersFetched": 0}
    if not origin or not destination or not outbound_date:
        return {"status": "error", "error": "originIata, destinationIata, outboundDate required",
                "offersWritten": 0, "offersFetched": 0}
    chosen = _resolve_source_for_fetch(source_id)
    observed_at = _now_iso()
    started = time.time()
    run_status = "ok"
    err_class = ""
    err_msg = ""
    written = 0
    raw: list[dict[str, Any]] = []
    try:
        adapter = _SOURCE_ADAPTERS[chosen]
        raw = adapter(origin, destination, outbound_date, return_date, currency, max_offers)
        written = _persist_offers(
            raw,
            provider=chosen,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            currency=currency,
            observed_at=observed_at,
        )
        if chosen != source_id:
            run_status = "fallback"
    except Exception as e:  # noqa: BLE001
        run_status = "error"
        err_class = type(e).__name__
        err_msg = str(e)
    latency_ms = int((time.time() - started) * 1000)
    try:
        if True:
            client = get_kotoba_client()
            _log_source_run(
                cur,
                source_id=source_id, resolved_source=chosen,
                origin=origin, destination=destination,
                outbound_date=outbound_date, return_date=return_date, currency=currency,
                status=run_status, error_class=err_class, error_message=err_msg,
                offers_fetched=len(raw), offers_written=written, latency_ms=latency_ms,
                observed_at=observed_at,
            )
    except Exception:  # noqa: BLE001
        pass  # log failure must not mask the fetch result
    if run_status == "error":
        return {
            "status": "error",
            "sourceId": source_id, "resolvedSource": chosen,
            "offersFetched": 0, "offersWritten": 0,
            "providerObservedAt": observed_at,
            "error": f"{err_class}: {err_msg}",
            "latencyMs": latency_ms,
        }
    return {
        "status": "ok",
        "sourceId": source_id,
        "resolvedSource": chosen,
        "offersFetched": len(raw),
        "offersWritten": written,
        "providerObservedAt": observed_at,
        "fallback": run_status == "fallback",
        "latencyMs": latency_ms,
    }


def _select_active_sources_for_route(
    cur: Any, origin: str, destination: str, max_sources: int = 8,
) -> list[str]:
    """Active broad sources: status in (active, stub) AND credentials available
    AND adapter registered. Source filter logic (per-airline coverage) is
    skipped here for simplicity — broad sources cover all 30+ airlines, and
    single-carrier sources (ana-ndc / jal-ndc) are gated by status='planned'."""
    _res = client.q(
        f"""
        SELECT source_id FROM {SOURCE_TABLE}
         WHERE status IN ('active', 'stub')
         LIMIT {int(max_sources)}
        """,
    )
    rows = _res or []
    out: list[str] = []
    for r in rows:
        sid = r[0]
        if sid in _SOURCE_ADAPTERS and _has_credentials(sid):
            out.append(sid)
    return out


def _parse_source_filter(provider_hint: str) -> list[str]:
    """vertex_flight_offer_watch.provider_hint is reused as a comma-separated
    source_id allowlist. Empty / 'auto' / '*' = fan-out to all active sources."""
    val = (provider_hint or "").strip().lower()
    if not val or val in {"auto", "*", "all"}:
        return []
    return [s.strip() for s in val.split(",") if s.strip()]


async def task_flight_offer_fetch_from_source(
    sourceId: str = "",
    originIata: str = "",
    destinationIata: str = "",
    outboundDate: str = "",
    returnDate: str = "",
    currency: str = "USD",
    maxOffers: int = 20,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_fetch_from_source,
            source_id=_clean(sourceId),
            origin=_clean(originIata).upper(),
            destination=_clean(destinationIata).upper(),
            outbound_date=_clean(outboundDate),
            return_date=_clean(returnDate),
            currency=_clean(currency).upper() or "USD",
            max_offers=int(maxOffers or 20),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.fetchFromSource failed: {e}",
                "offersWritten": 0, "offersFetched": 0}


def _do_list_sources(*, status: str, limit: int) -> dict[str, Any]:
    if True:
        client = get_kotoba_client()
        if status:
            _res = client.q(
                f"""
                SELECT source_id, source_type, adapter_key, base_url, auth_scheme,
                       cadence_minutes, rate_limit_rpm, airlines_count, coverage_note, status
                  FROM vertex_flight_offer_source
                 WHERE status = %s
                 LIMIT {int(limit)}
                """,
                (status,),
            )
        else:
            _res = client.q(
                f"""
                SELECT source_id, source_type, adapter_key, base_url, auth_scheme,
                       cadence_minutes, rate_limit_rpm, airlines_count, coverage_note, status
                  FROM vertex_flight_offer_source
                 LIMIT {int(limit)}
                """,
            )
        rows = _res or []
    items = [
        {
            "sourceId": r[0], "sourceType": r[1], "adapterKey": r[2],
            "baseUrl": r[3], "authScheme": r[4],
            "cadenceMinutes": int(r[5]) if r[5] is not None else None,
            "rateLimitRpm": int(r[6]) if r[6] is not None else None,
            "airlinesCount": int(r[7]) if r[7] is not None else None,
            "coverageNote": r[8], "status": r[9],
            "credentialsAvailable": _has_credentials(r[0] or ""),
            "adapterRegistered": (r[2] or "") in _SOURCE_ADAPTERS,
        }
        for r in rows
    ]
    return {"status": "ok", "items": items, "count": len(items)}


async def task_flight_offer_list_sources(
    status: str = "",
    limit: int = 100,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_list_sources,
            status=_clean(status),
            limit=max(1, min(int(limit or 100), 500)),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.listSources failed: {e}",
                "items": [], "count": 0}


def _do_list_airlines(*, country_code: str, alliance: str, limit: int) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if country_code:
        clauses.append("country_code = %s")
        params.append(country_code)
    if alliance:
        clauses.append("alliance = %s")
        params.append(alliance)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql_text = (
        f"SELECT iata_code, icao_code, name, country_code, alliance, ingest_status "
        f"FROM vertex_airline {where} LIMIT {int(limit)}"
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql_text, tuple(params) if params else ())
        rows = _res or []
    items = [
        {"iataCode": r[0], "icaoCode": r[1], "name": r[2], "countryCode": r[3],
         "alliance": r[4], "ingestStatus": r[5]}
        for r in rows
    ]
    return {"status": "ok", "items": items, "count": len(items)}


def _do_source_health(*, limit: int) -> dict[str, Any]:
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT source_id, runs_total, runs_ok, runs_error, runs_fallback,
                   avg_latency_ms, offers_written_total, last_run_at, last_ok_at
              FROM {SOURCE_HEALTH_MV}
             ORDER BY runs_total DESC
             LIMIT {int(limit)}
            """,
        )
        rows = _res or []
    items = []
    for r in rows:
        runs_total = int(r[1] or 0)
        runs_ok = int(r[2] or 0)
        success_rate = (runs_ok / runs_total) if runs_total > 0 else 0.0
        items.append({
            "sourceId": r[0],
            "runsTotal": runs_total,
            "runsOk": runs_ok,
            "runsError": int(r[3] or 0),
            "runsFallback": int(r[4] or 0),
            "successRate": round(success_rate, 4),
            "avgLatencyMs": float(r[5]) if r[5] is not None else None,
            "offersWrittenTotal": int(r[6] or 0),
            "lastRunAt": r[7] or "",
            "lastOkAt": r[8] or "",
        })
    return {"status": "ok", "items": items, "count": len(items)}


def _do_cleanup_runs(*, retention_days: int) -> dict[str, Any]:
    cutoff_epoch = time.time() - max(1, int(retention_days)) * 86400
    cutoff_iso = datetime.fromtimestamp(cutoff_epoch, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"DELETE FROM {SOURCE_RUN_TABLE} WHERE observed_at < %s",
            (cutoff_iso,),
        )
        deleted = int((len(_res) if isinstance(_res, list) else 1) or 0)
    return {"status": "ok", "deleted": deleted, "cutoffAt": cutoff_iso,
            "retentionDays": int(retention_days)}


async def task_flight_offer_cleanup_runs(
    retentionDays: int = 90,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_cleanup_runs,
            retention_days=int(retentionDays or 90),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.cleanupRuns failed: {e}",
                "deleted": 0}


async def task_flight_offer_source_health(
    limit: int = 50,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_source_health,
            limit=max(1, min(int(limit or 50), 500)),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.sourceHealth failed: {e}",
                "items": [], "count": 0}


async def task_flight_offer_list_airlines(
    countryCode: str = "",
    alliance: str = "",
    limit: int = 200,
    **_: Any,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _do_list_airlines,
            country_code=_clean(countryCode).upper(),
            alliance=_clean(alliance),
            limit=max(1, min(int(limit or 200), 1000)),
        )
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"flight.offer.listAirlines failed: {e}",
                "items": [], "count": 0}
