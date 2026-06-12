from typing import TypedDict
from langgraph.graph import StateGraph, END

class LaundryState(TypedDict):
    specs: dict
    approved: bool
    validation_log: list

def validate_specs(state: LaundryState):
    log = []
    specs = state.get('specs', {})
    if specs.get('energy_efficiency_rating') not in ['A', 'A+', 'A++']:
        log.append('Low energy efficiency detected.')
    return {'validation_log': log, 'approved': len(log) == 0}

graph = StateGraph(LaundryState)
graph.add_node('validation', validate_specs)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
