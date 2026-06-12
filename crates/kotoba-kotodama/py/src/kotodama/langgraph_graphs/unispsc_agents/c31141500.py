from typing import TypedDict
from langgraph.graph import StateGraph, END

class InjectionState(TypedDict):
    part_specs: dict
    validation_results: list
    is_approved: bool

def validate_geometry(state: InjectionState):
    # Simulate CAD dimension checking
    return {'validation_results': ['Geometry Check: Passed']}

def material_compliance_check(state: InjectionState):
    # Simulate material property verification
    return {'validation_results': state['validation_results'] + ['Material Check: Passed']}

graph = StateGraph(InjectionState)
graph.add_node('geometry', validate_geometry)
graph.add_node('material', material_compliance_check)
graph.add_edge('geometry', 'material')
graph.add_edge('material', END)
graph.set_entry_point('geometry')
graph = graph.compile()
