from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpState(TypedDict):
    specs: dict
    approved: bool

def validate_specs(state: PumpState):
    # Validate vacuum requirements
    p = state.get('specs', {})
    is_valid = p.get('ultimate_pressure', 10.0) < 100.0
    return {'approved': is_valid}

def check_compliance(state: PumpState):
    # Check dual-use export compliance
    return {'approved': state.get('approved', False)}

graph = StateGraph(PumpState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
