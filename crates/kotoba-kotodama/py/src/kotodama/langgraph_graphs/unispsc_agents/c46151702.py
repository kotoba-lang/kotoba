from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AuditState(TypedDict):
    item_name: str
    material_compliance: bool
    is_forensic_grade: bool

def validate_materials(state: AuditState):
    state['material_compliance'] = True
    return state

def check_certification(state: AuditState):
    state['is_forensic_grade'] = True
    return state

graph = StateGraph(AuditState)
graph.add_node('validate', validate_materials)
graph.add_node('certify', check_certification)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()
