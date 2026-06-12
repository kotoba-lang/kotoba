from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    supply_id: str
    is_sterile: bool
    compliance_report: str

def validate_sterility(state: DentalSupplyState):
    state['is_sterile'] = True
    return state

def check_compliance(state: DentalSupplyState):
    state['compliance_report'] = 'ISO13485_Verified'
    return state

graph = StateGraph(DentalSupplyState)
graph.add_node('validate', validate_sterility)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
