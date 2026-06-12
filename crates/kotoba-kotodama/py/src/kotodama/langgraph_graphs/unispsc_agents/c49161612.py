from typing import TypedDict
from langgraph.graph import StateGraph, END

class TennisSpecState(TypedDict):
    spec_data: dict
    is_validated: bool

def validate_safety_compliance(state: TennisSpecState):
    # Business logic for validating safety compliance of tennis equipment
    specs = state.get('spec_data', {})
    state['is_validated'] = specs.get('compliance_certified', False)
    return state

def check_durability(state: TennisSpecState):
    # Logic to check weather resistance requirements
    return {'is_validated': state['is_validated'] and 'uv_rated' in state['spec_data']}

graph = StateGraph(TennisSpecState)
graph.add_node('safety_check', validate_safety_compliance)
graph.add_node('durability_check', check_durability)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'durability_check')
graph.add_edge('durability_check', END)
graph = graph.compile()
