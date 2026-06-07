# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11151710"
UNISPSC_TITLE = "Tungsten"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11151710"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Tungsten (Ore/Metal)
    ore_purity_pct: float
    is_concentrate: bool
    refining_stage: str
    impurities_detected: list[str]

def assay_ore(state: State) -> dict[str, Any]:
    """Inspects the incoming material payload for tungsten content."""
    inp = state.get("input") or {}
    purity = inp.get("purity", 0.0)

    # Identify common tungsten impurities if purity is low
    impurities = []
    if purity < 0.75:
        impurities = ["Molybdenum", "Tin", "Copper"]

    return {
        "log": [f"{UNISPSC_CODE}:assay_ore"],
        "ore_purity_pct": purity,
        "impurities_detected": impurities,
        "refining_stage": "Raw Ore"
    }

def refine_to_apt(state: State) -> dict[str, Any]:
    """Simulates chemical processing into Ammonium Paratungstate (APT)."""
    current_purity = state.get("ore_purity_pct", 0.0)

    # If the material is already pure, skip heavy refining logic
    new_purity = min(0.999, current_purity + 0.25)

    return {
        "log": [f"{UNISPSC_CODE}:refine_to_apt"],
        "ore_purity_pct": new_purity,
        "is_concentrate": True,
        "refining_stage": "APT Intermediate"
    }

def certify_metal(state: State) -> dict[str, Any]:
    """Generates the final certificate for the Tungsten batch."""
    purity = state.get("ore_purity_pct", 0.0)
    stage = state.get("refining_stage", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:certify_metal"],
        "result": {
            "actor": UNISPSC_DID,
            "commodity": UNISPSC_TITLE,
            "purity_level": f"{purity * 100:.2f}%",
            "certification_status": "Passed" if purity > 0.9 else "Pending",
            "metadata": {
                "segment": UNISPSC_SEGMENT,
                "final_stage": stage,
                "impurities": state.get("impurities_detected", [])
            }
        }
    }

_g = StateGraph(State)

_g.add_node("assay", assay_ore)
_g.add_node("refine", refine_to_apt)
_g.add_node("certify", certify_metal)

_g.add_edge(START, "assay")
_g.add_edge("assay", "refine")
_g.add_edge("refine", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
