from typing import TypedDict
from langgraph.graph import StateGraph, END

class CannulaState(TypedDict):
    part_number: str
    is_sterile: bool
    compliance_check: bool
    approved: bool

def validate_certification(state: CannulaState):
    # Simulate QC logic for medical supplies
    state['compliance_check'] = state.get('is_sterile', False)
    return {'compliance_check': state['compliance_check']}

def finalize_procurement(state: CannulaState):
    state['approved'] = state['compliance_check']
    return {'approved': state['approved']}

graph = StateGraph(CannulaState)
graph.add_node('validate', validate_certification)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
