from typing import TypedDict
from langgraph.graph import StateGraph, END
class EphedrineState(TypedDict):
    quantity: float
    license_valid: bool
    compliance_docs: list
    is_approved: bool
def validate_license(state: EphedrineState):
    return {'license_valid': True if state.get('license_id_number') else False}
def check_compliance(state: EphedrineState):
    return {'is_approved': state['license_valid'] and len(state['compliance_docs']) > 0}
graph = StateGraph(EphedrineState)
graph.add_node('validate', validate_license)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
