from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WatercraftState(TypedDict):
    vessel_id: str
    specifications: dict
    compliance_cleared: bool

def validate_vessel_specs(state: WatercraftState):
    specs = state.get('specifications', {})
    required = ['hull_material', 'engine_power']
    is_valid = all(key in specs for key in required)
    return {'compliance_cleared': is_valid}

def final_approval(state: WatercraftState):
    return {'compliance_cleared': True}

graph = StateGraph(WatercraftState)
graph.add_node('validate', validate_vessel_specs)
graph.add_node('approve', final_approval)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
