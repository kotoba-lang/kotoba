from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class UroPressureState(TypedDict):
    equipment_id: str
    calibrated: bool
    sterility_confirmed: bool
    compliance_docs: List[str]

def validate_specs(state: UroPressureState):
    # Simulate CAD/spec hardware validation logic
    state['calibrated'] = True
    return state

def check_compliance(state: UroPressureState):
    state['compliance_docs'] = ['ISO13485', 'IEC60601']
    state['sterility_confirmed'] = True
    return state

graph = StateGraph(UroPressureState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
