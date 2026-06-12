from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CafeteriaState(TypedDict):
    facility_specs: dict
    compliance_checks: List[str]
    status: str

def validate_equipment(state: CafeteriaState):
    specs = state.get('facility_specs', {})
    checks = ['FSSAI_PASS'] if specs.get('has_kitchen') else []
    return {'compliance_checks': checks, 'status': 'VALIDATED'}

def finalize_procurement(state: CafeteriaState):
    return {'status': 'READY_FOR_TENDER'}

graph = StateGraph(CafeteriaState)
graph.add_node('validate', validate_equipment)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
