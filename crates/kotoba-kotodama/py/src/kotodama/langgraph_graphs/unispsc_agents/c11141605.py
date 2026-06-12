from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    safety_check_passed: bool
    quality_score: float
    processing_steps: Annotated[Sequence[str], operator.add]

def validate_material(state: ChemicalState):
    # Simulate high-precision chemical validation
    return {"safety_check_passed": True, "quality_score": 0.98}

def process_chemical(state: ChemicalState):
    return {"processing_steps": ["structural_analysis", "thermal_stability_test"]}

graph = StateGraph(ChemicalState)
graph.add_node("validate", validate_material)
graph.add_node("process", process_chemical)
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph.set_entry_point("validate")
graph = graph.compile()
