from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MiningPartsState(TypedDict):
    part_specs: dict
    validation_logs: Annotated[Sequence[str], add_messages]
    is_compliant: bool

def validate_material_specs(state: MiningPartsState):
    specs = state.get("part_specs", {})
    is_compliant = specs.get("tensile_strength", 0) > 500 and specs.get("wear_resistant", True)
    return {"is_compliant": is_compliant, "validation_logs": [f"Material check: {is_compliant}"]}

def structural_analysis_node(state: MiningPartsState):
    if state["is_compliant"]:
        return {"validation_logs": ["Structural integrity verified for mining stress."]}
    return {"validation_logs": ["Structural integrity failed - requires rework."]}

graph = StateGraph(MiningPartsState)
graph.add_node("validate_material", validate_material_specs)
graph.add_node("analyze_structure", structural_analysis_node)
graph.add_edge("validate_material", "analyze_structure")
graph.add_edge("analyze_structure", END)
graph.set_entry_point("validate_material")
graph = graph.compile()
