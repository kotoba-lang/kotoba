from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AssemblyState(TypedDict):
    assembly_id: str
    welding_parameters: dict
    is_validated: bool
    compliance_tags: List[str]

def validate_sonic_weld(state: AssemblyState) -> AssemblyState:
    params = state.get('welding_parameters', {})
    # Logic for validating ultrasonic weld pressure and frequency
    state['is_validated'] = all(k in params for k in ['frequency_khz', 'pressure_mpa'])
    return state

def check_compliance(state: AssemblyState) -> AssemblyState:
    state['compliance_tags'] = ['ISO-9001', 'Export-Checked']
    return state

graph = StateGraph(AssemblyState)
graph.add_node('validate', validate_sonic_weld)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')

graph = graph.compile()
