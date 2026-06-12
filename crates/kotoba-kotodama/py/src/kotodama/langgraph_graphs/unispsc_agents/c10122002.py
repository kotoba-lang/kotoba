# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10122002 — Commodity (segment 10).
Bespoke implementation for live animal commodity trading and valuation logic.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10122002"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10122002"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Live Animal Commodities
    specie_type: str
    trade_volume: float
    valuation_per_unit: float
    origin_region: str
    verified_inventory: bool


def inventory_lookup(state: State) -> dict[str, Any]:
    """Verify inventory availability for the requested live animal commodity."""
    inp = state.get("input") or {}
    specie = inp.get("specie", "unspecified")
    volume = float(inp.get("volume", 0.0))
    region = inp.get("region", "global")

    return {
        "log": [f"{UNISPSC_CODE}:inventory_lookup -> {specie} in {region}"],
        "specie_type": specie,
        "trade_volume": volume,
        "origin_region": region,
        "verified_inventory": volume > 0,
    }


def valuation_engine(state: State) -> dict[str, Any]:
    """Calculate market value based on specie and volume."""
    specie = state.get("specie_type", "unspecified")
    # Mock market prices per unit (head of livestock)
    prices = {
        "bovine": 1200.0,
        "porcine": 150.0,
        "ovine": 200.0,
        "equine": 3500.0,
    }
    unit_price = prices.get(specie.lower(), 100.0)

    return {
        "log": [f"{UNISPSC_CODE}:valuation_engine -> price={unit_price}"],
        "valuation_per_unit": unit_price,
    }


def settlement_emit(state: State) -> dict[str, Any]:
    """Prepare the final settlement result for the commodity trade."""
    volume = state.get("trade_volume", 0.0)
    price = state.get("valuation_per_unit", 0.0)
    total_value = volume * price

    return {
        "log": [f"{UNISPSC_CODE}:settlement_emit -> total={total_value}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specie": state.get("specie_type"),
            "total_valuation": total_value,
            "status": "cleared" if state.get("verified_inventory") else "rejected",
        },
    }


_g = StateGraph(State)
_g.add_node("inventory_lookup", inventory_lookup)
_g.add_node("valuation_engine", valuation_engine)
_g.add_node("settlement_emit", settlement_emit)

_g.add_edge(START, "inventory_lookup")
_g.add_edge("inventory_lookup", "valuation_engine")
_g.add_edge("valuation_engine", "settlement_emit")
_g.add_edge("settlement_emit", END)

graph = _g.compile()
