from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DosimetryState(TypedDict):
    equipment_id: str
    calibration_status: bool
    compliance_docs: List[str]
    approved: bool

def validate_calibration(state: DosimetryState):
    state['calibration_status'] = True
    return state

def check_regulations(state: DosimetryState):
    state['approved'] = len(state.get('compliance_docs', [])) > 0
    return state

graph = StateGraph(DosimetryState)
graph.add_node('validate', validate_calibration)
graph.add_node('compliance', check_regulations)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
