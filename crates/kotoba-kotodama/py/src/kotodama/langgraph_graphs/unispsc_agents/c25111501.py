from typing import TypedDict
from langgraph.graph import StateGraph, END

class TrawlerState(TypedDict):
    vessel_id: str
    specs: dict
    validation_status: bool

def validate_vessel(state: TrawlerState):
    specs = state.get('specs', {})
    is_valid = specs.get('length', 0) > 0 and 'registry_number' in specs
    return {'validation_status': is_valid}

def route_by_compliance(state: TrawlerState):
    if state['validation_status']:
        return 'final'
    return 'manual_review'

graph = StateGraph(TrawlerState)
graph.add_node('validate', validate_vessel)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
