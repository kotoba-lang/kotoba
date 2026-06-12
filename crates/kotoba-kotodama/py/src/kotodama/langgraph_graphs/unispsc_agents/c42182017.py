from typing import TypedDict
from langgraph.graph import StateGraph, END

class SpeculaState(TypedDict):
    material: str
    is_sterile: bool
    compatibility_check: bool

def validate_specs(state: SpeculaState) -> SpeculaState:
    if not state.get('material'):
        state['material'] = 'medical_grade_polypropylene'
    state['compatibility_check'] = True
    return state

def check_compliance(state: SpeculaState) -> str:
    return 'VALID' if state['compatibility_check'] else 'FAIL'

graph = StateGraph(SpeculaState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
