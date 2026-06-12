from typing import TypedDict
from langgraph.graph import StateGraph, END

class SatelliteState(TypedDict):
    spec_data: dict
    validation_status: str

def validate_tech_specs(state: SatelliteState):
    specs = state.get('spec_data', {})
    status = 'PASS' if 'radiation_level' in specs and 'ITAR' in specs else 'FAIL'
    return {'validation_status': status}

def export_review(state: SatelliteState):
    return {'validation_status': 'EXPORT_CLEARED'}

graph = StateGraph(SatelliteState)
graph.add_node('validate', validate_tech_specs)
graph.add_node('export_review', export_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_review')
graph.add_edge('export_review', END)
graph = graph.compile()
