from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FarmState(TypedDict):
    material_id: str
    safety_clearance: bool
    chemical_data: dict
    approved: bool

def validate_material(state: FarmState):
    # Simulate hazard and chemical compliance check
    chem = state.get('chemical_data', {})
    is_safe = chem.get('toxicity_level', 10) < 5
    return {'safety_clearance': is_safe}

def approval_check(state: FarmState):
    return 'approved' if state['safety_clearance'] else 'rejected'

graph = StateGraph(FarmState)
graph.add_node('validate', validate_material)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
