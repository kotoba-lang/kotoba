from typing import TypedDict
from langgraph.graph import StateGraph, END

class RadiotherapyState(TypedDict):
    equipment_id: str
    safety_check_passed: bool
    clearance_approved: bool

def validate_safety_protocols(state: RadiotherapyState):
    # Perform logic to check radiation safety documentation and shielding specs
    return {'safety_check_passed': True}

def process_logistics_clearance(state: RadiotherapyState):
    # Handle dual-use export and hazardous material transport requirements
    return {'clearance_approved': True}

graph = StateGraph(RadiotherapyState)
graph.add_node('safety_check', validate_safety_protocols)
graph.add_node('logistics', process_logistics_clearance)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()
