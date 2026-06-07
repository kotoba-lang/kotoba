from typing import TypedDict
from langgraph.graph import StateGraph, END

class EnemaProcurementState(TypedDict):
    product_id: str
    sterile_cert: bool
    compliant: bool

def validate_medical_compliance(state: EnemaProcurementState):
    state['compliant'] = state.get('sterile_cert', False)
    return state

builder = StateGraph(EnemaProcurementState)
builder.add_node('validate', validate_medical_compliance)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
