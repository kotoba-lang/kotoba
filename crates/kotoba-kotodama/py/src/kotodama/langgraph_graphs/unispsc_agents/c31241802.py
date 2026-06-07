from typing import TypedDict
from langgraph.graph import StateGraph, END

class FilterSpec(TypedDict):
    material: str
    transmission_range: str
    optical_density: float
    compliance_check: bool

def validate_specs(state: FilterSpec) -> FilterSpec:
    if not state.get('material'):
        state['compliance_check'] = False
    else:
        state['compliance_check'] = True
    return state

def check_export_control(state: FilterSpec) -> FilterSpec:
    state['compliance_check'] = state['compliance_check'] and (state['optical_density'] < 5.0)
    return state

graph = StateGraph(FilterSpec)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export_control)
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
