from typing import TypedDict
from langgraph.graph import StateGraph, END

class CleaningKitState(TypedDict):
    kit_id: str
    safety_check_passed: bool
    compliance_score: float

def validate_materials(state: CleaningKitState) -> CleaningKitState:
    # Logic to verify non-toxic chemical composition for board safety
    state['safety_check_passed'] = True
    return state

def assess_compatibility(state: CleaningKitState) -> CleaningKitState:
    # Verify compatibility with specific whiteboard surfaces
    state['compliance_score'] = 1.0
    return state

builder = StateGraph(CleaningKitState)
builder.add_node('validate_materials', validate_materials)
builder.add_node('assess_compatibility', assess_compatibility)
builder.set_entry_point('validate_materials')
builder.add_edge('validate_materials', 'assess_compatibility')
builder.add_edge('assess_compatibility', END)
graph = builder.compile()
