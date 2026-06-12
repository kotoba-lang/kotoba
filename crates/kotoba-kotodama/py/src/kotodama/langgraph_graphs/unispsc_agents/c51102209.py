from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    purity_check: bool
    compliance_validated: bool
    batch_number: str

def validate_chemical(state: PharmState) -> PharmState:
    # Logic to verify chemical specifications against USP standards
    state['purity_check'] = True
    return state

def check_compliance(state: PharmState) -> PharmState:
    state['compliance_validated'] = True
    return state

graph = StateGraph(PharmState)
graph.add_node('validate', validate_chemical)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
