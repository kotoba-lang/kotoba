from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_content: str
    approval_status: bool
    compliance_checks: List[str]

def validate_education_content(state: ProcurementState):
    content = state.get('material_content', '')
    checks = ['Standard Compliance']
    if len(content) > 10:
        checks.append('Content Depth Sufficient')
    return {'compliance_checks': checks}

def finalize_procurement(state: ProcurementState):
    return {'approval_status': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_education_content)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
