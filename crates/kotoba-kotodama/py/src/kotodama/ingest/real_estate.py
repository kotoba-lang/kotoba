"""Real Estate read handlers for BPMN + Zeebe."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


def _clamp_limit(value: Any, fallback: int = 50) -> int:
    try:
        parsed = int(value if value is not None else fallback)
    except (TypeError, ValueError):
        parsed = fallback
    return max(1, min(parsed, 200))


def _offset(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        parsed = 0
    return max(0, parsed)






def search_listings(**kwargs: Any) -> dict[str, Any]:
    limit = _clamp_limit(kwargs.get("limit"), 50)
    offset = _offset(kwargs.get("offset"))
    where: list[str] = []
    params: list[Any] = []

    if kwargs.get("countryIso2"):
        where.append("country_iso2 = %s")
        params.append(str(kwargs["countryIso2"]).upper())
    if kwargs.get("city"):
        where.append("city = %s")
        params.append(str(kwargs["city"]))
    if kwargs.get("listingKind"):
        where.append("listing_kind = %s")
        params.append(str(kwargs["listingKind"]))
    if kwargs.get("offerStatus"):
        where.append("offer_status = %s")
        params.append(str(kwargs["offerStatus"]))
    if kwargs.get("currency"):
        where.append("currency = %s")
        params.append(str(kwargs["currency"]).upper())
    if kwargs.get("sourceId"):
        where.append("source_id = %s")
        params.append(str(kwargs["sourceId"]))
    if kwargs.get("canonicalPropertyKey"):
        where.append("canonical_property_key = %s")
        params.append(str(kwargs["canonicalPropertyKey"]))
    if kwargs.get("minPrice") is not None:
        where.append("price >= %s")
        params.append(float(kwargs["minPrice"]))
    if kwargs.get("maxPrice") is not None:
        where.append("price <= %s")
        params.append(float(kwargs["maxPrice"]))

    client = get_kotoba_client()
    # R0: search_listings uses q() to fetch all potential listings and then applies filtering, ordering, and limiting in Python.
    all_listings_datalog = '[:find (pull ?e [*]) :where [?e :vertex_real_estate_listing/last_seen_at]]'
    all_listings_result = client.q(all_listings_datalog)
    rows = [item[0] for item in all_listings_result] if all_listings_result else []

    # Apply filters in Python
    filtered_rows = []
    for row in rows:
        match = True
        if kwargs.get("countryIso2") and row.get("country_iso2") != str(kwargs["countryIso2"]).upper():
            match = False
        if kwargs.get("city") and row.get("city") != str(kwargs["city"]):
            match = False
        if kwargs.get("listingKind") and row.get("listing_kind") != str(kwargs["listingKind"]):
            match = False
        if kwargs.get("offerStatus") and row.get("offer_status") != str(kwargs["offerStatus"]):
            match = False
        if kwargs.get("currency") and row.get("currency") != str(kwargs["currency"]).upper():
            match = False
        if kwargs.get("sourceId") and row.get("source_id") != str(kwargs["sourceId"]):
            match = False
        if kwargs.get("canonicalPropertyKey") and row.get("canonical_property_key") != str(kwargs["canonicalPropertyKey"]):
            match = False
        if kwargs.get("minPrice") is not None and row.get("price", 0) < float(kwargs["minPrice"]):
            match = False
        if kwargs.get("maxPrice") is not None and row.get("price", 0) > float(kwargs["maxPrice"]):
            match = False
        if match:
            filtered_rows.append(row)

    # Apply ordering in Python (ORDER BY last_seen_at DESC NULLS LAST)
    filtered_rows.sort(key=lambda x: x.get("last_seen_at") or "", reverse=True)

    # Apply limit and offset in Python
    items = filtered_rows[offset : offset + limit]
    return {"items": items, "count": len(filtered_rows), "limit": limit, "offset": offset}


def get_property(**kwargs: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    property_vid = kwargs.get("propertyVid")
    canonical_key = kwargs.get("canonicalPropertyKey")
    if property_vid:
        prop_dict = client.select_first_where("vertex_real_estate_property", "vertex_id", str(property_vid))
        rows = [prop_dict] if prop_dict else []
    elif canonical_key:
        prop_dict = client.select_first_where("vertex_real_estate_property", "canonical_property_key", str(canonical_key))
        rows = [prop_dict] if prop_dict else []
    else:
        return {"error": "propertyVid or canonicalPropertyKey required"}
    if not rows:
        return {"error": "not found"}

    prop = rows[0]
    prop_vid = str(prop.get("vertex_id") or "")
    prop_key = str(prop.get("canonical_property_key") or "")
    listings: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []
    if kwargs.get("includeListings") is not False:
        # R0: get_property listings query uses q() for OR condition, then Python for ordering/limiting.
        listings_datalog = """
            [:find (pull ?e [*])
             :in $ ?prop_vid_val ?prop_key_val
             :where
               (or [?e :vertex_real_estate_listing/property_vid ?prop_vid_val]
                   [?e :vertex_real_estate_listing/canonical_property_key ?prop_key_val])]
        """
        listings_result = client.q(listings_datalog, prop_vid, prop_key)
        listings = [item[0] for item in listings_result] if listings_result else []
        listings.sort(key=lambda x: x.get("last_seen_at") or "", reverse=True) # ORDER BY last_seen_at DESC NULLS LAST
        listings = listings[:50] # LIMIT 50
    if kwargs.get("includeTransactions"):
        # R0: get_property transactions query uses q() then Python for ordering/limiting.
        transactions_datalog = """
            [:find (pull ?e [*])
             :in $ ?prop_vid_val
             :where
               [?e :vertex_real_estate_transaction/property_vid ?prop_vid_val]]
        """
        transactions_result = client.q(transactions_datalog, prop_vid)
        transactions = [item[0] for item in transactions_result] if transactions_result else []
        transactions.sort(key=lambda x: x.get("signed_at") or "", reverse=True) # ORDER BY signed_at DESC NULLS LAST
        transactions = transactions[:50] # LIMIT 50
    return {"property": prop, "listings": listings, "transactions": transactions}


def get_market_stats(**kwargs: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    limit = _clamp_limit(kwargs.get("limit"), 50)
    where = ["offer_status IN ('active', 'pending')"]
    params: list[Any] = []
    if kwargs.get("countryIso2"):
        where.append("country_iso2 = %s")
        params.append(str(kwargs["countryIso2"]).upper())
    if kwargs.get("city"):
        where.append("city = %s")
        params.append(str(kwargs["city"]))
    if kwargs.get("listingKind"):
        where.append("listing_kind = %s")
        params.append(str(kwargs["listingKind"]))
    if kwargs.get("currency"):
        where.append("currency = %s")
        params.append(str(kwargs["currency"]).upper())
    # R0: get_market_stats uses q() for aggregation and grouping, then Python for ordering/limiting.
    datalog_query_parts = [
        '[:find ?country_iso2 ?city ?listing_kind ?currency (count ?e) (avg ?price) (min ?price) (max ?price) (avg ?price_per_sqm) (max ?last_seen_at)',
        ':where',
        '   [?e :vertex_real_estate_listing/offer_status ?offer_status]',
        '   [(contains? #{"active" "pending"} ?offer_status)]',
        '   [?e :vertex_real_estate_listing/country_iso2 ?country_iso2]',
        '   [?e :vertex_real_estate_listing/city ?city]',
        '   [?e :vertex_real_estate_listing/listing_kind ?listing_kind]',
        '   [?e :vertex_real_estate_listing/currency ?currency]',
        '   [?e :vertex_real_estate_listing/price ?price]',
        '   [?e :vertex_real_estate_listing/price_per_sqm ?price_per_sqm]',
        '   [?e :vertex_real_estate_listing/last_seen_at ?last_seen_at]',
    ]

    if kwargs.get("countryIso2"):
        datalog_query_parts.append(f'   [(= ?country_iso2 "{str(kwargs["countryIso2"]).upper()}") ]')
    if kwargs.get("city"):
        datalog_query_parts.append(f'   [(= ?city "{str(kwargs["city"])})"] ')
    if kwargs.get("listingKind"):
        datalog_query_parts.append(f'   [(= ?listing_kind "{str(kwargs["listingKind"])})"] ')
    if kwargs.get("currency"):
        datalog_query_parts.append(f'   [(= ?currency "{str(kwargs["currency"]).upper()}") ]')

    datalog_query_parts.append(' :group-by ?country_iso2 ?city ?listing_kind ?currency]')

    datalog_query = "\n".join(datalog_query_parts)
    raw_results = client.q(datalog_query)

    results_dicts = []
    if raw_results:
        for row in raw_results:
            results_dicts.append({
                "country_iso2": row[0],
                "city": row[1],
                "listing_kind": row[2],
                "currency": row[3],
                "listing_count": int(row[4]), # COUNT is float in Datalog
                "avg_price": float(row[5]),
                "min_price": float(row[6]),
                "max_price": float(row[7]),
                "avg_price_per_sqm": float(row[8]),
                "latest_seen_at": row[9],
            })

    # ORDER BY COUNT(*) DESC
    results_dicts.sort(key=lambda x: x["listing_count"], reverse=True)

    # LIMIT
    items = results_dicts[:limit]
    return {"items": items, "count": len(results_dicts)}
