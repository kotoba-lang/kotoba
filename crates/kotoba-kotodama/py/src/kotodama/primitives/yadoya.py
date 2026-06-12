"""Yadoya catalog query primitives for BPMN/LangServer.

Moves the read-side hotel search/list logic out of the Cloudflare Worker.
Mutation flows already have BPMN definitions under 00-contracts/bpmn/com/etzhayyim/yadoya.
"""

from __future__ import annotations

from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


HOTEL_COLUMNS = (
    "vertex_id",
    "owner_did",
    "name",
    "country",
    "region",
    "city",
    "chain_did",
    "property_did",
    "isic_code",
    "price_jpy_min",
    "status",
    "created_at",
)


def _int(v: Any, default: int, *, min_value: int, max_value: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    return max(min_value, min(max_value, n))


def task_yadoya_search_hotels(
    country: str = "",
    region: str = "",
    city: str = "",
    chainDid: str = "",
    isicCode: str = "",
    priceJpyMax: Any = 0,
    limit: Any = 50,
    **_: Any,
) -> dict[str, Any]:
    """Filtered catalog search for com.etzhayyim.apps.yadoya.searchHotels.
    # R0: Multiple predicates and ORDER BY NULLS LAST are handled by fetching a broader set
    # and applying filtering/sorting in Python.
    """
    limit_n = _int(limit, 50, min_value=1, max_value=200)
    try:
        price_max = int(priceJpyMax or 0)
    except (TypeError, ValueError):
        price_max = 0

    # Fetch all published hotels up to a reasonable limit, then filter in Python
    all_hotels = get_kotoba_client().select_where(
        "vertex_yadoya_hotel",
        "status",
        "published",
        columns=HOTEL_COLUMNS,
        limit=2000, # Per instruction: fetch a broader set with limit=2000
    )

    filtered_hotels = []
    for hotel in all_hotels:
        if country and hotel.get("country") != country:
            continue
        if region and hotel.get("region") != region:
            continue
        if city and hotel.get("city") != city:
            continue
        if chainDid and hotel.get("chain_did") != chainDid:
            continue
        if isicCode and hotel.get("isic_code") != isicCode:
            continue
        if price_max > 0 and hotel.get("price_jpy_min", 0) > price_max:
            continue
        filtered_hotels.append(hotel)

    # Apply ORDER BY region NULLS LAST, city NULLS LAST, name NULLS LAST
    # Sorting key for NULLS LAST: (is_none_field, field_value)
    filtered_hotels.sort(
        key=lambda x: (
            x.get("region") is None, x.get("region"),
            x.get("city") is None, x.get("city"),
            x.get("name") is None, x.get("name"),
        )
    )

    hotels = filtered_hotels[:limit_n]
    return {"hotels": hotels, "total": len(hotels)}


def task_yadoya_list_hotels(
    region: str = "",
    chainDid: str = "",
    limit: Any = 50,
    offset: Any = 0,
    **_: Any,
) -> dict[str, Any]:
    """Unfiltered/paged catalog listing for com.etzhayyim.apps.yadoya.listHotels.
    # R0: Multiple predicates, ORDER BY NULLS LAST, OFFSET, and LIMIT are handled by
    # fetching a broader set and applying filtering/sorting/paging in Python.
    """
    limit_n = _int(limit, 50, min_value=1, max_value=500)
    offset_n = _int(offset, 0, min_value=0, max_value=100_000)

    # Fetch all published hotels up to a reasonable limit, then filter and page in Python
    all_hotels = get_kotoba_client().select_where(
        "vertex_yadoya_hotel",
        "status",
        "published",
        columns=HOTEL_COLUMNS,
        limit=2000, # Per instruction: fetch a broader set with limit=2000
    )

    filtered_hotels = []
    for hotel in all_hotels:
        if region and hotel.get("region") != region:
            continue
        if chainDid and hotel.get("chain_did") != chainDid:
            continue
        filtered_hotels.append(hotel)

    # Apply ORDER BY region NULLS LAST, city NULLS LAST, name NULLS LAST
    filtered_hotels.sort(
        key=lambda x: (
            x.get("region") is None, x.get("region"),
            x.get("city") is None, x.get("city"),
            x.get("name") is None, x.get("name"),
        )
    )

    # Apply OFFSET and LIMIT
    paged_hotels = filtered_hotels[offset_n : offset_n + limit_n]

    return {"hotels": paged_hotels, "total": len(filtered_hotels), "offset": offset_n, "limit": limit_n}


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    worker.task(
        task_type="xrpc.com.etzhayyim.apps.yadoya.searchHotels",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yadoya_search_hotels)
    worker.task(
        task_type="xrpc.com.etzhayyim.apps.yadoya.listHotels",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yadoya_list_hotels)
