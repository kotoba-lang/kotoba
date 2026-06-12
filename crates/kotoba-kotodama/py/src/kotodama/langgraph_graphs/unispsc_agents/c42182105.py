from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    is_sterile: bool
    compliance_checked: bool

def validate_medical_grade(state: ProcurementState):
    # Business logic for stethoscope cover validation
    state['compliance_checked'] = True if state.get('is_sterile') else False
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_medical_grade)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
