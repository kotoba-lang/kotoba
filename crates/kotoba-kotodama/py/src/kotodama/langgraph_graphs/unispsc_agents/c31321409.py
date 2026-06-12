from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    material_grade: str
    welding_qa_passed: bool
    mtl_cert_validated: bool

def validate_specs(state: AssemblyState):
    state['welding_qa_passed'] = state.get('material_grade') in ['304', '316L']
    return state

def check_certification(state: AssemblyState):
    state['mtl_cert_validated'] = state.get('welding_qa_passed', False)
    return state

graph = StateGraph(AssemblyState)
graph.add_node('validate', validate_specs)
graph.add_node('certify', check_certification)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()
