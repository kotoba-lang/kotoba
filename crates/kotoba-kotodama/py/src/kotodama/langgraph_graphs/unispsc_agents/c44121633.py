from typing import TypedDict
from langgraph.graph import StateGraph, END

class StampDispenserState(TypedDict):
    model_number: str
    material_check: bool
    is_compliant: bool

def validate_materials(state: StampDispenserState):
    # Business logic for material quality inspection
    return {'material_check': True}

def check_postal_compliance(state: StampDispenserState):
    # Business logic for standard compatibility
    return {'is_compliant': True}

graph = StateGraph(StampDispenserState)
graph.add_node('material', validate_materials)
graph.add_node('compliance', check_postal_compliance)
graph.set_entry_point('material')
graph.add_edge('material', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
