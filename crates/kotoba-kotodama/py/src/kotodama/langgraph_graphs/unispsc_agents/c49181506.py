from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    approved: bool

def validate_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    # Logic to validate electrical specs for blower units
    is_valid = 'blower_voltage_spec' in specs and 'safety_certification_ce_ul' in specs
    return {'approved': is_valid}

def build_graph():
    graph = StateGraph(ProcurementState)
    graph.add_node('validate', validate_specs)
    graph.set_entry_point('validate')
    graph.add_edge('validate', END)
    return graph.compile()

graph = build_graph()
