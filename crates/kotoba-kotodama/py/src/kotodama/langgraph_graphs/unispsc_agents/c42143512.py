from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class EarWickState(TypedDict):
    sterility_cert: bool
    biocompatibility_report: str
    batch_number: str

def validate_medical_grade(state: EarWickState) -> EarWickState:
    if not state.get('sterility_cert'):
        raise ValueError('Sterility certification required for Class 42143512')
    return state

def check_compliance(state: EarWickState) -> str:
    return 'APPROVED' if state.get('biocompatibility_report') else 'REJECTED'

graph = StateGraph(EarWickState)
graph.add_node('validate', validate_medical_grade)
graph.add_node('check', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'check')
graph.add_edge('check', END)
graph = graph.compile()
