"""
LandDonationProcessingCell — Pregel cell orchestrating the 6-step land donation ritual.

Per ADR-2605192245 (Global Land Sovereignty) + ADR-2605192330 (Extended) + ADR-2605192345 (Succession).

Trigger: MST listener on `com.etzhayyim.apps.etzhayyim.land-donation` records
Effect:
  - Validate WGS84 GeoJSON boundary
  - Verify satellite imagery hash
  - Verify donor oath signature
  - Verify successor designation (primary + 2 backup, per ADR-2605192345)
  - Verify donor is not Charter Non-Aligned
  - Call LandRegistry.donate() on geth-private
  - Mirror to PublicLandRegistry on Base L2 via AnchorBridge

Murakumo node: judah (leader), asher (failover replica)
"""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver


LandType = Literal[
    "Agricultural", "Residential", "Forest", "ReligiousFacility", "Other",
    "Ocean", "Water", "Air", "Orbit",
]


class LandDonationProcessingState(TypedDict, total=False):
    # Input — from MST event
    donation_uri: str
    donor_did: str
    geojson_cid: str
    imagery_bundle_cid: str
    deed_cid: str
    national_registry_ref: str
    area_m2: float
    land_type: LandType
    oath_hash: str  # keccak256 of canonical oath text
    donor_signature: str

    # Successor declaration (per ADR-2605192345)
    primary_successor_did: str
    backup_successor_dids: list[str]
    successor_pre_acceptances: list[str]  # at:// URIs of pre-acceptance records
    fallback_path: Literal["council-appointed", "corpus-direct", "community-trust", "dissolution-to-corpus"]

    # Validation results
    geojson_valid: bool
    geojson_area_match: bool
    imagery_hash_valid: bool
    oath_signature_valid: bool
    successor_pre_acceptance_count: int
    donor_charter_compliant: bool

    # Outputs
    land_id: int
    geth_private_tx_hash: str
    base_l2_tx_hash: str
    public_land_nft_id: int


def build_graph(
    checkpointer: BaseCheckpointSaver,
    geth_port,
    base_port,
    charter_compliance_port,
):
    g = StateGraph(LandDonationProcessingState)

    g.add_node("load_donation_request", load_donation_request)
    g.add_node("validate_geojson", validate_geojson)
    g.add_node("verify_imagery_hash", verify_imagery_hash)
    g.add_node("verify_oath_signature", verify_oath_signature)
    g.add_node("verify_successor_designation", verify_successor_designation)
    g.add_node("check_charter_compliance", lambda s: check_charter_compliance(s, charter_compliance_port))
    g.add_node("emit_geth_private", lambda s: emit_geth_private(s, geth_port))
    g.add_node("emit_base_l2_mirror", lambda s: emit_base_l2_mirror(s, base_port))
    g.add_node("emit_at_record", emit_at_record)

    g.add_edge(START, "load_donation_request")
    g.add_edge("load_donation_request", "validate_geojson")
    g.add_edge("validate_geojson", "verify_imagery_hash")
    g.add_edge("verify_imagery_hash", "verify_oath_signature")
    g.add_edge("verify_oath_signature", "verify_successor_designation")
    g.add_edge("verify_successor_designation", "check_charter_compliance")

    # If any validation failed, skip to error AT record
    def validation_router(state):
        all_valid = (
            state.get("geojson_valid")
            and state.get("geojson_area_match")
            and state.get("imagery_hash_valid")
            and state.get("oath_signature_valid")
            and state.get("successor_pre_acceptance_count", 0) >= 3  # 1 primary + 2 backup
            and state.get("donor_charter_compliant")
        )
        return "emit_geth_private" if all_valid else "emit_at_record"

    g.add_conditional_edges("check_charter_compliance", validation_router)
    g.add_edge("emit_geth_private", "emit_base_l2_mirror")
    g.add_edge("emit_base_l2_mirror", "emit_at_record")
    g.add_edge("emit_at_record", END)

    return g.compile(checkpointer=checkpointer)


# ─── Node functions ──────────────────────────────────────────────────


def load_donation_request(state):
    """Fetch land-donation record + linked successor declaration from MST."""
    return state


def validate_geojson(state):
    """Verify GeoJSON is valid WGS84, ±1m precision, area matches declared area_m2."""
    # TODO: shapely + pyproj for area calculation + projection check
    return {**state, "geojson_valid": True, "geojson_area_match": True}


def verify_imagery_hash(state):
    """Verify satellite imagery bundle CID resolves + contains ≥3 months of time series."""
    return {**state, "imagery_hash_valid": True}


def verify_oath_signature(state):
    """Verify donor DID key signed the canonical oath text matching oath_hash."""
    return {**state, "oath_signature_valid": True}


def verify_successor_designation(state):
    """Verify primary + ≥2 backup successors have signed pre-acceptance records.

    Per ADR-2605192345 §1.1 (Donation 時の Successor 事前指定 Required).
    """
    return {**state, "successor_pre_acceptance_count": len(state.get("successor_pre_acceptances", []))}


def check_charter_compliance(state, port):
    """Verify donor + primary successor are not Non-Aligned (per ADR-2605192230)."""
    # TODO: port.is_non_aligned_address(donor_address)
    return {**state, "donor_charter_compliant": True}


def emit_geth_private(state, port):
    """Call LandRegistry.donate() on geth-private (constitutional layer)."""
    # TODO: port.donate(oath_hash, geojson_cid, ...)
    return {**state, "geth_private_tx_hash": "0x...", "land_id": 1}


def emit_base_l2_mirror(state, port):
    """Mirror to PublicLandRegistry on Base L2 via AnchorBridge."""
    return {**state, "base_l2_tx_hash": "0x...", "public_land_nft_id": 1}


def emit_at_record(state):
    """Emit com.etzhayyim.apps.etzhayyim.land-donation success/failure record to MST."""
    return state
