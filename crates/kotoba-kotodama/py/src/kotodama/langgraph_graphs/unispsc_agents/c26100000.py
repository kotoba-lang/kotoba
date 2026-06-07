from typing import TypedDict
from langgraph.graph import StateGraph, END

class PowerSourceState(TypedDict):
    spec_data: dict
    validation_results: dict

def validate_specs(state: PowerSourceState):
    specs = state.get('spec_data', {})
    status = 'PASS' if 'efficiency_rating' in specs and 'safety_certifications' in specs else 'FAIL'
    return {'validation_results': {'status': status}}

def check_compliance(state: PowerSourceState):
    return {'validation_results': {'compliance': 'CLEARED'}}

graph = StateGraph(PowerSourceState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
