"""Vessel registry, AIS tracking, and voyage handlers for BPMN + Zeebe."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math

from typing import Any
from uuid import uuid4

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:v3ss3l01.etzhayyim.com"
PUBLIC_DID = "did:web:vessel.etzhayyim.com"
NANOID = "v3ss3l01"

LABEL_COLLECTION = {
    "Ship": "com.etzhayyim.apps.vessel.ship",
    "Shipowner": "com.etzhayyim.apps.vessel.shipowner",
    "ShipRegistry": "com.etzhayyim.apps.vessel.shipRegistry",
    "VesselPosition": "com.etzhayyim.apps.vessel.vesselPosition",
    "Voyage": "com.etzhayyim.apps.vessel.voyage",
    "PortCall": "com.etzhayyim.apps.vessel.portCall",
    "OwnerLink": "com.etzhayyim.apps.vessel.ownerLink",
}

LABEL_TABLE = {
    "Ship": "vertex_vessel_ship",
    "Shipowner": "vertex_vessel_shipowner",
    "ShipRegistry": "vertex_vessel_ship_registry",
    "VesselPosition": "vertex_vessel_position",
    "Voyage": "vertex_vessel_voyage",
    "PortCall": "vertex_vessel_port_call",
    "OwnerLink": "vertex_vessel_owner_link",
}

PROMOTED_COLUMNS = {
    "Ship": {
        "ship_id": "shipId",
        "imo_number": "imoNumber",
        "mmsi": "mmsi",
        "name": "name",
        "vessel_type": "vesselType",
        "flag_state": "flagState",
        "latitude": "latitude",
        "longitude": "longitude",
    },
    "Shipowner": {"owner_id": "ownerId", "name": "name", "country": "country"},
    "ShipRegistry": {"registry_id": "registryId", "flag_state": "flagState", "authority_name": "authorityName"},
    "VesselPosition": {
        "position_id": "positionId",
        "imo_number": "imoNumber",
        "mmsi": "mmsi",
        "latitude": "latitude",
        "longitude": "longitude",
        "course": "course",
        "speed_knots": "speedKnots",
        "heading": "heading",
        "navigation_status": "navigationStatus",
        "destination": "destination",
        "eta": "eta",
        "received_at": "receivedAt",
        "source_did": "sourceDid",
    },
    "Voyage": {"voyage_id": "voyageId", "imo_number": "imoNumber", "port_locode": "portLocode"},
    "PortCall": {"call_id": "callId", "imo_number": "imoNumber", "port_locode": "portLocode"},
    "OwnerLink": {"link_id": "imoNumber", "imo_number": "imoNumber", "entity_did": "entityDid", "link_type": "linkType", "linked_at": "linkedAt"},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def _n(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _execute(table: str, row_dict: dict) -> dict | None:
    return get_kotoba_client().insert_row(table, row_dict)


def _label_for_collection(collection: str) -> str:
    for label, mapped in LABEL_COLLECTION.items():
        if mapped == collection:
            return label
    raise ValueError(f"unsupported vessel collection: {collection}")


def _select(collection: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    label = _label_for_collection(collection)
    table = LABEL_TABLE[label]
    rows = get_kotoba_client().select_where(table, "status", "active", limit=2000) # R0: Fetch a broad set; apply sorting, limit, offset in Python
    # Sort by created_date descending
    rows.sort(key=lambda r: r.get("created_date", ""), reverse=True)
    # Apply offset and limit
    end_index = offset + limit
    return [_inflate(row) for row in rows[offset:end_index]]


def _inflate(row: dict[str, Any]) -> dict[str, Any]:
    props = row.get("props")
    if isinstance(props, str) and props:
        try:
            parsed = json.loads(props)
            if isinstance(parsed, dict):
                return {**row, **parsed}
        except json.JSONDecodeError:
            pass
    return row


def _insert(label: str, props: dict[str, Any], id_field: str | None = None) -> dict[str, Any]:
    collection = LABEL_COLLECTION[label]
    table = LABEL_TABLE[label]
    rec_id = _s(props.get(id_field or "id") or _id(label.lower()))
    if id_field:
        props[id_field] = rec_id
    props.setdefault("nodeLabel", label)
    props.setdefault("createdAt", now_iso())
    props.setdefault("orgId", "anon")
    props.setdefault("userId", "anon")
    props.setdefault("actorId", OWNER_DID)
    vertex_id = f"at://{OWNER_DID}/com.etzhayyim.apps.vessel.{label}/{rec_id}"
    row_dict = {
        "vertex_id": vertex_id,
        "created_date": now_iso(), # Using now_iso for consistency
        "sensitivity_ord": 100,
        "owner_did": OWNER_DID,
        "rkey": rec_id,
        "repo": OWNER_DID, # Consistent with original values list
        "label": label,
        "did": props.get("did") or vertex_id,
        "collection": collection,
        "status": "active",
        "props": json.dumps(props, ensure_ascii=False, sort_keys=True),
        "actor_did": OWNER_DID,
        "org_did": "anon",
    }
    promoted = PROMOTED_COLUMNS[label]
    for column, prop_name in promoted.items():
        value = props.get(prop_name)
        if column in {"latitude", "longitude", "course", "speed_knots", "heading"}:
            value = _n(value)
        row_dict[column] = value

    _execute(table, row_dict)
    if label == "OwnerLink" and props.get("entityDid"):
        ship_vid = f"at://{OWNER_DID}/com.etzhayyim.apps.vessel.Ship/{props.get('imoNumber')}"
        _insert_edge("edge_vessel_owner_link", rec_id, ship_vid, _s(props.get("entityDid")), "ENTITY_OWNS", props)
    elif label == "PortCall":
        ship_vid = f"at://{OWNER_DID}/com.etzhayyim.apps.vessel.Ship/{props.get('imoNumber')}"
        _insert_edge("edge_vessel_port_call_endpoint", rec_id, ship_vid, vertex_id, "HAS_PORT_CALL", props)
    return {"ok": True, id_field or "id": rec_id}


def _insert_edge(table: str, key: str, src_vid: str, dst_vid: str, relation: str, props: dict[str, Any]) -> None:
    edge_id = f"at://{OWNER_DID}/{table}/{key}"
    row_dict = {
        "edge_id": edge_id,
        "created_date": now_iso(),
        "sensitivity_ord": 100,
        "owner_did": OWNER_DID,
        "src_vid": src_vid,
        "dst_vid": dst_vid,
        "relation": relation,
        "status": "active",
        "props": json.dumps(props, ensure_ascii=False, sort_keys=True),
        "actor_did": OWNER_DID,
        "org_did": "anon",
    }
    _execute(table, row_dict)


def _find(collection: str, predicate: Any) -> dict[str, Any] | None:
    for row in _select(collection, 10000, 0):
        if predicate(row):
            return row
    return None


def _list(label: str, limit: Any = 50, offset: Any = 0) -> dict[str, Any]:
    rows = _select(LABEL_COLLECTION[label], int(_n(limit, 50)), int(_n(offset)))
    return {"items": rows, "total": len(rows)}


def _register(label: str, id_field: str, **kwargs: Any) -> dict[str, Any]:
    return _insert(label, dict(kwargs), id_field)


def register_ship(**kwargs: Any) -> dict[str, Any]:
    return _register("Ship", "shipId", **kwargs)


def update_ship(**kwargs: Any) -> dict[str, Any]:
    return _register("Ship", "shipId", **kwargs)


def register_owner(**kwargs: Any) -> dict[str, Any]:
    return _register("Shipowner", "ownerId", **kwargs)


def transfer_ownership(**kwargs: Any) -> dict[str, Any]:
    return _register("Ship", "shipId", **kwargs)


def register_registry(**kwargs: Any) -> dict[str, Any]:
    return _register("ShipRegistry", "registryId", **kwargs)


def change_flag(**kwargs: Any) -> dict[str, Any]:
    return _register("Ship", "shipId", **kwargs)


def get_ship(shipId: Any = None, id: Any = None, imoNumber: Any = None, imo: Any = None, **_: Any) -> dict[str, Any]:
    key = _s(shipId or id)
    imo_key = _s(imoNumber or imo)
    row = _find(LABEL_COLLECTION["Ship"], lambda r: (key and _s(r.get("shipId")) == key) or (imo_key and _s(r.get("imoNumber")) == imo_key))
    return row or {"error": "not found"}


def list_ships(limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    return _list("Ship", limit, offset)


def search_ships(query: Any = None, q: Any = None, limit: Any = 50, **_: Any) -> dict[str, Any]:
    needle = _s(query or q).lower()
    rows = [
        r for r in _select(LABEL_COLLECTION["Ship"], 10000, 0)
        if needle in _s(r.get("name")).lower() or needle in _s(r.get("imoNumber")).lower() or needle in _s(r.get("mmsi")).lower()
    ][: int(_n(limit, 50))]
    return {"items": rows, "count": len(rows)}


def get_owner(ownerId: Any = None, id: Any = None, **_: Any) -> dict[str, Any]:
    key = _s(ownerId or id)
    row = _find(LABEL_COLLECTION["Shipowner"], lambda r: _s(r.get("ownerId")) == key)
    return row or {"error": "not found"}


def get_ship_owner(**kwargs: Any) -> dict[str, Any]:
    return get_owner(**kwargs)


def get_ships_by_flag(flagState: Any = None, limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    rows = _select(LABEL_COLLECTION["Ship"], 10000, int(_n(offset)))
    if _s(flagState):
        rows = [r for r in rows if _s(r.get("flagState")) == _s(flagState)]
    rows = rows[: int(_n(limit, 50))]
    return {"items": rows, "total": len(rows)}


def ingest_positions(positions: Any = None, **kwargs: Any) -> dict[str, Any]:
    batch = positions if isinstance(positions, list) else [kwargs]
    count = 0
    for pos in batch:
        if not isinstance(pos, dict):
            continue
        rec = {
            "positionId": _id("vpos"),
            "imoNumber": pos.get("imoNumber") or pos.get("imo") or "",
            "mmsi": pos.get("mmsi") or "",
            "latitude": _n(pos.get("latitude")),
            "longitude": _n(pos.get("longitude")),
            "course": pos.get("course"),
            "speedKnots": pos.get("speedKnots"),
            "heading": pos.get("heading"),
            "navigationStatus": pos.get("navigationStatus") or "unknown",
            "destination": pos.get("destination"),
            "eta": pos.get("eta"),
            "receivedAt": pos.get("receivedAt") or now_iso(),
            "sourceDid": pos.get("sourceDid") or f"{PUBLIC_DID}:source:ais",
        }
        _insert("VesselPosition", rec, "positionId")
        count += 1
    return {"ok": True, "ingested": count}


def get_vessel_position(imoNumber: Any = None, imo: Any = None, **_: Any) -> dict[str, Any]:
    imo_key = _s(imoNumber or imo)
    row = _find(LABEL_COLLECTION["VesselPosition"], lambda r: _s(r.get("imoNumber")) == imo_key)
    return {"vp": row} if row else {"error": "no position data", "imoNumber": imo_key}


def get_position_by_mmsi(mmsi: Any = None, **_: Any) -> dict[str, Any]:
    row = _find(LABEL_COLLECTION["VesselPosition"], lambda r: _s(r.get("mmsi")) == _s(mmsi))
    return {"vp": row} if row else {"error": "no position data", "mmsi": mmsi}


def list_vessels_in_area(minLat: Any = None, maxLat: Any = None, minLon: Any = None, maxLon: Any = None, south: Any = None, north: Any = None, west: Any = None, east: Any = None, limit: Any = 100, **_: Any) -> dict[str, Any]:
    lo_lat, hi_lat = _n(minLat if minLat is not None else south), _n(maxLat if maxLat is not None else north)
    lo_lon, hi_lon = _n(minLon if minLon is not None else west), _n(maxLon if maxLon is not None else east)
    rows = [
        r for r in _select(LABEL_COLLECTION["VesselPosition"], 10000, 0)
        if lo_lat <= _n(r.get("latitude")) <= hi_lat and lo_lon <= _n(r.get("longitude")) <= hi_lon
    ][: int(_n(limit, 100))]
    return {"items": [{"vp": r} for r in rows], "count": len(rows)}


def get_position_history(imoNumber: Any = None, imo: Any = None, limit: Any = 100, **_: Any) -> dict[str, Any]:
    imo_key = _s(imoNumber or imo)
    rows = [r for r in _select(LABEL_COLLECTION["VesselPosition"], 10000, 0) if _s(r.get("imoNumber")) == imo_key][: int(_n(limit, 100))]
    return {"items": [{"vp": r} for r in rows], "count": len(rows)}


def list_vessels_near_port(latitude: Any = None, longitude: Any = None, radiusDeg: Any = 0.1, limit: Any = 50, **_: Any) -> dict[str, Any]:
    lat, lon, radius = _n(latitude), _n(longitude), _n(radiusDeg, 0.1)
    rows = [
        r for r in _select(LABEL_COLLECTION["VesselPosition"], 10000, 0)
        if math.fabs(_n(r.get("latitude")) - lat) <= radius and math.fabs(_n(r.get("longitude")) - lon) <= radius
    ][: int(_n(limit, 50))]
    return {"port": {"latitude": lat, "longitude": lon}, "vessels": [{"vp": r} for r in rows], "count": len(rows)}


def register_voyage(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("voyageId", _id("voy"))
    kwargs.setdefault("status", "planned")
    return _insert("Voyage", dict(kwargs), "voyageId")


def update_voyage(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("updatedAt", now_iso())
    return _insert("Voyage", dict(kwargs), "voyageId")


def list_voyages(imoNumber: Any = None, imo: Any = None, limit: Any = 50, **_: Any) -> dict[str, Any]:
    imo_key = _s(imoNumber or imo)
    rows = _select(LABEL_COLLECTION["Voyage"], 10000, 0)
    if imo_key:
        rows = [r for r in rows if _s(r.get("imoNumber")) == imo_key]
    rows = rows[: int(_n(limit, 50))]
    return {"items": [{"v": r} for r in rows], "count": len(rows)}


def record_port_call(**kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("callId", _id("pcall"))
    kwargs.setdefault("status", "expected")
    return _insert("PortCall", dict(kwargs), "callId")


def list_port_calls(imoNumber: Any = None, portLocode: Any = None, limit: Any = 50, **_: Any) -> dict[str, Any]:
    rows = _select(LABEL_COLLECTION["PortCall"], 10000, 0)
    if _s(imoNumber):
        rows = [r for r in rows if _s(r.get("imoNumber")) == _s(imoNumber)]
    if _s(portLocode):
        rows = [r for r in rows if _s(r.get("portLocode")) == _s(portLocode)]
    rows = rows[: int(_n(limit, 50))]
    return {"items": [{"pc": r} for r in rows], "count": len(rows)}


def link_owner_entity(imoNumber: Any = None, entityDid: Any = None, ownerDid: Any = None, **_: Any) -> dict[str, Any]:
    rec = {"imoNumber": _s(imoNumber), "entityDid": _s(entityDid or ownerDid), "linkType": "ENTITY_OWNS", "linkedAt": now_iso()}
    return _insert("OwnerLink", rec, "imoNumber")


def get_vessel_chain(imoNumber: Any = None, imo: Any = None, **_: Any) -> dict[str, Any]:
    imo_key = _s(imoNumber or imo)
    return {
        "chain": {
            "ship": {"s": get_ship(imoNumber=imo_key)} if imo_key else None,
            "position": get_vessel_position(imoNumber=imo_key),
            "portCalls": list_port_calls(imoNumber=imo_key).get("items", []),
            "voyages": list_voyages(imoNumber=imo_key).get("items", []),
        }
    }


def seed_maritime(force: Any = False, **_: Any) -> dict[str, Any]:
    existing = len(_select(LABEL_COLLECTION["Ship"], 1, 0))
    if existing and not force:
        return {"ok": True, "skipped": True, "existingShips": existing}
    ships = [
        {"name": "Maersk Mc-Kinney Moller", "imoNumber": "9619907", "mmsi": "219018573", "vesselType": "container", "flagState": "DK", "latitude": 1.26, "longitude": 103.85},
        {"name": "MSC Irina", "imoNumber": "9930620", "mmsi": "255806650", "vesselType": "container", "flagState": "PA", "latitude": 31.35, "longitude": 121.50},
        {"name": "Ever Given", "imoNumber": "9811000", "mmsi": "353136000", "vesselType": "container", "flagState": "PA", "latitude": 34.67, "longitude": 135.44},
        {"name": "Front Alta", "imoNumber": "9834073", "mmsi": "538008785", "vesselType": "tanker", "flagState": "MH", "latitude": 26.64, "longitude": 50.17},
    ]
    for ship in ships:
        register_ship(**ship)
        ingest_positions(**ship)
    return {"ok": True, "ships": len(ships), "positions": len(ships)}


def get_dashboard(**_: Any) -> dict[str, Any]:
    return {"dashboard": {label: len(_select(collection, 10000, 0)) for label, collection in LABEL_COLLECTION.items() if label != "OwnerLink"}}
