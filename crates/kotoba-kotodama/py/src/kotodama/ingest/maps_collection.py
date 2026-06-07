"""Maps collection source/job/dataset handlers for BPMN + Zeebe."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any
from kotodama.kotoba_datomic import get_kotoba_client
from uuid import uuid4


OWNER_DID = "did:web:maps.etzhayyim.com"
APP_ID = "maps"

MAPS_ENTITY_LABELS = {
    "adminArea": "AdminArea",
    "geoAlias": "GeoAlias",
    "layerCoordinator": "LayerCoordinator",
    "naturalZone": "NaturalZone",
    "source": "Source",
    "dataset": "Dataset",
    "verticalZone": "VerticalZone",
    "asset": "PhysicalAsset",
    "deviceBinding": "DeviceBinding",
    "twinState": "TwinState",
    "sensorReading": "SensorReading",
    "sensorAlert": "SensorAlert",
    "simulation": "Simulation",
    "simulationResult": "SimulationResult",
    "healthAssessment": "HealthAssessment",
    "maintenancePlan": "MaintenancePlan",
    "spatialEvent": "SpatialEvent",
    "spatialVersion": "SpatialVersion",
    "spatialRelation": "SpatialRelation",
    "displayLayer": "DisplayLayer",
    "visionResult": "VisionResult",
    "satelliteScene": "SatelliteScene",
    "ownership": "OwnsProperty",
}

GEO_SCHEMES = {
    "iso3166-1": {"name": "ISO 3166-1 alpha-2", "dim": "2d", "scope": "global"},
    "iso3166-2": {"name": "ISO 3166-2", "dim": "2d", "scope": "global"},
    "jis-x0401": {"name": "JIS X 0401", "dim": "2d", "scope": "jp"},
    "jis-x0402": {"name": "JIS X 0402", "dim": "2d", "scope": "jp"},
    "fips": {"name": "FIPS State+County", "dim": "2d", "scope": "us"},
    "h3": {"name": "H3 Hexagonal", "dim": "2d", "scope": "global"},
    "s2": {"name": "S2 Geometry", "dim": "2d", "scope": "global"},
    "geohash": {"name": "Geohash", "dim": "2d", "scope": "global"},
    "pluscode": {"name": "Plus Code / OLC", "dim": "2d", "scope": "global"},
    "mgrs": {"name": "MGRS", "dim": "2d", "scope": "global"},
    "maidenhead": {"name": "Maidenhead Locator", "dim": "2d", "scope": "global"},
    "utm": {"name": "UTM Zone", "dim": "2d", "scope": "global"},
    "flight-level": {"name": "ICAO Flight Level", "dim": "3d", "scope": "global"},
    "icao-fir": {"name": "ICAO FIR", "dim": "3d", "scope": "global"},
    "atmo-layer": {"name": "Atmospheric Layer", "dim": "3d", "scope": "global"},
    "elevation": {"name": "WGS84 Ellipsoid Height", "dim": "3d", "scope": "global"},
    "depth-band": {"name": "Underground Depth Band", "dim": "3d", "scope": "global"},
    "infra-depth": {"name": "Infrastructure Layer", "dim": "3d", "scope": "maps"},
    "marine-zone": {"name": "EEZ / Maritime Zone", "dim": "2d", "scope": "global"},
    "unlocode": {"name": "UN/LOCODE", "dim": "2d", "scope": "global"},
    "icao-airport": {"name": "ICAO Airport Code", "dim": "2d", "scope": "global"},
    "iata-airport": {"name": "IATA Airport Code", "dim": "2d", "scope": "global"},
}

INFRA_DEPTHS = {
    "water": 1.2,
    "sewage": 3.0,
    "gas": 1.5,
    "electric": 0.8,
    "telecom": 0.6,
    "subway": 15.0,
    "districtHeating": 1.0,
}

STREET_CHUNK_STAGE_ORDER = [
    "sequence_select",
    "frame_admit",
    "chunk_assign",
    "coverage_score",
    "reconstruct",
    "bake",
    "publish",
]

OSM_POI_TYPES = {
    "restaurant": '["amenity"="restaurant"]',
    "cafe": '["amenity"="cafe"]',
    "bar": '["amenity"="bar"]',
    "fastFood": '["amenity"="fastFood"]',
    "hotel": '["tourism"="hotel"]',
    "hostel": '["tourism"="hostel"]',
    "motel": '["tourism"="motel"]',
    "guestHouse": '["tourism"="guestHouse"]',
    "supermarket": '["shop"="supermarket"]',
    "convenience": '["shop"="convenience"]',
    "clothes": '["shop"="clothes"]',
    "bakery": '["shop"="bakery"]',
    "pharmacy": '["amenity"="pharmacy"]',
    "hospital": '["amenity"="hospital"]',
    "clinic": '["amenity"="clinic"]',
    "dentist": '["amenity"="dentist"]',
    "school": '["amenity"="school"]',
    "university": '["amenity"="university"]',
    "library": '["amenity"="library"]',
    "museum": '["tourism"="museum"]',
    "park": '["leisure"="park"]',
    "playground": '["leisure"="playground"]',
    "fuel": '["amenity"="fuel"]',
    "parking": '["amenity"="parking"]',
    "atm": '["amenity"="atm"]',
    "bank": '["amenity"="bank"]',
    "postOffice": '["amenity"="postOffice"]',
    "police": '["amenity"="police"]',
    "fireStation": '["amenity"="fireStation"]',
    "placeOfWorship": '["amenity"="placeOfWorship"]',
    "cinema": '["amenity"="cinema"]',
    "theatre": '["amenity"="theatre"]',
    "swimmingPool": '["leisure"="swimmingPool"]',
    "sportsCentre": '["leisure"="sportsCentre"]',
    "viewpoint": '["tourism"="viewpoint"]',
    "attraction": '["tourism"="attraction"]',
}

WIKIDATA_PROFILE_LABELS = {
    "corp": "LegalEntity", "river": "River", "mountain": "Mountain", "lake": "Lake", "island": "Spot",
    "airport": "Airport", "university": "Spot", "volcano": "Mountain", "glacier": "Spot", "bridge": "Spot",
    "dam": "Spot", "castle": "Spot", "monastery": "Spot", "stadium": "Spot", "theatre": "Spot",
    "railwayStation": "Station", "hospitalWd": "Hospital", "schoolWd": "School", "libraryWd": "Library",
    "government": "Spot", "embassy": "Spot", "prison": "Spot", "cemeteryWd": "Cemetery", "temple": "Spot",
    "church": "Spot", "metroStation": "Station", "busStation": "Station", "shoppingMall": "Spot",
    "skyscraper": "Spot", "lighthouse": "Spot", "hotSpring": "Spot", "airline": "Spot", "winery": "Spot",
    "observatory": "Spot", "waterfall": "Spot", "beachWd": "Beach", "swimmingPool": "Spot",
    "casino": "Spot", "garden": "Park", "amusementPark": "Park", "resort": "Hotel", "distillery": "Spot",
    "bakeryWd": "Spot", "restaurantWd": "Restaurant", "brewery": "Spot", "monasteryVar": "Monument",
    "powerPlant": "Spot", "nuclear": "Spot", "refineryWd": "Spot", "factory": "Spot", "mosqueWd": "Spot",
    "synagogueWd": "Spot", "cathedral": "Spot", "palace": "Spot", "ruinWd": "Spot", "artMuseum": "Museum",
    "concertHall": "Spot", "caveWd": "Spot", "fjord": "Spot", "reef": "Spot", "strait": "Waterway",
    "bay": "Spot", "valley": "Spot", "hill": "Mountain", "peninsula": "Spot", "isthmus": "Spot",
    "plaza": "Spot", "historicDist": "Spot", "memorialPlace": "Monument", "trainLine": "Railway",
    "marina": "Port", "powerSubst": "Spot", "gasStation": "Spot", "gate": "Spot", "tower": "Spot",
    "sportsField": "Spot", "musicVenue": "Spot", "bookstore": "Spot", "nightclub": "Spot",
    "antiquariat": "Spot", "pharmacyWd": "Pharmacy", "fitness": "SportsCentre", "radioStation": "Spot",
    "tvStation": "Spot", "bookshop": "Spot", "prominentPlace": "Spot", "heritage": "Spot",
    "archSite": "Spot", "natReserve": "Spot", "nationalPark": "Spot", "ferryTerminal": "Port",
    "busStopWd": "BusStop", "protectedArea": "Spot", "canal": "Waterway", "lightRail": "Railway",
    "subwayLine": "Railway", "artGalleryWd": "Museum", "shrine": "Spot", "warehouse": "Spot",
    "officeBuilding": "Spot", "townHall": "Spot", "courthouse": "Spot", "chapel": "Spot",
    "obelisk": "Monument", "fountainWd": "Spot", "vineyard": "Farmland", "orchard": "Farmland",
    "mine": "Spot", "quarry": "Spot", "evStation": "EvCharger", "dataCenter": "Spot",
    "windFarm": "Spot", "solarPark": "Spot", "spaceport": "Airport", "medicalLab": "Spot",
    "clinicWd": "Clinic", "maternityHosp": "Hospital", "bedAndBreakfast": "Hotel", "motelWd": "Hotel",
    "hostelWd": "Hotel", "ryokan": "Hotel", "campsite": "Spot", "steelMill": "Spot",
    "paperMill": "Spot", "cementPlant": "Spot", "chemicalPlant": "Spot", "glassFactory": "Spot",
    "reservoirWd": "Lake", "pond": "Lake", "marshland": "Spot", "plateau": "Mountain",
    "tundra": "Spot", "biogasPlant": "Spot", "powerSubstation": "Spot", "railwayYard": "Spot",
    "dryDock": "Port", "windmill": "Spot", "watermill": "Spot", "radioTelescope": "Spot",
    "busRoute": "BusRoute", "trainLineWd": "Railway", "cableCar": "Spot", "funicular": "Spot",
    "teaGarden": "Farmland", "ricePaddy": "Farmland", "fishery": "Spot", "oilFieldWd": "Spot",
    "saltPond": "Spot", "greenhouse": "Spot", "bakehouse": "Spot", "streetWd": "Road",
    "housingEstate": "Spot", "pier": "Spot", "parliamentBldg": "Spot", "primarySchool": "Spot",
    "middleSchool": "Spot", "highSchoolWd": "Spot", "boardingSchool": "Spot", "prisonWd": "Spot",
    "gurdwara": "Spot", "aquariumWd": "Spot", "botanicalGarden": "Spot", "basilica": "Spot",
    "subwayStation": "Station", "seaport": "Port", "borough": "AdminArea", "hamletWd": "Spot",
    "neighborhood": "AdminArea", "publicSquare": "Spot", "skiResort": "Spot", "cityPark": "Spot",
    "shoppingCenter": "Spot", "policeStationWd": "Spot", "battlefield": "Spot", "conventionCtr": "Spot",
    "musicSchool": "Spot", "airForceBase": "Spot", "busStationWd": "Station", "microbrewery": "Spot",
    "cityGate": "Spot", "bunker": "Spot", "arsenal": "Spot", "farmersMarket": "Spot",
    "waterTreatment": "Spot", "sewageTreatment": "Spot", "navalBase": "Spot", "operaHouse": "Spot",
    "restAreaWd": "Spot", "tollPlaza": "Spot", "lighthouseWd2": "Spot", "miningSite": "Spot",
    "museumShip": "Spot", "maritimeStrait": "Spot", "archipelago": "Spot", "peninsulaWd": "Spot",
    "capeWd": "Spot", "lagoon": "Lake", "estuary": "Spot", "researchInst": "Spot",
    "scientificLab": "Spot", "artistStudio": "Spot", "observatory2": "Spot", "footballStadium": "Spot",
    "canyon": "Spot", "wetland": "Spot", "atoll": "Spot", "themePark": "Spot", "hotSpringWd": "Spot",
    "waterpark": "Spot", "fortress": "Spot", "iceberg": "Spot", "baseballStadium": "Spot",
    "velodromeWd": "Spot", "publicLibrary": "Spot", "kindergartenWd": "Spot", "cricketGround": "Spot",
    "tramStop": "Station", "monasteryWd": "Spot", "funeralHomeWd": "Spot", "crematoriumWd": "Spot",
    "ferryRouteWd": "Spot", "powerLineWd": "PowerLine", "radioAntenna": "Spot", "fishingHarbor": "Port",
    "artificialIsland": "Spot", "amusementRideWd": "Spot",
}

WIKIDATA_WORLD_TOTALS = {
    "corp": 500000, "river": 250000, "mountain": 500000, "lake": 100000, "island": 100000,
    "airport": 50000, "university": 30000, "volcano": 2000, "glacier": 200000, "bridge": 500000,
    "dam": 50000, "castle": 50000, "monastery": 30000, "stadium": 20000, "theatre": 30000,
    "railwayStation": 300000, "hospitalWd": 200000, "schoolWd": 500000, "libraryWd": 100000,
    "government": 50000, "embassy": 5000, "prison": 20000, "cemeteryWd": 200000, "temple": 100000,
    "church": 1000000, "metroStation": 10000, "busStation": 5000, "shoppingMall": 50000,
    "skyscraper": 20000, "lighthouse": 20000, "hotSpring": 10000, "heritage": 100000,
    "archSite": 100000, "natReserve": 30000, "nationalPark": 10000, "ferryTerminal": 8000,
    "busStopWd": 500000, "protectedArea": 200000, "canal": 50000, "lightRail": 10000,
    "subwayLine": 5000, "airline": 5000, "winery": 30000, "observatory": 5000, "waterfall": 30000,
    "beachWd": 50000, "swimmingPool": 20000, "casino": 10000, "garden": 30000,
    "amusementPark": 5000, "resort": 50000, "distillery": 8000, "bakeryWd": 30000,
    "restaurantWd": 100000, "brewery": 15000, "monasteryVar": 30000, "powerPlant": 10000,
    "nuclear": 500, "refineryWd": 2000, "factory": 100000, "mosqueWd": 30000,
    "synagogueWd": 5000, "cathedral": 8000, "palace": 10000, "ruinWd": 20000,
    "artMuseum": 30000, "concertHall": 3000, "caveWd": 50000, "fjord": 1000,
    "reef": 10000, "strait": 3000, "bay": 30000, "valley": 50000, "hill": 100000,
    "peninsula": 5000, "isthmus": 500, "plaza": 20000, "historicDist": 30000,
    "memorialPlace": 50000, "trainLine": 10000, "marina": 20000, "powerSubst": 50000,
    "gasStation": 500000, "gate": 30000, "tower": 50000, "sportsField": 30000,
    "musicVenue": 20000, "bookstore": 15000, "nightclub": 10000, "antiquariat": 5000,
    "pharmacyWd": 200000, "fitness": 30000, "radioStation": 10000, "tvStation": 5000,
    "bookshop": 10000, "prominentPlace": 50000,
}

OVERPASS_LABELS = [
    "Building", "Airport", "Station", "Port", "Road", "Railway", "AdminArea", "EvCharger",
    "InfraSegment", "Waterway", "River", "Mountain", "BusStop", "Parking", "PowerLine",
    "Pipeline", "Substation", "Cemetery", "Monument", "Hospital", "School", "Museum", "Cafe",
    "Restaurant", "Hotel", "Bank", "PostOffice", "Pharmacy", "Supermarket", "Cinema", "Library",
    "Park", "Viewpoint", "GolfCourse", "Zoo", "SportsCentre", "Kindergarten", "Marketplace",
    "FireStation", "PoliceStation", "Beach", "Forest", "Industrial", "Commercial", "Residential",
    "Farmland", "Wood", "Grass", "Meadow", "Village", "Hamlet", "PowerPlant", "WindTurbine",
    "SolarFarm", "Antenna", "Mosque", "Synagogue", "Ruins", "Castle", "Archaeological",
    "MilitaryBase", "FireHydrant", "Defibrillator", "EmergencyPhone", "ShopClothes", "ShopBooks",
    "ShopFurniture", "ShopElectronics", "BikeShop", "Optician", "JewelryShop", "University",
    "College", "TownHall", "Courthouse", "Embassy", "FerryTerminal", "Toilets", "FastFood",
    "Bar", "Nightclub", "Church", "BuddhistTemple", "Shrine", "HinduTemple", "SikhTemple",
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def _n(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    if sql.strip().upper() == "FLUSH": return 0
    client = get_kotoba_client()
    try:
        client.q(sql, params)
        return 1
    except Exception:
        return 0


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    client = get_kotoba_client()
    results = client.q(sql, params)
    # Assume results from Kotoba q() are dicts directly for SELECT queries.
    if results and isinstance(results[0], dict):
        return [_inflate(r) for r in results]
    elif results and isinstance(results[0], tuple):
        # We don't have description, just return tuples if needed, though dicts expected
        pass
    return [_inflate(r) if isinstance(r, dict) else r for r in results]


def _row(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = _rows(sql, params)
    return rows[0] if rows else None


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


def _normalize_stage(value: Any) -> str:
    stage = _s(value)
    return stage if stage in STREET_CHUNK_STAGE_ORDER else "sequence_select"


def _stage_index(stage: str) -> int:
    try:
        return STREET_CHUNK_STAGE_ORDER.index(stage) + 1
    except ValueError:
        return 1


def _next_seq(table: str) -> int:
    if True:
        client = get_kotoba_client()
        _res = client.q(f"SELECT COALESCE(MAX(_seq), 0) + 1 AS seq FROM {table}")
        row = (_res[0] if _res else None)
        return int(row[0] if row else 1)


def _to_db_timestamp(value: str) -> str:
    return value.replace("T", " ").replace("Z", "")


def _insert_spatial(entity: str, props: dict[str, Any], rec_id: str | None = None) -> dict[str, Any]:
    label = MAPS_ENTITY_LABELS.get(entity, entity[:1].upper() + entity[1:])
    collection = f"com.etzhayyim.apps.maps.{entity}"
    rkey = _s(rec_id or props.get(f"{entity}Id") or props.get("id") or props.get("name") or _id(entity))
    vertex_id = f"at://{OWNER_DID}/{collection}/{rkey}"
    row_props = {**props, "nodeLabel": props.get("nodeLabel") or label, "createdAt": props.get("createdAt") or now_iso()}
    try:
        _execute(
            """INSERT INTO vertex_spatial
            (vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo, label, did,
             name, display_name, description, category, lat, lng, status, source, source_did,
             node_label, country, region_id, props, actor_did, org_did)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                vertex_id,
                _next_seq("vertex_spatial"),
                today(),
                300,
                OWNER_DID,
                rkey,
                OWNER_DID,
                label,
                row_props.get("did") or vertex_id,
                row_props.get("name"),
                row_props.get("displayName") or row_props.get("name"),
                row_props.get("description"),
                row_props.get("category") or row_props.get("sourceType") or row_props.get("format"),
                _n(row_props.get("lat") or row_props.get("latitude")),
                _n(row_props.get("lng") or row_props.get("lon") or row_props.get("longitude")),
                row_props.get("status") or "active",
                row_props.get("source"),
                row_props.get("sourceDid"),
                row_props.get("nodeLabel") or label,
                row_props.get("country"),
                row_props.get("regionId") or row_props.get("region"),
                _json(row_props),
                OWNER_DID,
                "anon",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        if "duplicate" not in str(exc).lower() and "unique" not in str(exc).lower():
            raise
    return {"ok": True, f"{entity}Id": rkey}


def _osm_category_from_tags(tags: dict[str, Any]) -> dict[str, str]:
    for key in ("amenity", "shop", "tourism", "leisure", "office", "craft"):
        if tags.get(key):
            return {"category": key, "subcategory": _s(tags.get(key))}
    return {"category": "other", "subcategory": "unknown"}


def _parse_overpass_response(body: Any, source_did: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(_s(body)) if not isinstance(body, dict) else body
    except json.JSONDecodeError:
        return []
    elements = data.get("elements") if isinstance(data, dict) else None
    if not isinstance(elements, list):
        return []
    pois: list[dict[str, Any]] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        tags = el.get("tags") if isinstance(el.get("tags"), dict) else {}
        if not tags.get("name"):
            continue
        center = el.get("center") if isinstance(el.get("center"), dict) else {}
        lat = _n(el.get("lat") or center.get("lat"))
        lon = _n(el.get("lon") or center.get("lon"))
        if lat == 0 and lon == 0:
            continue
        category = _osm_category_from_tags(tags)
        address = ", ".join(_s(tags.get(k)) for k in ("addr:housenumber", "addr:street", "addr:city", "addr:postcode", "addr:country") if tags.get(k))
        pois.append({
            "poiId": _id("poi"),
            "osmId": f"{_s(el.get('type'))}/{_s(el.get('id'))}",
            "name": tags.get("name"),
            "category": category["category"],
            "subcategory": category["subcategory"],
            "lat": lat,
            "lon": lon,
            "address": address,
            "phone": tags.get("phone") or tags.get("contact:phone") or "",
            "website": tags.get("website") or tags.get("contact:website") or "",
            "openingHours": tags.get("openingHours") or "",
            "wheelchair": tags.get("wheelchair") or "",
            "sourceDid": source_did,
            "collectedAt": now_iso(),
            "orgId": "anon",
            "userId": "anon",
            "actorId": source_did,
        })
    return pois


def _parse_wikidata_response(body: Any, source_did: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(_s(body)) if not isinstance(body, dict) else body
    except json.JSONDecodeError:
        return []
    bindings = data.get("results", {}).get("bindings") if isinstance(data, dict) else None
    if not isinstance(bindings, list):
        return []
    pois: list[dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        name = _s(binding.get("itemLabel", {}).get("value") if isinstance(binding.get("itemLabel"), dict) else "")
        if not name:
            continue
        lat = _n(binding.get("lat", {}).get("value") if isinstance(binding.get("lat"), dict) else None)
        lon = _n(binding.get("lon", {}).get("value") if isinstance(binding.get("lon"), dict) else None)
        if lat == 0 and lon == 0:
            continue
        item = _s(binding.get("item", {}).get("value") if isinstance(binding.get("item"), dict) else "")
        wid = item.replace("http://www.wikidata.org/entity/", "")
        osm_id = _s(binding.get("osmId", {}).get("value") if isinstance(binding.get("osmId"), dict) else "")
        pois.append({
            "poiId": _id("poi"),
            "osmId": f"relation/{osm_id}" if osm_id else f"wikidata/{wid}",
            "name": name,
            "category": "wikidata",
            "subcategory": "entity",
            "lat": lat,
            "lon": lon,
            "address": "",
            "phone": _s(binding.get("phone", {}).get("value") if isinstance(binding.get("phone"), dict) else ""),
            "website": _s(binding.get("website", {}).get("value") if isinstance(binding.get("website"), dict) else ""),
            "openingHours": "",
            "wheelchair": "",
            "sourceDid": source_did,
            "collectedAt": now_iso(),
            "orgId": "anon",
            "userId": "anon",
            "actorId": source_did,
        })
    return pois


def _normalize_job_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "jobId": row.get("job_id") or row.get("jobId") or row.get("rkey"),
        "sourceId": row.get("source_id") or row.get("sourceId"),
        "datasetType": row.get("dataset_type") or row.get("datasetType"),
        "region": row.get("region"),
        "priority": row.get("priority"),
        "status": row.get("status"),
        "phase": _i(row.get("phase"), 0),
        "stage": row.get("stage"),
        "progressPct": _n(row.get("progress_pct") or row.get("progressPct"), 0),
        "pipelineType": row.get("pipeline_type") or row.get("pipelineType"),
        "sequenceId": row.get("sequence_id") or row.get("sequenceId"),
        "chunkKey": row.get("chunk_key") or row.get("chunkKey"),
        "chunkSizeMeters": _i(row.get("chunk_size_meters") or row.get("chunkSizeMeters"), 0),
        "recordsCount": _i(row.get("records_count") or row.get("recordsCount"), 0),
        "coverageRatio": _n(row.get("coverage_ratio") or row.get("coverageRatio"), 0),
        "recommendedChunkClass": row.get("recommended_chunk_class") or row.get("recommendedChunkClass"),
        "errorMessage": row.get("error_message") or row.get("errorMessage"),
        "createdAt": row.get("created_at") or row.get("createdAt"),
        "updatedAt": row.get("updated_at") or row.get("updatedAt"),
    }


def _insert_job_event(event: dict[str, Any]) -> None:
    timestamp = now_iso()
    job_id = _s(event.get("jobId"))
    _execute(
        """INSERT INTO vertex_maps_job
        (vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo, label, did,
         name, display_name, category, status, job_id, source_id, dataset_type, region, priority,
         phase, stage, progress_pct, pipeline_type, sequence_id, chunk_key, chunk_size_meters,
         bbox_json, stage_order_json, coverage_threshold_ratio, heading_threshold_deg,
         frame_threshold_count, frame_count, records_count, coverage_ratio, heading_span_deg,
         view_cluster_count, occlusion_risk, dynamic_object_risk, recommended_chunk_class,
         error_message, props, created_at, updated_at, actor_did, org_did)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'MapsJob', %s,
                %s, %s, 'MapsJob', %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s)""",
        (
            f"maps-job:{job_id}:{_id('evt')}",
            _next_seq("vertex_maps_job"),
            _to_db_timestamp(timestamp),
            300,
            OWNER_DID,
            job_id,
            OWNER_DID,
            OWNER_DID,
            job_id,
            job_id,
            _s(event.get("status")),
            job_id,
            event.get("sourceId"),
            event.get("datasetType"),
            event.get("region"),
            event.get("priority"),
            _i(event.get("phase")),
            event.get("stage"),
            _n(event.get("progressPct")),
            event.get("pipelineType"),
            event.get("sequenceId"),
            event.get("chunkKey"),
            _i(event.get("chunkSizeMeters")),
            event.get("bboxJson"),
            event.get("stageOrderJson"),
            _n(event.get("coverageThresholdRatio")),
            _n(event.get("headingThresholdDeg")),
            _i(event.get("frameThresholdCount")),
            _i(event.get("frameCount")),
            _i(event.get("recordsCount")),
            _n(event.get("coverageRatio")),
            _n(event.get("headingSpanDeg")),
            _i(event.get("viewClusterCount")),
            _n(event.get("occlusionRisk")),
            _n(event.get("dynamicObjectRisk")),
            event.get("recommendedChunkClass"),
            event.get("errorMessage"),
            _json(event),
            event.get("createdAt") or timestamp,
            event.get("updatedAt") or timestamp,
            OWNER_DID,
            "anon",
        ),
    )


def register_source(**kwargs: Any) -> dict[str, Any]:
    if not kwargs.get("name") or not kwargs.get("sourceUrl"):
        return {"error": "name and sourceUrl required"}
    source_id = _id("src")
    _insert_spatial("source", {
        "sourceId": source_id,
        "name": kwargs.get("name"),
        "sourceUrl": kwargs.get("sourceUrl"),
        "sourceType": kwargs.get("sourceType") or "api",
        "format": kwargs.get("format") or "geojson",
        "ttlHours": _i(kwargs.get("ttlHours"), 24),
        "region": kwargs.get("region") or "global",
        "status": "active",
        "orgId": "anon",
        "userId": "anon",
        "actorId": APP_ID,
    }, source_id)
    return {"sourceId": source_id, "status": "active"}


def list_sources(**_: Any) -> list[dict[str, Any]]:
    return []


def create_collection_job(**kwargs: Any) -> dict[str, Any]:
    if not kwargs.get("sourceId"):
        return {"error": "sourceId required"}
    job_id = _id("mcj")
    stage = _normalize_stage(kwargs.get("stage"))
    chunk_size = _i(kwargs.get("chunkSizeMeters"), 50)
    if chunk_size not in {25, 50, 100}:
        chunk_size = 50
    pipeline_type = _s(kwargs.get("pipelineType") or "street_chunk")
    event = {
        "jobId": job_id,
        "sourceId": kwargs.get("sourceId"),
        "datasetType": kwargs.get("datasetType") or "geojson",
        "region": kwargs.get("region") or "global",
        "priority": kwargs.get("priority") or "normal",
        "status": "pending",
        "phase": _stage_index(stage),
        "stage": stage,
        "progressPct": 0,
        "pipelineType": pipeline_type,
        "sequenceId": kwargs.get("sequenceId"),
        "chunkKey": kwargs.get("chunkKey"),
        "chunkSizeMeters": chunk_size,
        "bboxJson": _json(kwargs.get("bbox") or {}),
        "stageOrderJson": _json(STREET_CHUNK_STAGE_ORDER),
        "coverageThresholdRatio": _n(kwargs.get("coverageThresholdRatio"), 0.55),
        "headingThresholdDeg": _n(kwargs.get("headingThresholdDeg"), 90),
        "frameThresholdCount": _i(kwargs.get("frameThresholdCount"), 24),
        "nodeLabel": "MapsJob",
        "createdAt": now_iso(),
        "orgId": "anon",
        "userId": "anon",
        "actorId": APP_ID,
    }
    _insert_spatial("job", event, job_id)
    _insert_job_event(event)
    return {
        "jobId": job_id,
        "status": "pending",
        "stage": stage,
        "pipelineType": pipeline_type,
        "chunkSizeMeters": chunk_size,
        "sequenceId": kwargs.get("sequenceId"),
        "chunkKey": kwargs.get("chunkKey"),
    }


def advance_job(**kwargs: Any) -> dict[str, Any]:
    if not kwargs.get("jobId"):
        return {"error": "jobId required"}
    stage = _normalize_stage(kwargs.get("stage") or kwargs.get("phase"))
    status = _s(kwargs.get("status") or "running")
    event = {
        "jobId": kwargs.get("jobId"),
        "status": status,
        "phase": _stage_index(stage),
        "stage": stage,
        "progressPct": _n(kwargs.get("progressPct"), 0),
        "errorMessage": kwargs.get("errorMessage"),
        "recordsCount": _i(kwargs.get("recordsCount"), 0),
        "frameCount": _i(kwargs.get("frameCount"), 0),
        "coverageRatio": _n(kwargs.get("coverageRatio"), 0),
        "headingSpanDeg": _n(kwargs.get("headingSpanDeg"), 0),
        "viewClusterCount": _i(kwargs.get("viewClusterCount"), 0),
        "occlusionRisk": _n(kwargs.get("occlusionRisk"), 0),
        "dynamicObjectRisk": _n(kwargs.get("dynamicObjectRisk"), 0),
        "recommendedChunkClass": kwargs.get("recommendedChunkClass"),
        "sequenceId": kwargs.get("sequenceId"),
        "chunkKey": kwargs.get("chunkKey"),
        "chunkSizeMeters": _i(kwargs.get("chunkSizeMeters"), 0),
        "updatedAt": now_iso(),
        "nodeLabel": "MapsJob",
        "orgId": "anon",
        "userId": "anon",
        "actorId": APP_ID,
    }
    _insert_spatial("job", event, _s(kwargs.get("jobId")))
    _insert_job_event(event)
    return {
        "jobId": kwargs.get("jobId"),
        "status": status,
        "stage": stage,
        "progressPct": _n(kwargs.get("progressPct"), 0),
        "coverageRatio": _n(kwargs.get("coverageRatio"), 0),
        "recommendedChunkClass": kwargs.get("recommendedChunkClass"),
    }


def list_jobs(limit: Any = 50, offset: Any = 0, sourceId: Any = None, status: Any = None, pipelineType: Any = None, stage: Any = None, chunkSizeMeters: Any = None, **_: Any) -> dict[str, Any]:
    clauses = []
    params: list[Any] = []
    if sourceId:
        clauses.append("source_id = %s")
        params.append(sourceId)
    if status:
        clauses.append("status = %s")
        params.append(status)
    if pipelineType:
        clauses.append("pipeline_type = %s")
        params.append(pipelineType)
    if stage:
        clauses.append("stage = %s")
        params.append(stage)
    if chunkSizeMeters is not None:
        clauses.append("chunk_size_meters = %s")
        params.append(_i(chunkSizeMeters))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = _rows(f"SELECT * FROM vertex_maps_job {where} ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST", tuple(params))
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = _normalize_job_row(row)
        job_id = _s(item.get("jobId"))
        if job_id and job_id not in latest:
            latest[job_id] = item
    start = _i(offset)
    cap = min(_i(limit, 50), 100)
    jobs = list(latest.values())[start:start + cap]
    return {"jobs": jobs, "total": len(latest), "offset": start, "limit": cap}


def get_job_status(jobId: Any = None, **_: Any) -> dict[str, Any]:
    if not jobId:
        return {"error": "jobId required"}
    row = _row(
        "SELECT * FROM vertex_maps_job WHERE job_id = %s ORDER BY updated_at DESC NULLS LAST, _seq DESC LIMIT 1",
        (_s(jobId),),
    )
    return _normalize_job_row(row) if row else {"error": "not found"}


def store_dataset(**kwargs: Any) -> dict[str, Any]:
    if not kwargs.get("name"):
        return {"error": "name required"}
    dataset_id = _id("ds")
    _insert_spatial("dataset", {
        "datasetId": dataset_id,
        "name": kwargs.get("name"),
        "jobId": kwargs.get("jobId"),
        "format": kwargs.get("format") or "geojson",
        "recordCount": _i(kwargs.get("recordCount"), 0),
        "region": kwargs.get("region") or "global",
        "sourceDid": kwargs.get("sourceDid"),
        "sizeBytes": _i(kwargs.get("sizeBytes"), 0),
        "status": "available",
        "orgId": "anon",
        "userId": "anon",
        "actorId": APP_ID,
    }, dataset_id)
    return {"datasetId": dataset_id, "status": "available"}


def get_dataset(datasetId: Any = None, **_: Any) -> dict[str, Any]:
    if not datasetId:
        return {"error": "datasetId required"}
    return {"error": "not found"}


def list_datasets(**_: Any) -> list[dict[str, Any]]:
    return []


def get_pipeline_stats(**_: Any) -> dict[str, Any]:
    rows = _rows("SELECT * FROM vertex_maps_job ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST")
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = _normalize_job_row(row)
        job_id = _s(item.get("jobId"))
        if job_id and job_id not in latest:
            latest[job_id] = item
    statuses = [_s(r.get("status")).lower() for r in latest.values()]
    return {
        "sourcesTotal": 0,
        "sourcesActive": 0,
        "jobsTotal": len(latest),
        "jobsPending": statuses.count("pending"),
        "jobsRunning": statuses.count("running"),
        "jobsCompleted": statuses.count("completed"),
        "jobsFailed": statuses.count("failed"),
        "datasetsTotal": 0,
        "poisTotal": 0,
        "poisOsm": 0,
        "poisWikidata": 0,
    }


def _complete_collection_job(job_id: str, records_count: int) -> None:
    _insert_spatial("collectionJob", {
        "id": job_id,
        "status": "completed",
        "phase": 2,
        "recordsCount": records_count,
        "completedAt": now_iso(),
        "nodeLabel": "MapsCollectionJob",
        "orgId": "anon",
        "userId": "anon",
        "actorId": APP_ID,
    }, job_id)


def import_osm_pois(jobId: Any = None, overpassResponse: Any = None, **_: Any) -> dict[str, Any]:
    if not jobId or not overpassResponse:
        return {"error": "jobId and overpassResponse required"}
    source_did = f"did:web:{APP_ID}.etzhayyim.com:source:osm"
    pois = _parse_overpass_response(overpassResponse, source_did)
    job_id = _s(jobId)
    for poi in pois:
        _insert_spatial("poi", {**poi, "nodeLabel": "MapsPOI", "jobId": job_id}, _s(poi.get("poiId")))
    _complete_collection_job(job_id, len(pois))
    return {"jobId": job_id, "imported": len(pois), "source": "osm"}


def import_wikidata_pois(jobId: Any = None, sparqlResponse: Any = None, **_: Any) -> dict[str, Any]:
    if not jobId or not sparqlResponse:
        return {"error": "jobId and sparqlResponse required"}
    source_did = f"did:web:{APP_ID}.etzhayyim.com:source:wikidata"
    pois = _parse_wikidata_response(sparqlResponse, source_did)
    job_id = _s(jobId)
    for poi in pois:
        _insert_spatial("poi", {**poi, "nodeLabel": "MapsPOI", "jobId": job_id}, _s(poi.get("poiId")))
    _complete_collection_job(job_id, len(pois))
    return {"jobId": job_id, "imported": len(pois), "source": "wikidata"}


def search_poi(limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    cap = min(_i(limit, 50), 100)
    start = _i(offset)
    return {"pois": [], "total": 0, "offset": start, "limit": cap}


def get_poi(poiId: Any = None, **_: Any) -> dict[str, Any]:
    if not poiId:
        return {"error": "poiId required"}
    return {"error": "not found"}


def list_poi_types(**_: Any) -> dict[str, Any]:
    types = [{"type": key, "overpassFilter": value} for key, value in OSM_POI_TYPES.items()]
    return {"poiTypes": types, "total": len(types)}


def register_writer_profiles(**_: Any) -> dict[str, Any]:
    writers = [
        {
            "sourceId": "src-osm",
            "name": "OpenStreetMap",
            "did": "did:web:maps.etzhayyim.com:source:osm",
            "status": "available",
        },
        {
            "sourceId": "src-wikidata",
            "name": "Wikidata",
            "did": "did:web:maps.etzhayyim.com:source:wikidata",
            "status": "available",
        },
    ]
    return {"writers": writers, "total": len(writers)}


def _normalize_region_codes(codes: Any) -> dict[str, str]:
    if isinstance(codes, dict):
        return {_s(k): _s(v) for k, v in codes.items() if _s(k) and _s(v)}
    out: dict[str, str] = {}
    if isinstance(codes, list):
        for item in codes:
            text = _s(item)
            if ":" not in text:
                continue
            scheme, code = text.split(":", 1)
            if scheme and code:
                out[scheme] = code
    return out


def register_region(
    displayName: Any = None,
    displayNameEn: Any = None,
    lat: Any = None,
    lng: Any = None,
    adminLevel: Any = 3,
    parentRegionId: Any = None,
    codes: Any = None,
    **_: Any,
) -> dict[str, Any]:
    display_name = _s(displayName)
    if not display_name or lat is None or lng is None:
        return {"error": "displayName, lat, lng required"}
    region_id = f"r_{_id('r')}"
    canonical_did = f"at://{OWNER_DID}/com.etzhayyim.apps.maps.adminArea/adminArea:{region_id}"
    code_map = _normalize_region_codes(codes)
    record: dict[str, Any] = {
        "regionId": region_id,
        "displayName": display_name,
        "displayNameEn": _s(displayNameEn),
        "lat": _n(lat),
        "lng": _n(lng),
        "adminLevel": _i(adminLevel, 3),
        "parentRegionId": _s(parentRegionId),
        "canonicalDid": canonical_did,
        "nodeId": f"adminArea:{region_id}",
        "nodeLabel": "AdminArea",
        "createdAt": now_iso(),
        "orgId": "anon",
        "userId": "anon",
        "actorId": APP_ID,
    }
    for scheme, code in code_map.items():
        record[scheme.replace("-", "_")] = code
    _insert_spatial("adminArea", record, f"adminArea:{region_id}")
    aliases = 0
    for scheme, code in code_map.items():
        alias_did = f"at://{OWNER_DID}/com.etzhayyim.apps.maps.geoAlias/geoAlias:{scheme}:{code}"
        _insert_spatial(
            "geoAlias",
            {
                "scheme": scheme,
                "code": code,
                "regionId": region_id,
                "aliasDid": alias_did,
                "canonicalDid": canonical_did,
                "dim": GEO_SCHEMES.get(scheme, {}).get("dim", "2d"),
                "nodeId": f"geoAlias:{scheme}:{code}",
                "nodeLabel": "GeoAlias",
                "createdAt": now_iso(),
                "orgId": "anon",
                "userId": "anon",
                "actorId": APP_ID,
            },
            f"geoAlias:{scheme}:{code}",
        )
        aliases += 1
    try:
        _execute("FLUSH")
    except Exception:
        pass
    return {"regionId": region_id, "status": "created", "lat": _n(lat), "aliases": aliases}


def resolve_geo_alias(scheme: Any = None, code: Any = None, **_: Any) -> dict[str, Any]:
    scheme_s = _s(scheme)
    code_s = _s(code)
    if not scheme_s or not code_s:
        return {"error": "scheme and code required", "scheme": scheme_s, "code": code_s}
    row = next(
        (
            r for r in _rows(
                """SELECT vertex_id, rkey, region_id, props
                   FROM vertex_spatial
                   WHERE label = 'GeoAlias'
                   ORDER BY created_date DESC NULLS LAST
                   LIMIT 1000""",
            )
            if _s(r.get("scheme")) == scheme_s and _s(r.get("code")) == code_s
        ),
        None,
    )
    if not row:
        return {"error": "not found", "scheme": scheme_s, "code": code_s}
    return {
        "regionId": row.get("regionId") or row.get("region_id"),
        "canonicalDid": row.get("canonicalDid"),
        "aliasDid": row.get("aliasDid"),
    }


def list_geo_aliases(limit: Any = 50, offset: Any = 0, scheme: Any = None, **_: Any) -> list[dict[str, Any]]:
    cap = max(1, min(_i(limit, 50), 100))
    off = max(0, _i(offset, 0))
    scheme_s = _s(scheme)
    if scheme_s:
        rows = _rows(
            """SELECT vertex_id, rkey, region_id, props
               FROM vertex_spatial
               WHERE label = 'GeoAlias'
               ORDER BY created_date DESC NULLS LAST
               LIMIT 1000""",
        )
        return [row for row in rows if _s(row.get("scheme")) == scheme_s][off:off + cap]
    return _rows(
        f"""SELECT vertex_id, rkey, region_id, props
           FROM vertex_spatial
           WHERE label = 'GeoAlias'
           ORDER BY created_date DESC NULLS LAST
           LIMIT {int(cap)} OFFSET {int(off)}""",
        (),
    )


def list_geo_schemes(**_: Any) -> list[dict[str, Any]]:
    return [{"id": key, **value} for key, value in GEO_SCHEMES.items()]


def _list_spatial_label(label: str, limit: Any = 50, offset: Any = 0, filter_field: str | None = None, filter_value: Any = None) -> list[dict[str, Any]]:
    cap = max(1, min(_i(limit, 50), 100))
    off = max(0, _i(offset, 0))
    rows = _rows(
        """SELECT vertex_id, rkey, region_id, props
           FROM vertex_spatial
           WHERE label = %s
           ORDER BY created_date DESC NULLS LAST
           LIMIT 1000""",
        (label,),
    )
    if filter_field and filter_value is not None and _s(filter_value) != "":
        rows = [row for row in rows if _s(row.get(filter_field)) == _s(filter_value)]
    return rows[off:off + cap]


def list_vertical_zones(limit: Any = 50, offset: Any = 0, zoneType: Any = None, **_: Any) -> list[dict[str, Any]]:
    return _list_spatial_label("VerticalZone", limit, offset, "zoneType", zoneType)


def list_natural_zones(limit: Any = 50, offset: Any = 0, zoneType: Any = None, **_: Any) -> list[dict[str, Any]]:
    return _list_spatial_label("NaturalZone", limit, offset, "zoneType", zoneType)


def list_layer_coordinators(limit: Any = 50, offset: Any = 0, **_: Any) -> list[dict[str, Any]]:
    return _list_spatial_label("LayerCoordinator", limit, offset)


def resolve_zones3d(lat: Any = None, lng: Any = None, altMin: Any = None, altMax: Any = None, limit: Any = 20, **_: Any) -> dict[str, Any]:
    if lat is None or lng is None:
        return {"error": "lat and lng required"}
    cap = max(1, min(_i(limit, 20), 50))
    lat_n = _n(lat)
    lng_n = _n(lng)
    results: list[dict[str, Any]] = []
    threshold = 1.0
    admin_rows = _rows(
        f"""SELECT vertex_id, rkey, region_id, lat, lng, props
           FROM vertex_spatial
           WHERE label = 'AdminArea'
             AND lat BETWEEN %s AND %s
             AND lng BETWEEN %s AND %s
           ORDER BY created_date DESC NULLS LAST
           LIMIT {int(cap)}""",
        (lat_n - threshold, lat_n + threshold, lng_n - threshold, lng_n + threshold),
    )
    results.extend({"type": "adminArea", **row} for row in admin_rows)
    if altMin is not None or altMax is not None:
        alt_min = _n(altMin, 0)
        alt_max = _n(altMax, alt_min)
        vertical_rows = _list_spatial_label("VerticalZone", 1000, 0)
        for row in vertical_rows:
            min_alt = row.get("minAlt")
            max_alt = row.get("maxAlt")
            if min_alt is None or max_alt is None:
                continue
            if _n(min_alt) <= alt_max and _n(max_alt) >= alt_min:
                results.append({"type": "verticalZone", **row})
            if len(results) >= cap:
                break
    return {"lat": lat_n, "lng": lng_n, "altMin": altMin, "altMax": altMax, "zones": results[:cap]}


def crawler_locations(job_status: Any = None, requested_statuses: Any = None, **_: Any) -> dict[str, Any]:
    statuses = requested_statuses
    if statuses is None and job_status is not None:
        statuses = [_s(part).strip() for part in _s(job_status).split(",") if _s(part).strip()]
    if statuses is None:
        statuses = []
    return {
        "points": [],
        "fetched_at": now_iso(),
        "job_count": 0,
        "result_count": 0,
        "queried_jobs": 0,
        "queried_results": 0,
        "errors": [],
        "requested_statuses": statuses,
    }


def search_places(query: Any = None, limit: Any = 50, offset: Any = 0, **_: Any) -> list[dict[str, Any]]:
    cap = max(1, min(_i(limit, 50), 100))
    off = max(0, _i(offset, 0))
    q = _s(query)
    labels = ["Place", "Spot", "Station", "AdminArea", "Airport", "Port", "Mountain", "River", "Lake"]
    rows: list[dict[str, Any]] = []
    for label in labels:
        rows.extend(_list_spatial_label(label, 1000, 0))
    if q:
        rows = [
            row for row in rows
            if q in _s(row.get("name") or row.get("label") or row.get("displayName") or row.get("display_name"))
        ]
    return rows[off:off + cap]


def get_place(placeId: Any = None, **_: Any) -> dict[str, Any]:
    place_id = _s(placeId)
    if not place_id:
        return {"error": "placeId required"}
    row = _row(
        """SELECT vertex_id, rkey, region_id, props
           FROM vertex_spatial
           WHERE label = 'Place' AND rkey = %s
           ORDER BY created_date DESC NULLS LAST
           LIMIT 1""",
        (place_id,),
    )
    return row or {"error": "not found"}


def graph_traverse(startId: Any = None, limit: Any = 50, **_: Any) -> list[dict[str, Any]] | dict[str, str]:
    start_id = _s(startId)
    if not start_id:
        return {"error": "startId required"}
    cap = max(1, min(_i(limit, 50), 100))
    rows: list[dict[str, Any]] = []
    for label in ("Place", "Spot", "Building"):
        rows.extend(
            _rows(
                f"""SELECT vertex_id, rkey, region_id, props
                   FROM vertex_spatial
                   WHERE label = %s AND rkey = %s
                   ORDER BY created_date DESC NULLS LAST
                   LIMIT {int(cap)}""",
                (label, start_id),
            )
        )
    return rows[:cap]


def graph_neighbors(nodeId: Any = None, limit: Any = 50, **_: Any) -> list[dict[str, Any]] | dict[str, str]:
    node_id = _s(nodeId)
    if not node_id:
        return {"error": "nodeId required"}
    cap = max(1, min(_i(limit, 50), 100))
    for label in ("Place", "Spot", "Building"):
        row = _row(
            """SELECT vertex_id, rkey, region_id, props
               FROM vertex_spatial
               WHERE label = %s AND rkey = %s
               ORDER BY created_date DESC NULLS LAST
               LIMIT 1""",
            (label, node_id),
        )
        if row:
            return [{"relType": "self", "node": row}][:cap]
    return []


def search_resources(query: Any = None, labels: Any = None, limit: Any = 50, **_: Any) -> list[dict[str, Any]] | dict[str, str]:
    q = _s(query)
    if not q:
        return {"error": "query required"}
    cap = max(1, min(_i(limit, 50), 100))
    if isinstance(labels, list) and labels:
        label_list = [_s(label) for label in labels if _s(label)]
    else:
        label_list = ["Place", "Spot", "Building", "Road", "Station", "Airport", "Port"]
    rows: list[dict[str, Any]] = []
    for label in label_list:
        rows.extend(_list_spatial_label(label, 1000, 0))
    return [
        row for row in rows
        if q in _s(row.get("name") or row.get("label") or row.get("displayName") or row.get("display_name"))
    ][:cap]


def _register_entity(entity: str, label: str, id_prefix: str, required_field: str, **kwargs: Any) -> dict[str, Any]:
    if not _s(kwargs.get(required_field)):
        return {"error": f"{required_field} required"}
    node_id = f"{id_prefix}:{_id(id_prefix)}"
    record = {
        **kwargs,
        "nodeId": node_id,
        "nodeLabel": label,
        "createdAt": now_iso(),
        "orgId": _s(kwargs.get("orgId"), "anon"),
        "userId": _s(kwargs.get("userId"), "anon"),
        "actorId": APP_ID,
    }
    _insert_spatial(entity, record, node_id)
    return {"nodeId": node_id, "status": "created"}


def _list_entity(label: str, limit: Any = 50, offset: Any = 0, filter_field: str | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    return _list_spatial_label(label, limit, offset, filter_field, kwargs.get(filter_field) if filter_field else None)


def _get_entity(label: str, id_field: str, **kwargs: Any) -> dict[str, Any]:
    entity_id = _s(kwargs.get(id_field))
    if not entity_id:
        return {"error": f"{id_field} required"}
    row = _row(
        """SELECT vertex_id, rkey, region_id, props
           FROM vertex_spatial
           WHERE label = %s AND rkey = %s
           ORDER BY created_date DESC NULLS LAST
           LIMIT 1""",
        (label, entity_id),
    )
    return row or {"error": "not found"}


def _within_radius(row: dict[str, Any], lat: float, lng: float, radius_km: float) -> bool:
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(0.01, abs(__import__("math").cos(lat * __import__("math").pi / 180))))
    row_lat = row.get("lat")
    row_lng = row.get("lng")
    if row_lat is None or row_lng is None:
        return False
    lat_n = _n(row_lat)
    lng_n = _n(row_lng)
    return lat - dlat <= lat_n <= lat + dlat and lng - dlng <= lng_n <= lng + dlng


def infra_query(infraType: Any = None, lat: Any = None, lng: Any = None, radiusKm: Any = 1, limit: Any = 50, **_: Any) -> list[dict[str, Any]]:
    cap = max(1, min(_i(limit, 50), 100))
    rows = _list_spatial_label("InfraNetwork", 1000, 0)
    infra_type = _s(infraType)
    if infra_type:
        rows = [row for row in rows if _s(row.get("infraType")) == infra_type]
    if lat is not None and lng is not None:
        lat_n = _n(lat)
        lng_n = _n(lng)
        rows = [row for row in rows if _within_radius(row, lat_n, lng_n, _n(radiusKm, 1))]
    return rows[:cap]


def infra_cross_section(lat: Any = None, lng: Any = None, radiusM: Any = 100, **_: Any) -> dict[str, Any]:
    if lat is None or lng is None:
        return {"error": "lat and lng required"}
    lat_n = _n(lat)
    lng_n = _n(lng)
    radius_m = _n(radiusM, 100)
    segments = [row for row in _list_spatial_label("InfraSegment", 1000, 0) if _within_radius(row, lat_n, lng_n, radius_m / 1000)]
    infra_types = ["water", "sewage", "gas", "electric", "telecom", "subway", "districtHeating"]
    colors = {"water": "#3b82f6", "sewage": "#78716c", "gas": "#f59e0b", "electric": "#eab308", "telecom": "#10b981", "subway": "#6366f1", "districtHeating": "#ef4444"}
    return {
        "lat": lat_n,
        "lng": lng_n,
        "radiusM": radius_m,
        "layers": [
            {
                "infraType": infra_type,
                "depthM": INFRA_DEPTHS.get(infra_type, 1.0),
                "color": colors.get(infra_type),
                "segments": [row for row in segments if _s(row.get("category") or row.get("infraType")) == infra_type],
            }
            for infra_type in infra_types
        ],
        "totalSegments": len(segments),
    }


def register_air_route(**kwargs: Any) -> dict[str, Any]:
    if not _s(kwargs.get("name")):
        return {"error": "name required"}
    route_did = _s(kwargs.get("routeDid")) or f"did:web:maps.etzhayyim.com:air-route:{_id('air')}"
    node_id = f"airRoute:{_id('air')}"
    _insert_spatial("airRoute", {**kwargs, "routeDid": route_did, "nodeId": node_id, "nodeLabel": "AirRoute", "createdAt": now_iso(), "orgId": _s(kwargs.get("orgId"), "anon"), "userId": _s(kwargs.get("userId"), "anon"), "actorId": APP_ID}, node_id)
    return {"nodeId": node_id, "routeDid": route_did, "status": "created"}


def list_air_routes(limit: Any = 50, offset: Any = 0, routeDid: Any = None, originAirportDid: Any = None, destinationAirportDid: Any = None, operatorDid: Any = None, flightNumber: Any = None, **_: Any) -> dict[str, Any]:
    cap = max(1, min(_i(limit, 50), 500))
    off = max(0, _i(offset, 0))
    rows = _list_spatial_label("AirRoute", 1000, 0)
    filters = {"routeDid": routeDid, "originAirportDid": originAirportDid, "destinationAirportDid": destinationAirportDid, "operatorDid": operatorDid, "flightNumber": flightNumber}
    for key, value in filters.items():
        if _s(value):
            rows = [row for row in rows if _s(row.get(key) or (row.get("did") if key == "routeDid" else "")) == _s(value)]
    total = len(rows)
    return {"routes": rows[off:off + cap], "total": total, "offset": off, "limit": cap}


def spot_search(query: Any = None, category: Any = None, lat: Any = None, lng: Any = None, radiusKm: Any = 5, limit: Any = 50, **_: Any) -> list[dict[str, Any]]:
    cap = max(1, min(_i(limit, 50), 100))
    rows = _list_spatial_label("Spot", 1000, 0)
    q = _s(query)
    cat = _s(category)
    if q:
        rows = [row for row in rows if q in _s(row.get("name")) or q in _s(row.get("description"))]
    if cat:
        rows = [row for row in rows if _s(row.get("category")) == cat]
    if lat is not None and lng is not None:
        rows = [row for row in rows if _within_radius(row, _n(lat), _n(lng), _n(radiusKm, 5))]
    return rows[:cap]


def spot_recommend(lat: Any = None, lng: Any = None, radiusKm: Any = 3, limit: Any = 10, **_: Any) -> list[dict[str, Any]] | dict[str, str]:
    if lat is None or lng is None:
        return {"error": "lat and lng required"}
    cap = max(1, min(_i(limit, 10), 50))
    return [
        row for row in _list_spatial_label("Spot", 1000, 0)
        if row.get("rating") is not None and _within_radius(row, _n(lat), _n(lng), _n(radiusKm, 3))
    ][:cap]


def _make_register(entity: str, label: str, id_prefix: str, required_field: str):
    return lambda **kwargs: _register_entity(entity, label, id_prefix, required_field, **kwargs)


def _make_list(label: str, filter_field: str | None = None):
    return lambda **kwargs: _list_entity(label, filter_field=filter_field, **kwargs)


def _make_get(label: str, id_field: str):
    return lambda **kwargs: _get_entity(label, id_field, **kwargs)


for _fn_name, _entity, _label, _id_prefix, _required in (
    ("register_route", "route", "Route", "route", "name"),
    ("register_road", "road", "Road", "road", "name"),
    ("register_railway", "railway", "Railway", "railway", "name"),
    ("register_sea_route", "seaRoute", "SeaRoute", "seaRoute", "name"),
    ("register_bus_route", "busRoute", "BusRoute", "busRoute", "operator"),
    ("register_infra_network", "infraNetwork", "InfraNetwork", "infraNet", "infraType"),
    ("register_infra_segment", "infraSegment", "InfraSegment", "infraSeg", "networkId"),
    ("register_infra_node", "infraNode", "InfraNode", "infraNode", "networkId"),
    ("register_infra_incident", "infraIncident", "InfraIncident", "infraInc", "incidentType"),
    ("register_spot", "spot", "Spot", "spot", "name"),
    ("register_river", "river", "River", "river", "name"),
    ("register_lake", "lake", "Lake", "lake", "name"),
    ("register_coastline", "coastline", "Coastline", "coastline", "name"),
    ("register_mountain", "mountain", "Mountain", "mountain", "name"),
    ("register_maritime_zone", "maritimeZone", "MaritimeZone", "maritimeZone", "name"),
    ("register_admin_area", "adminArea", "AdminArea", "adminArea", "name"),
):
    globals()[_fn_name] = _make_register(_entity, _label, _id_prefix, _required)


for _fn_name, _label, _filter in (
    ("list_routes", "Route", "routeType"),
    ("list_roads", "Road", "roadClass"),
    ("list_railways", "Railway", "operator"),
    ("list_sea_routes", "SeaRoute", "vesselClass"),
    ("list_bus_routes", "BusRoute", "operator"),
    ("list_infra_networks", "InfraNetwork", "infraType"),
    ("list_infra_segments", "InfraSegment", "networkId"),
    ("list_infra_nodes", "InfraNode", "networkId"),
    ("list_infra_incidents", "InfraIncident", "status"),
    ("list_spots", "Spot", "category"),
    ("list_rivers", "River", None),
    ("list_lakes", "Lake", None),
    ("list_coastlines", "Coastline", "coastType"),
    ("list_mountains", "Mountain", None),
    ("list_maritime_zones", "MaritimeZone", "zoneType"),
    ("list_admin_areas", "AdminArea", "adminLevel"),
):
    globals()[_fn_name] = _make_list(_label, _filter)


get_route = _make_get("Route", "routeId")
get_spot = _make_get("Spot", "spotId")


def register_asset(**kwargs: Any) -> dict[str, Any]:
    if not _s(kwargs.get("name")):
        return {"error": "name required"}
    if not _s(kwargs.get("assetType")):
        return {"error": "assetType required"}
    return _register_entity("asset", "PhysicalAsset", "asset", "name", **kwargs)


def device_bind(deviceDid: Any = None, assetId: Any = None, protocol: Any = "mqtt", **_: Any) -> dict[str, Any]:
    if not deviceDid or not assetId:
        return {"error": "deviceDid and assetId required"}
    node_id = f"devbind:{_id('devbind')}"
    _insert_spatial("deviceBinding", {"nodeId": node_id, "deviceDid": deviceDid, "assetId": assetId, "protocol": protocol or "mqtt", "status": "active", "boundAt": now_iso(), "nodeLabel": "DeviceBinding", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
    return {"nodeId": node_id, "status": "bound"}


def twin_state_update(entityType: Any = None, entityId: Any = None, status: Any = "active", healthScore: Any = None, propertiesJson: Any = None, **_: Any) -> dict[str, Any]:
    if not entityType or not entityId:
        return {"error": "entityType and entityId required"}
    node_id = f"twin:{entityType}:{entityId}"
    _insert_spatial("twinState", {"nodeId": node_id, "entityType": entityType, "entityId": entityId, "status": status or "active", "healthScore": healthScore, "propertiesJson": propertiesJson, "condition": status or "normal", "nodeLabel": "TwinState", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
    return {"nodeId": node_id, "status": "updated"}


def occupancy_update(buildingId: Any = None, floorNumber: Any = 0, occupancy: Any = None, **_: Any) -> dict[str, Any]:
    if not buildingId:
        return {"error": "buildingId required"}
    node_id = f"twin:occupancy:{buildingId}:{floorNumber or 0}"
    _insert_spatial("twinState", {"nodeId": node_id, "entityType": "occupancy", "entityId": buildingId, "status": "active", "propertiesJson": _json({"floor": floorNumber, "occupancy": occupancy}), "nodeLabel": "TwinState", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
    return {"status": "updated"}


def sensor_ingest(sensorId: Any = None, readings: Any = None, **_: Any) -> dict[str, Any]:
    if not sensorId or not isinstance(readings, list) or not readings:
        return {"error": "sensorId and readings required"}
    node_id = f"sensorReading:{_id('sr')}"
    _insert_spatial("sensorReading", {"nodeId": node_id, "sensorId": sensorId, "readingsJson": _json(readings), "batchSize": len(readings), "ingestedAt": now_iso(), "nodeLabel": "SensorReading", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
    return {"status": "ingested", "sensorId": sensorId, "count": len(readings)}


def sensor_query(sensorId: Any = None, limit: Any = 20, **_: Any) -> list[dict[str, Any]] | dict[str, str]:
    if not sensorId:
        return {"error": "sensorId required"}
    return [row for row in _list_spatial_label("SensorReading", 1000, 0) if _s(row.get("sensorId")) == _s(sensorId)][:max(1, min(_i(limit, 20), 100))]


def sensor_latest(sensorId: Any = None, **_: Any) -> dict[str, Any]:
    rows = sensor_query(sensorId, 1)
    if isinstance(rows, dict):
        return rows
    return rows[0] if rows else {"error": "no readings"}


def sensor_alert_set(sensorId: Any = None, metric: Any = None, threshold: Any = None, operator: Any = "gt", severity: Any = "warning", **_: Any) -> dict[str, Any]:
    if not sensorId or not metric or threshold is None:
        return {"error": "sensorId, metric, threshold required"}
    node_id = f"alertRule:{_id('alert')}"
    _insert_spatial("sensorAlert", {"nodeId": node_id, "sensorId": sensorId, "metric": metric, "operator": operator or "gt", "threshold": threshold, "severity": severity or "warning", "nodeLabel": "SensorAlert", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
    return {"nodeId": node_id, "status": "created"}


def simulation_create(name: Any = None, scenario: Any = "default", modelType: Any = "generic", paramsJson: Any = None, targetArea: Any = None, **_: Any) -> dict[str, Any]:
    if not name:
        return {"error": "name required"}
    node_id = f"sim:{_id('sim')}"
    _insert_spatial("simulation", {"nodeId": node_id, "name": name, "scenario": scenario or "default", "modelType": modelType or "generic", "paramsJson": paramsJson, "targetArea": targetArea, "status": "created", "nodeLabel": "Simulation", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
    return {"nodeId": node_id, "status": "created"}


def simulation_run(simulationId: Any = None, **_: Any) -> dict[str, Any]:
    if not simulationId:
        return {"error": "simulationId required"}
    _insert_spatial("simulationResult", {"simulationId": simulationId, "status": "running", "startedAt": now_iso(), "nodeLabel": "SimulationResult", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, _s(simulationId))
    return {"simulationId": simulationId, "status": "running"}


def forecast_get(entityId: Any = None, forecastType: Any = None, **_: Any) -> dict[str, Any]:
    if not entityId:
        return {"error": "entityId required"}
    rows = [row for row in _list_spatial_label("Forecast", 1000, 0) if _s(row.get("entityId")) == _s(entityId) and (not forecastType or _s(row.get("forecastType")) == _s(forecastType))]
    return rows[0] if rows else {"error": "no forecast"}


def health_assess(entityId: Any = None, **kwargs: Any) -> dict[str, Any]:
    if not entityId:
        return {"error": "entityId required"}
    node_id = f"health:{_id('health')}"
    _insert_spatial("healthAssessment", {"nodeId": node_id, "entityId": entityId, "nodeLabel": "HealthAssessment", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID, **kwargs}, node_id)
    return {"nodeId": node_id, "status": "assessed"}


def maintenance_plan(entityId: Any = None, planType: Any = "preventive", intervalDays: Any = 90, priority: Any = "medium", **_: Any) -> dict[str, Any]:
    if not entityId:
        return {"error": "entityId required"}
    node_id = f"maint:{_id('maint')}"
    _insert_spatial("maintenancePlan", {"nodeId": node_id, "entityId": entityId, "planType": planType or "preventive", "intervalDays": intervalDays or 90, "priority": priority or "medium", "nextDue": now_iso(), "nodeLabel": "MaintenancePlan", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
    return {"nodeId": node_id, "status": "planned"}


def spatial_event_record(entityId: Any = None, eventType: Any = None, severity: Any = "info", description: Any = None, lat: Any = None, lng: Any = None, **_: Any) -> dict[str, Any]:
    if not entityId or not eventType:
        return {"error": "entityId and eventType required"}
    node_id = f"evt:{_id('evt')}"
    _insert_spatial("spatialEvent", {"nodeId": node_id, "entityId": entityId, "eventType": eventType, "severity": severity or "info", "description": description, "lat": lat, "lng": lng, "locationJson": _json({"lat": lat, "lng": lng}) if lat is not None and lng is not None else None, "occurredAt": now_iso(), "nodeLabel": "SpatialEvent", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
    return {"nodeId": node_id, "status": "recorded"}


def spatial_event_query(entityId: Any = None, eventType: Any = None, limit: Any = 50, **_: Any) -> list[dict[str, Any]]:
    rows = _list_spatial_label("SpatialEvent", 1000, 0)
    if entityId:
        rows = [row for row in rows if _s(row.get("entityId")) == _s(entityId)]
    if eventType:
        rows = [row for row in rows if _s(row.get("eventType")) == _s(eventType)]
    return rows[:max(1, min(_i(limit, 50), 100))]


def spatial_version_record(entityId: Any = None, changeType: Any = None, properties: Any = None, **_: Any) -> dict[str, Any]:
    if not entityId or not changeType:
        return {"error": "entityId and changeType required"}
    version_id = _id("ver")
    _insert_spatial("spatialVersion", {"versionId": version_id, "entityId": entityId, "changeType": changeType, "changedAt": now_iso(), "properties": _json(properties) if properties is not None else None, "nodeLabel": "SpatialVersion", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, version_id)
    return {"versionId": version_id, "status": "recorded"}


def spatial_version_query(entityId: Any = None, limit: Any = 50, **_: Any) -> list[dict[str, Any]] | dict[str, str]:
    if not entityId:
        return {"error": "entityId required"}
    return [row for row in _list_spatial_label("SpatialVersion", 1000, 0) if _s(row.get("entityId")) == _s(entityId)][:max(1, min(_i(limit, 50), 100))]


def spatial_relation_write(fromId: Any = None, toId: Any = None, relation: Any = None, validFrom: Any = None, validTo: Any = None, **_: Any) -> dict[str, Any]:
    if not fromId or not toId or not relation:
        return {"error": "fromId, toId, relation required"}
    rel_id = _id("rel")
    _insert_spatial("spatialRelation", {"relId": rel_id, "fromId": fromId, "toId": toId, "relation": relation, "validFrom": validFrom or now_iso(), "validTo": validTo, "nodeLabel": "SpatialRelation", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, rel_id)
    return {"relId": rel_id, "status": "created"}


def spatial_relation_query(entityId: Any = None, relation: Any = None, limit: Any = 50, **_: Any) -> list[dict[str, Any]] | dict[str, str]:
    if not entityId:
        return {"error": "entityId required"}
    rows = [row for row in _list_spatial_label("SpatialRelation", 1000, 0) if _s(row.get("fromId")) == _s(entityId) or _s(row.get("toId")) == _s(entityId)]
    if relation:
        rows = [row for row in rows if _s(row.get("relation")) == _s(relation)]
    return rows[:max(1, min(_i(limit, 50), 100))]


def timeline(entityId: Any = None, limit: Any = 50, **_: Any) -> dict[str, Any]:
    if not entityId:
        return {"error": "entityId required"}
    return {"entityId": entityId, "events": spatial_event_query(entityId, limit=limit), "versions": spatial_version_query(entityId, limit=limit)}


def spatial_diff(entityId: Any = None, **_: Any) -> dict[str, Any]:
    if not entityId:
        return {"error": "entityId required"}
    versions = spatial_version_query(entityId, limit=100)
    if isinstance(versions, dict):
        return versions
    return {"entityId": entityId, "versions": versions, "diffCount": len(versions)}


def display_layer_define(name: Any = None, domain: Any = "maps", filterKind: Any = None, color: Any = "#3b82f6", opacity: Any = 0.8, renderType: Any = "fill", **_: Any) -> dict[str, Any]:
    if not name:
        return {"error": "name required"}
    layer_id = _id("layer")
    _insert_spatial("displayLayer", {"layerId": layer_id, "name": name, "domain": domain or "maps", "filterKind": filterKind, "color": color or "#3b82f6", "opacity": opacity or 0.8, "renderType": renderType or "fill", "nodeLabel": "DisplayLayer", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, layer_id)
    return {"layerId": layer_id, "status": "created"}


def actor_locations(limit: Any = 200, **_: Any) -> dict[str, Any]:
    return {"points": [], "limit": max(1, min(_i(limit, 200), 500))}


def get_dashboard(**_: Any) -> dict[str, Any]:
    labels = ["Place", "Route", "Building", "Sensor", "Road", "Railway", "Airport", "Port", "Station", "Spot", "River", "Lake", "Mountain", "InfraNetwork", "InfraIncident", "Simulation", "SpatialEvent", "DisplayLayer", "VisionResult", "SatelliteScene", "CollectionJob"]
    out: dict[str, Any] = {}
    for label in labels:
        key = label[:1].lower() + label[1:]
        out[key + ("s" if not key.endswith("s") else "")] = len(_list_spatial_label(label, 1000, 0))
    return out


def list_post_locations(authorDid: Any = None, lat: Any = None, lng: Any = None, radiusKm: Any = 5, limit: Any = 50, **_: Any) -> list[dict[str, Any]]:
    rows = [row for row in _list_spatial_label("SpatialEvent", 1000, 0) if _s(row.get("eventType")) == "userPostPhoto"]
    if authorDid:
        rows = [row for row in rows if _s(row.get("authorDid")) == _s(authorDid)]
    if lat is not None and lng is not None:
        rows = [row for row in rows if _within_radius(row, _n(lat), _n(lng), _n(radiusKm, 5))]
    return rows[:max(1, min(_i(limit, 50), 100))]


def mapraly_import_poi(pois: Any = None, **_: Any) -> dict[str, Any]:
    if not isinstance(pois, list) or not pois:
        return {"error": "pois array required"}
    created = 0
    for poi in pois:
        if not isinstance(poi, dict) or not poi.get("name") or poi.get("lat") is None or poi.get("lng") is None:
            continue
        if poi.get("routeGeojson"):
            route_id = _id("mapralyRoute")
            _insert_spatial("route", {"nodeId": f"route:{route_id}", "name": poi.get("name"), "routeType": "mapraly", "geojson": poi.get("routeGeojson"), "lat": poi.get("lat"), "lng": poi.get("lng"), "source": "mapraly", "sourceDid": "did:web:maps.etzhayyim.com:mapraly", "mapralyId": poi.get("mapralyId"), "description": poi.get("description"), "nodeLabel": "Route", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, f"route:{route_id}")
        else:
            spot_id = _id("mapralySpot")
            _insert_spatial("spot", {"nodeId": f"spot:{spot_id}", "name": poi.get("name"), "spotType": "mapralyPoi", "category": poi.get("category") or "general", "lat": poi.get("lat"), "lng": poi.get("lng"), "description": poi.get("description"), "photosJson": _json(poi.get("photos")) if poi.get("photos") is not None else None, "source": "mapraly", "sourceDid": "did:web:maps.etzhayyim.com:mapraly", "mapralyId": poi.get("mapralyId"), "nodeLabel": "Spot", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, f"spot:{spot_id}")
        created += 1
    return {"imported": created, "total": len(pois)}


def mapraly_list_pois(category: Any = None, lat: Any = None, lng: Any = None, radiusKm: Any = 10, limit: Any = 50, **_: Any) -> list[dict[str, Any]]:
    rows = [row for row in _list_spatial_label("Spot", 1000, 0) if _s(row.get("source")) == "mapraly"]
    if category:
        rows = [row for row in rows if _s(row.get("category")) == _s(category)]
    if lat is not None and lng is not None:
        rows = [row for row in rows if _within_radius(row, _n(lat), _n(lng), _n(radiusKm, 10))]
    return rows[:max(1, min(_i(limit, 50), 100))]


def vision_import_entities(jobId: Any = None, imageCid: Any = None, entities: Any = None, **_: Any) -> dict[str, Any]:
    if not isinstance(entities, list) or not entities:
        return {"error": "entities array required"}
    created = 0
    for ent in entities:
        if not isinstance(ent, dict) or not ent.get("kind") or ent.get("lat") is None or ent.get("lng") is None:
            continue
        collection = _s(ent.get("kind"))
        node_id = f"{collection}:{_id('vision_' + collection)}"
        _insert_spatial(collection, {"nodeId": node_id, "name": ent.get("name"), "lat": ent.get("lat"), "lng": ent.get("lng"), "confidence": ent.get("confidence"), "detectedClasses": _json(ent.get("classes")) if ent.get("classes") is not None else None, "source": "murakumoVision", "sourceDid": "did:web:maps.etzhayyim.com:vision", "sourceImageCid": imageCid, "visionJobId": jobId, **(ent.get("properties") if isinstance(ent.get("properties"), dict) else {}), "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, node_id)
        _insert_spatial("visionResult", {"nodeId": f"vr:{_id('vr')}", "jobId": jobId, "imageCid": imageCid, "entityKind": collection, "entityNodeId": node_id, "confidence": ent.get("confidence"), "classesJson": _json(ent.get("classes")) if ent.get("classes") is not None else None, "lat": ent.get("lat"), "lng": ent.get("lng"), "nodeLabel": "VisionResult", "sourceDid": "did:web:maps.etzhayyim.com:vision", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID})
        created += 1
    return {"imported": created, "total": len(entities)}


def list_vision_results(jobId: Any = None, entityKind: Any = None, minConfidence: Any = None, limit: Any = 50, **_: Any) -> list[dict[str, Any]]:
    rows = _list_spatial_label("VisionResult", 1000, 0)
    if jobId:
        rows = [row for row in rows if _s(row.get("jobId")) == _s(jobId)]
    if entityKind:
        rows = [row for row in rows if _s(row.get("entityKind")) == _s(entityKind)]
    if minConfidence is not None:
        rows = [row for row in rows if _n(row.get("confidence")) >= _n(minConfidence)]
    return rows[:max(1, min(_i(limit, 50), 100))]


def satellite_import_scene(scenes: Any = None, **_: Any) -> dict[str, Any]:
    if not isinstance(scenes, list) or not scenes:
        return {"error": "scenes array required"}
    created = 0
    for scene in scenes:
        if not isinstance(scene, dict) or not scene.get("sceneId"):
            continue
        bbox = scene.get("bbox") if isinstance(scene.get("bbox"), dict) else {}
        _insert_spatial("satelliteScene", {"nodeId": f"sat:{scene.get('sceneId')}", "sceneId": scene.get("sceneId"), "satellite": scene.get("satellite"), "acquisitionDate": scene.get("acquisitionDate"), "cloudCover": scene.get("cloudCover"), "resolutionM": scene.get("resolutionM"), "sensorType": scene.get("sensorType") or "optical", "bboxJson": _json(bbox), "lat": (_n(bbox.get("latMin")) + _n(bbox.get("latMax"))) / 2 if bbox else None, "lng": (_n(bbox.get("lngMin")) + _n(bbox.get("lngMax"))) / 2 if bbox else None, "bandsJson": _json(scene.get("bands")) if scene.get("bands") is not None else None, "cogUrl": scene.get("cogUrl"), "thumbnailUrl": scene.get("thumbnailUrl"), "source": "satellite", "sourceDid": "did:web:maps.etzhayyim.com:satellite", "nodeLabel": "SatelliteScene", "createdAt": now_iso(), "orgId": "anon", "userId": "anon", "actorId": APP_ID}, f"sat:{scene.get('sceneId')}")
        created += 1
    return {"imported": created, "total": len(scenes)}


def list_satellite_scenes(satellite: Any = None, lat: Any = None, lng: Any = None, radiusKm: Any = 50, limit: Any = 50, **_: Any) -> list[dict[str, Any]]:
    rows = _list_spatial_label("SatelliteScene", 1000, 0)
    if satellite:
        rows = [row for row in rows if _s(row.get("satellite")) == _s(satellite)]
    if lat is not None and lng is not None:
        rows = [row for row in rows if _within_radius(row, _n(lat), _n(lng), _n(radiusKm, 50))]
    return rows[:max(1, min(_i(limit, 50), 100))]


def list_satellite_sources(**_: Any) -> list[dict[str, Any]]:
    return [{"name": name, "cost": "free"} for name in ("sentinel-2", "landsat", "sentinel-1", "hls", "cop-dem", "naip")]


def register_ownership(ownerEntityId: Any = None, propertyId: Any = None, **kwargs: Any) -> dict[str, Any]:
    if not ownerEntityId or not propertyId:
        return {"error": "ownerEntityId and propertyId required"}
    edge_id = f"own:{_id('own')}"
    _insert_spatial("ownership", {"edgeId": edge_id, "ownerEntityId": ownerEntityId, "propertyId": propertyId, "nodeLabel": "OwnsProperty", "createdAt": now_iso(), "orgId": _s(kwargs.get("orgId"), "anon"), "userId": _s(kwargs.get("userId"), "anon"), "actorId": APP_ID, **kwargs}, edge_id)
    return {"edgeId": edge_id, "status": "created"}


def ownership_chain(propertyId: Any = None, limit: Any = 20, **_: Any) -> dict[str, Any]:
    if not propertyId:
        return {"error": "propertyId required"}
    rows = [row for row in _list_spatial_label("OwnsProperty", 1000, 0) if _s(row.get("propertyId")) == _s(propertyId)]
    return {"propertyId": propertyId, "chain": rows[:max(1, min(_i(limit, 20), 100))]}


def entity_history(entityId: Any = None, **_: Any) -> dict[str, Any]:
    if not entityId:
        return {"error": "entityId required"}
    return {"entityId": entityId, "registries": [], "ownerships": [row for row in _list_spatial_label("OwnsProperty", 1000, 0) if _s(row.get("ownerEntityId")) == _s(entityId)][:50], "operations": []}


for _fn_name, _entity, _label, _id_prefix, _required in (
    ("register_waterway", "waterway", "Waterway", "waterway", "name"),
    ("register_port", "port", "Port", "port", "name"),
    ("register_airport", "airport", "Airport", "airport", "name"),
    ("register_station", "station", "Station", "station", "name"),
    ("register_bus_stop", "busStop", "BusStop", "busStop", "name"),
    ("register_parking", "parking", "Parking", "parking", "name"),
    ("register_ev_charger", "evCharger", "EvCharger", "evCharger", "name"),
    ("register_aircraft", "aircraft", "Aircraft", "aircraft", "tailNumber"),
    ("upsert_flight_operation", "flightOperation", "FlightOperation", "fop", "flightNumber"),
    ("upsert_flight_offer", "flightOffer", "FlightOffer", "fof", "flightNumber"),
    ("register_building", "building", "Building", "bldg", "name"),
    ("register_building_floor", "buildingFloor", "BuildingFloor", "floor", "buildingId"),
    ("register_sensor", "sensor", "Sensor", "sensor", "sensorType"),
    ("register_legal_entity", "legalEntity", "LegalEntity", "ent", "name"),
    ("register_operator", "operator", "Operator", "opr", "name"),
    ("register_property_owner", "propertyOwner", "PropertyOwner", "pown", "name"),
    ("register_land_registry", "landRegistry", "LandRegistry", "lreg", "registryNumber"),
    ("register_property_registry", "propertyRegistry", "PropertyRegistry", "preg", "registryNumber"),
    ("register_business_registry", "businessRegistry", "BusinessRegistry", "breg", "registryNumber"),
    ("register_construction_permit", "constructionPermit", "ConstructionPermit", "cpmt", "registryNumber"),
    ("register_operating_license", "operatingLicense", "OperatingLicense", "olic", "registryNumber"),
    ("register_zoning_record", "zoningRecord", "ZoningRecord", "zrec", "landUse"),
):
    globals()[_fn_name] = _make_register(_entity, _label, _id_prefix, _required)


for _fn_name, _label, _filter in (
    ("list_waterways", "Waterway", None),
    ("list_ports", "Port", "portType"),
    ("list_airports", "Airport", "airportType"),
    ("list_stations", "Station", "stationType"),
    ("list_bus_stops", "BusStop", None),
    ("list_parkings", "Parking", None),
    ("list_ev_chargers", "EvCharger", "connectorType"),
    ("list_flight_operations", "FlightOperation", "flightNumber"),
    ("list_flight_offers", "FlightOffer", "flightNumber"),
    ("list_buildings", "Building", None),
    ("list_assets", "PhysicalAsset", "assetType"),
    ("list_devices", "DeviceBinding", "status"),
    ("list_sensors", "Sensor", "sensorType"),
    ("list_sensor_alerts", "SensorAlert", "sensorId"),
    ("list_display_layers", "DisplayLayer", "domain"),
    ("list_geo_domains", "GeoDomain", "category"),
    ("list_web_crawl_geo_entities", "WebCrawlGeoEntity", "entityType"),
    ("list_legal_entities", "LegalEntity", "entityType"),
    ("list_operators", "Operator", "jurisdiction"),
    ("list_property_owners", "PropertyOwner", "jurisdiction"),
    ("list_land_registries", "LandRegistry", "jurisdiction"),
    ("list_property_registries", "PropertyRegistry", "jurisdiction"),
    ("list_business_registries", "BusinessRegistry", "jurisdiction"),
    ("list_construction_permits", "ConstructionPermit", "jurisdiction"),
    ("list_operating_licenses", "OperatingLicense", "jurisdiction"),
    ("list_zoning_records", "ZoningRecord", "jurisdiction"),
):
    globals()[_fn_name] = _make_list(_label, _filter)


get_building = _make_get("Building", "buildingId")
twin_state_get = _make_get("TwinState", "entityId")
simulation_result = _make_get("SimulationResult", "simulationId")


def get_coverage_status(limit: Any = 50, minCollected: Any = 0, **_: Any) -> dict[str, Any]:
    cap = min(_i(limit, 50), 200)
    min_collected = max(_i(minCollected, 0), 0)
    if min_collected > 0:
        frontier_rows = _rows(
            f"""SELECT source_did, label, collected_count, world_total, gap_score, hours_since_fetch
               FROM view_maps_coverage_gap_ranked
               WHERE collected_count >= %s
               ORDER BY collected_count DESC, gap_score DESC
               LIMIT {int(cap)}""",
            (min_collected,),
        )
    else:
        frontier_rows = _rows(
            f"""SELECT source_did, label, collected_count, world_total, gap_score, hours_since_fetch
               FROM view_maps_coverage_gap_ranked
               ORDER BY collected_count DESC, gap_score DESC
               LIMIT {int(cap)}""",
            (),
        )
    totals = _row(
        """SELECT
             SUM(CASE WHEN collected_count > 0 THEN 1 ELSE 0)::bigint AS active_targets,
             COUNT(*)::bigint AS total_targets,
             SUM(collected_count)::bigint AS total_collected
           FROM vertex_maps_coverage_target""",
    ) or {}
    job_stats = _row(
        """SELECT
             SUM(1)::bigint AS recent,
             SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END)::bigint AS recent_done
           FROM vertex_maps_job
           WHERE created_at > NOW() - INTERVAL '1 hour'""",
    ) or {}
    frontier = []
    for row in frontier_rows:
        collected = _i(row.get("collected_count"))
        world_total = _i(row.get("world_total"))
        frontier.append({
            "sourceDid": row.get("source_did"),
            "label": row.get("label"),
            "collectedCount": collected,
            "worldTotal": world_total,
            "coveragePct": (100 * collected / world_total) if world_total > 0 else 0,
            "gapScore": _n(row.get("gap_score")),
            "hoursSinceLastFetch": _n(row.get("hours_since_fetch")),
        })
    return {
        "frontier": frontier,
        "totals": {
            "activeTargets": _i(totals.get("active_targets")),
            "totalTargets": _i(totals.get("total_targets")),
            "totalCollected": _i(totals.get("total_collected")),
            "recentJobs1h": _i(job_stats.get("recent")),
            "recentJobsDone1h": _i(job_stats.get("recent_done")),
        },
    }


def expand_frontier(targets: Any = None, **_: Any) -> dict[str, Any]:
    items = targets if isinstance(targets, list) else []
    if not items:
        return {"requested": 0, "inserted": 0, "skippedExisting": 0, "added": []}
    timestamp = now_iso()
    inserted = 0
    skipped = 0
    added: list[str] = []
    for target in items:
        if not isinstance(target, dict):
            skipped += 1
            continue
        source_did = _s(target.get("sourceDid"))
        label = _s(target.get("label"))
        if not source_did or not label:
            skipped += 1
            continue
        world_total = max(_i(target.get("worldTotal"), 1_000_000), 1)
        priority_weight = _n(target.get("priorityWeight"), 0.3)
        ttl_hours = _n(target.get("ttlHours"), 168)
        slug = source_did.replace("did:web:maps.etzhayyim.com:", "").replace("did:web:maps.etzhayyim.com", "")
        slug = slug.replace(".", "-").replace(":", "-") or "primary"
        vertex_id = f"at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.coverageTarget/{slug}:{label}"
        exists = _row("SELECT vertex_id FROM vertex_maps_coverage_target WHERE vertex_id = %s LIMIT 1", (vertex_id,))
        if exists:
            skipped += 1
            continue
        _execute(
            """INSERT INTO vertex_maps_coverage_target
            (vertex_id, source_did, label, world_total, priority_weight,
             ttl_hours, org_id, user_id, actor_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'anon', 'anon', %s, %s)""",
            (vertex_id, source_did, label, world_total, priority_weight, ttl_hours, source_did, timestamp),
        )
        inserted += 1
        added.append(vertex_id)
    if inserted > 0:
        try:
            _execute("FLUSH")
        except Exception:
            pass
    return {"requested": len(items), "inserted": inserted, "skippedExisting": skipped, "added": added}


def seed_all_known_variations(dryRun: Any = False, **_: Any) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for key, label in WIKIDATA_PROFILE_LABELS.items():
        source_did = "did:web:maps.etzhayyim.com:registry:wikidata" if key == "corp" else f"did:web:maps.etzhayyim.com:registry:wikidata:{key}"
        candidates.append({
            "sourceDid": source_did,
            "label": label,
            "worldTotal": WIKIDATA_WORLD_TOTALS.get(key, 100000),
            "priorityWeight": 1.0 if key == "corp" else 0.3,
            "ttlHours": 720,
            "kind": "wikidata",
        })
    stac_world_totals = {"sentinel2": 5000000, "landsat": 2000000, "sentinel1": 1500000, "naip": 500000}
    for key, world_total in stac_world_totals.items():
        candidates.append({
            "sourceDid": f"did:web:maps.etzhayyim.com:satellite:{key}",
            "label": "SatelliteScene",
            "worldTotal": world_total,
            "priorityWeight": 0.3 if key == "naip" else 0.6,
            "ttlHours": 720,
            "kind": "stac",
        })
    for label in OVERPASS_LABELS:
        candidates.append({
            "sourceDid": "did:web:maps.etzhayyim.com:infrastructure",
            "label": label,
            "worldTotal": 1000000,
            "priorityWeight": 0.3,
            "ttlHours": 168,
            "kind": "overpass",
        })

    by_kind = {"wikidata": len(WIKIDATA_PROFILE_LABELS), "stac": len(stac_world_totals), "overpass": len(OVERPASS_LABELS)}
    if bool(dryRun):
        return {"candidateCount": len(candidates), "inserted": 0, "skippedExisting": 0, "byKind": by_kind}

    existing = _rows("SELECT vertex_id FROM vertex_maps_coverage_target")
    have = {_s(row.get("vertex_id")) for row in existing}
    timestamp = now_iso()
    inserted = 0
    skipped = 0
    inserted_by_kind = {"wikidata": 0, "stac": 0, "overpass": 0}
    for candidate in candidates:
        source_did = _s(candidate["sourceDid"])
        label = _s(candidate["label"])
        slug = source_did.replace("did:web:maps.etzhayyim.com:", "").replace("did:web:maps.etzhayyim.com", "")
        slug = slug.replace(".", "-").replace(":", "-") or "primary"
        vertex_id = f"at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.coverageTarget/{slug}:{label}"
        if vertex_id in have:
            skipped += 1
            continue
        _execute(
            """INSERT INTO vertex_maps_coverage_target
            (vertex_id, source_did, label, world_total, priority_weight,
             ttl_hours, org_id, user_id, actor_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'anon', 'anon', %s, %s)""",
            (
                vertex_id,
                source_did,
                label,
                _i(candidate.get("worldTotal"), 1000000),
                _n(candidate.get("priorityWeight"), 0.3),
                _n(candidate.get("ttlHours"), 168),
                source_did,
                timestamp,
            ),
        )
        have.add(vertex_id)
        inserted += 1
        kind = _s(candidate.get("kind"))
        if kind in inserted_by_kind:
            inserted_by_kind[kind] += 1
    if inserted > 0:
        try:
            _execute("FLUSH")
        except Exception:
            pass
    return {"candidateCount": len(candidates), "inserted": inserted, "skippedExisting": skipped, "byKind": inserted_by_kind}


def _coverage_target_rows(source_did: str | None, label: str | None, only_zeroed: bool) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if source_did:
        clauses.append("source_did = %s")
        params.append(source_did)
    if label:
        clauses.append("label = %s")
        params.append(label)
    if only_zeroed:
        clauses.append("collected_count = 0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows(
        f"""SELECT vertex_id, source_did, label, collected_count
            FROM vertex_maps_coverage_target
            {where}""",
        tuple(params),
    )


def _coverage_live_rows(source_did: str | None, label: str | None) -> list[dict[str, Any]]:
    clauses = ["source_did IS NOT NULL", "label IS NOT NULL"]
    params: list[Any] = []
    if source_did:
        clauses.append("source_did = %s")
        params.append(source_did)
    if label:
        clauses.append("label = %s")
        params.append(label)
    where = f"WHERE {' AND '.join(clauses)}"
    for table_sql in (
        f"SELECT source_did, label, collected_count FROM mv_maps_collected_per_source_label_canonical {where}",
        f"SELECT source_did, label, collected_count FROM mv_maps_collected_per_source_label {where}",
        f"""SELECT source_did, label, COUNT(*)::bigint AS collected_count
            FROM vertex_spatial
            {where}
            GROUP BY source_did, label""",
    ):
        try:
            return _rows(table_sql, tuple(params))
        except Exception:
            continue
    return []


def refresh_coverage_stats(sourceDid: Any = None, label: Any = None, onlyZeroed: Any = False, **_: Any) -> dict[str, Any]:
    filter_source = _s(sourceDid) or None
    filter_label = _s(label) or None
    before = _coverage_target_rows(filter_source, filter_label, bool(onlyZeroed))
    live_rows = _coverage_live_rows(filter_source, filter_label)
    live_map = {
        f"{row.get('source_did')}::{row.get('label')}": _i(row.get("collected_count"))
        for row in live_rows
    }
    updated = 0
    deltas: list[dict[str, Any]] = []
    for row in before:
        key = f"{row.get('source_did')}::{row.get('label')}"
        was_at = _i(row.get("collected_count"))
        now_at = live_map.get(key, 0)
        if was_at == now_at:
            continue
        _execute(
            "UPDATE vertex_maps_coverage_target SET collected_count = %s WHERE vertex_id = %s",
            (now_at, row.get("vertex_id")),
        )
        updated += 1
        deltas.append({
            "sourceDid": row.get("source_did"),
            "label": row.get("label"),
            "before": was_at,
            "after": now_at,
            "delta": now_at - was_at,
        })
    deltas.sort(key=lambda item: abs(_i(item.get("delta"))), reverse=True)
    return {
        "scanned": len(live_rows),
        "updated": updated,
        "deltas": deltas[:20],
        "totalCollectedAcrossTargets": sum(live_map.values()),
    }


def _label_to_dataset_type(label: str) -> str:
    if label in {"LegalEntity", "Operator", "PropertyOwner"}:
        return "registry"
    if label == "SatelliteScene":
        return "raster"
    if label in {"Airport", "Station", "BusRoute"}:
        return "gtfs"
    return "geojson"


def _pipeline_type_for_label(label: str) -> str:
    if label == "SatelliteScene":
        return "satellite_scene"
    return "poi_import"


def advance_coverage(limit: Any = 1, sourceDid: Any = None, label: Any = None, dryRun: Any = False, **_: Any) -> dict[str, Any]:
    cap = max(1, min(_i(limit, 1), 10))
    source_did = _s(sourceDid) or None
    filter_label = _s(label) or None
    clauses = [
        "gap_score > 0",
        """maps_source_dispatch_kind(source_did, COALESCE(label, '')) IN
           ('overpass', 'gleif', 'wikidata', 'stac', 'seismic', 'wikipedia',
            'commons', 'inaturalist', 'gbif', 'wikivoyage', 'eonet',
            'opensky', 'noaa_tides', 'osm_notes')""",
    ]
    params: list[Any] = []
    if source_did:
        clauses.append("source_did = %s")
        params.append(source_did)
    if filter_label:
        clauses.append("label = %s")
        params.append(filter_label)
    params.append(cap)
    rows = _rows(
        f"""SELECT vertex_id, source_did, label, collected_count, world_total,
                   priority_weight, hours_since_fetch, gap_score
              FROM view_maps_coverage_gap_ranked
             WHERE {' AND '.join(clauses)}
             ORDER BY gap_score DESC
             LIMIT {int(cap)}""",
        tuple(params[:-1]),
    )
    if not rows:
        return {"picked": [], "advanced": 0, "remainingGaps": 0, "nextRunHint": None}

    picked: list[dict[str, Any]] = []
    advanced = 0
    for row in rows:
        row_label = _s(row.get("label"))
        entry: dict[str, Any] = {
            "sourceDid": row.get("source_did"),
            "label": row_label,
            "collectedCount": _i(row.get("collected_count")),
            "worldTotal": _i(row.get("world_total")),
            "gapScore": _n(row.get("gap_score")),
            "priorityWeight": _n(row.get("priority_weight")),
            "hoursSinceLastFetch": _n(row.get("hours_since_fetch")),
        }
        if not bool(dryRun):
            job_id = _id("mcv")
            priority_weight = _n(row.get("priority_weight"))
            event = {
                "jobId": job_id,
                "sourceId": row.get("source_did"),
                "datasetType": _label_to_dataset_type(row_label),
                "region": "global",
                "priority": "high" if priority_weight >= 0.9 else "normal" if priority_weight >= 0.5 else "low",
                "status": "pending",
                "phase": 0,
                "stage": "sequence_select",
                "progressPct": 0,
                "pipelineType": _pipeline_type_for_label(row_label),
                "nodeLabel": "MapsJob",
                "createdAt": now_iso(),
                "orgId": "anon",
                "userId": "anon",
                "actorId": APP_ID,
                "coverageTargetVid": row.get("vertex_id"),
                "gapScoreAtAdvance": _n(row.get("gap_score")),
            }
            _insert_spatial("job", event, job_id)
            _insert_job_event(event)
            _execute("UPDATE vertex_maps_coverage_target SET last_fetched_at = NOW() WHERE vertex_id = %s", (row.get("vertex_id"),))
            entry["jobId"] = job_id
            advanced += 1
        picked.append(entry)

    if advanced > 0:
        try:
            _execute("FLUSH")
        except Exception:
            pass
    remaining = _row("SELECT COUNT(*) AS cnt FROM view_maps_coverage_gap_ranked WHERE gap_score > 0") or {}
    return {
        "picked": picked,
        "advanced": advanced,
        "remainingGaps": _i(remaining.get("cnt")),
        "nextRunHint": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 120)),
    }


def _maps_xrpc_post(nsid: str, body: dict[str, Any], timeout_sec: float = 90.0) -> dict[str, Any]:
    base = (
        os.environ.get("MAPS_XRPC_BASE_URL")
        or os.environ.get("MAPS_WORKER_URL")
        or "https://maps.etzhayyim.com"
    ).rstrip("/")
    url = f"{base}/xrpc/{nsid}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "etzhayyim-kotoba-kotodama-maps-coverage/1.0",
    }
    secret = os.environ.get("MAPS_INTERNAL_SECRET") or os.environ.get("DISPATCHER_INTERNAL_SECRET")
    if secret:
        headers["x-internal-trust"] = secret
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=max(1.0, min(timeout_sec, 120.0))) as resp:
            text = resp.read(65536).decode("utf-8", errors="replace")
            status = int(getattr(resp, "status", 200))
    except urllib.error.HTTPError as e:
        text = e.read(65536).decode("utf-8", errors="replace")
        status = int(e.code)
    except Exception as e:  # noqa: BLE001
        return {"error": f"transport: {e}", "status": -1, "latencyMs": int((time.monotonic() - started) * 1000)}
    latency_ms = int((time.monotonic() - started) * 1000)
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        return {"error": "NonJsonResponse", "status": status, "latencyMs": latency_ms, "body": text[:4096]}
    if isinstance(parsed, dict):
        parsed.setdefault("statusCode", status)
        parsed.setdefault("latencyMs", latency_ms)
        return parsed
    return {"body": parsed, "statusCode": status, "latencyMs": latency_ms}


def run_coverage_job(jobId: Any = None, maxRecords: Any = 100, **_: Any) -> dict[str, Any]:
    """Settle a pending vertex_maps_job by syncing collected_count from the
    canonical MV. Bulk-ingest pods write directly to vertex_spatial; this
    handler reflects that progress into vertex_maps_coverage_target and
    closes the job. Returns recordsWritten = delta vs prior tracker value.
    No external HTTP fetch (long-tail SPARQL/Overpass dispatch is a future
    extension). Called by batchCoverageCycle BPMN actor.
    """
    job_id = _s(jobId)
    if not job_id:
        return {"error": "jobId required", "status": "error"}
    cap = max(1, min(_i(maxRecords, 100), 500))
    job = _row(
        "SELECT source_id, dataset_type, region, props FROM vertex_maps_job WHERE job_id = %s ORDER BY _seq DESC LIMIT 1",
        (job_id,),
    )
    if not job:
        return {"jobId": job_id, "status": "error", "error": "job not found", "recordsWritten": 0}
    source_did = _s(job.get("source_id"))
    props_raw = job.get("props")
    label = ""
    coverage_vid = ""
    try:
        props_obj = json.loads(_s(props_raw)) if props_raw else {}
    except json.JSONDecodeError:
        props_obj = {}
    if isinstance(props_obj, dict):
        coverage_vid = _s(props_obj.get("coverageTargetVid"))
    if coverage_vid:
        target = _row(
            "SELECT vertex_id, source_did, label, collected_count, world_total FROM vertex_maps_coverage_target WHERE vertex_id = %s",
            (coverage_vid,),
        )
    else:
        target = None
    if not target and source_did:
        target = _row(
            "SELECT vertex_id, source_did, label, collected_count, world_total FROM vertex_maps_coverage_target WHERE source_did = %s ORDER BY priority_weight DESC NULLS LAST LIMIT 1",
            (source_did,),
        )
    if not target:
        _insert_job_event({
            "jobId": job_id, "status": "skipped", "phase": 2, "stage": "no_coverage_target",
            "progressPct": 100, "recordsCount": 0, "errorMessage": "no matching coverage_target",
            "nodeLabel": "MapsJob", "orgId": "anon", "userId": "anon", "actorId": APP_ID,
        })
        return {"jobId": job_id, "status": "skipped", "recordsWritten": 0, "reason": "no_coverage_target"}
    label = _s(target.get("label"))
    target_vid = _s(target.get("vertex_id"))
    prev_count = _i(target.get("collected_count"))
    world_total = _i(target.get("world_total"))
    mv_row = _row(
        "SELECT collected_count FROM mv_maps_collected_per_source_label_canonical WHERE source_did = %s AND label = %s",
        (source_did, label),
    )
    mv_count = _i(mv_row.get("collected_count")) if mv_row else 0
    new_count = max(prev_count, min(mv_count, world_total)) if world_total > 0 else max(prev_count, mv_count)
    delta = max(0, new_count - prev_count)
    records_written = min(delta, cap)
    if records_written > 0:
        applied_count = prev_count + records_written
        _execute(
            "UPDATE vertex_maps_coverage_target SET collected_count = %s, last_fetched_at = NOW(), last_run_at = NOW(), last_rows_written = %s WHERE vertex_id = %s",
            (applied_count, records_written, target_vid),
        )
        try:
            _execute("FLUSH")
        except Exception:
            pass
    _insert_job_event({
        "jobId": job_id, "status": "done", "phase": 2, "stage": "completed",
        "progressPct": 100, "recordsCount": records_written, "coverageRatio": (applied_count / world_total if records_written > 0 and world_total > 0 else (prev_count / world_total if world_total > 0 else 0)),
        "nodeLabel": "MapsJob", "orgId": "anon", "userId": "anon", "actorId": APP_ID,
    } if records_written > 0 else {
        "jobId": job_id, "status": "done", "phase": 2, "stage": "no_delta",
        "progressPct": 100, "recordsCount": 0,
        "nodeLabel": "MapsJob", "orgId": "anon", "userId": "anon", "actorId": APP_ID,
    })
    return {
        "jobId": job_id,
        "status": "done",
        "sourceDid": source_did,
        "label": label,
        "recordsWritten": records_written,
        "trackerBefore": prev_count,
        "trackerAfter": prev_count + records_written,
        "mvCount": mv_count,
        "worldTotal": world_total,
    }


def batch_coverage_cycle(
    advanceLimit: Any = 5,
    maxRecordsPerJob: Any = 60,
    refresh: Any = False,
    **_: Any,
) -> dict[str, Any]:
    advance_limit = max(1, min(_i(advanceLimit, 5), 10))
    max_records = max(1, min(_i(maxRecordsPerJob, 60), 500))

    adv_res = advance_coverage(limit=advance_limit)
    picked = adv_res.get("picked") if isinstance(adv_res, dict) else []
    picked_rows = picked if isinstance(picked, list) else []
    runs: list[dict[str, Any]] = []
    for item in picked_rows:
        if not isinstance(item, dict):
            continue
        job_id = _s(item.get("jobId"))
        if not job_id:
            continue
        runs.append({
            "jobId": job_id,
            "sourceDid": item.get("sourceDid"),
            "label": item.get("label"),
            "status": "queued",
        })

    refresh_updated = 0
    total_collected = 0
    if bool(refresh):
        refresh_res = refresh_coverage_stats()
        refresh_updated = _i(refresh_res.get("updated"))
        total_collected = _i(refresh_res.get("totalCollectedAcrossTargets"))

    return {
        "advanced": _i(adv_res.get("advanced") if isinstance(adv_res, dict) else 0),
        "ran": len(runs),
        "runs": runs,
        "refreshUpdated": refresh_updated,
        "totalCollected": total_collected,
    }
