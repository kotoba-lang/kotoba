from langgraph.graph import StateGraph, END
from typing import TypedDict, List
class DefenseProcurementState(TypedDict):
    item_id: str
    compliance_docs: List[str]
    export_cleared: bool
    approved: bool
def validate_compliance(state: DefenseProcurementState):
    state['compliance_docs'] = ['ISO9001', 'ITAR_Compliance']
    return {'compliance_docs': state['compliance_docs']}
def check_export_controls(state: DefenseProcurementState):
    state['export_cleared'] = True
    return {'export_cleared': state['export_cleared']}
def approve_procurement(state: DefenseProcurementState):
    state['approved'] = state['export_cleared']
    return {'approved': state['approved']}
graph = StateGraph(DefenseProcurementState)
graph.add_node('validate', validate_compliance)
graph.add_node('export', check_export_controls)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
