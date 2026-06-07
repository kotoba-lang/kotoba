from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoilState(TypedDict):
    material_grade: str
    spec_check: bool
    approved: bool

def validate_specs(state: CoilState):
    # Simulate validation logic for industrial coil procurement
    is_compliant = state.get('material_grade') in ['SS400', 'SPCC']
    return {'spec_check': is_compliant, 'approved': is_compliant}

graph = StateGraph(CoilState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
