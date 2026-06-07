from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class PolymerProcessState(TypedDict):
    material_id: str
    purity_check: bool
    thermal_validation: bool
    compliance_status: list[str]

def validate_material_purity(state: PolymerProcessState) -> PolymerProcessState:
    # Specialized logic for polymer purity validation
    state['purity_check'] = True
    return state

def check_compliance(state: PolymerProcessState) -> PolymerProcessState:
    # Check against dual-use and safety regulations
    state['compliance_status'] = ['REACH_OK', 'RoHS_OK']
    return state

graph = StateGraph(PolymerProcessState)
graph.add_node('validate', validate_material_purity)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
