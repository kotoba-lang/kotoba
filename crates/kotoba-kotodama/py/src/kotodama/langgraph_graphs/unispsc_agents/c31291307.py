from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    material: str
    specs: dict
    approved: bool

def validate_lead_specs(state: ExtrusionState):
    # Validate lead content and environmental safety
    if state.get('specs', {}).get('lead_purity_percentage', 0) > 99.0:
        return {'approved': True}
    return {'approved': False}

def safety_protocol(state: ExtrusionState):
    # Protocol for handling hazardous lead extrusions
    print('Logging hazardous material handling requirements...')
    return {}

graph = StateGraph(ExtrusionState)
graph.add_node('validate', validate_lead_specs)
graph.add_node('safety', safety_protocol)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
