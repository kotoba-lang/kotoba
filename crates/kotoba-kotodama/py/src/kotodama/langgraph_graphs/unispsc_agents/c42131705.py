from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_id: str
    specifications: dict
    is_compliant: bool
    validation_log: List[str]

def validate_medical_standards(state: ProcurementState):
    specs = state.get('specifications', {})
    checks = ['compression_class', 'biocompatibility_iso_10993']
    is_valid = all(key in specs for key in checks)
    return {'is_compliant': is_valid, 'validation_log': ['Standard compliance check completed']}

def route_by_compliance(state: ProcurementState):
    return 'compliant' if state['is_compliant'] else 'reject'

graph = StateGraph(ProcurementState)
graph.add_node('validator', validate_medical_standards)
graph.set_entry_point('validator')
graph.add_conditional_edges('validator', route_by_compliance, {'compliant': END, 'reject': END})
graph = graph.compile()
