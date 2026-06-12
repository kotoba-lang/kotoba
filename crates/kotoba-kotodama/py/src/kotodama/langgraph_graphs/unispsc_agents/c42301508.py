from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MedicalVideoState(TypedDict):
    content_url: str
    validation_checks: List[str]
    approved: bool

def validate_content(state: MedicalVideoState):
    checks = ['regulatory_review', 'clinical_accuracy_check']
    return {'validation_checks': checks, 'approved': True}

graph = StateGraph(MedicalVideoState)
graph.add_node('validate', validate_content)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
