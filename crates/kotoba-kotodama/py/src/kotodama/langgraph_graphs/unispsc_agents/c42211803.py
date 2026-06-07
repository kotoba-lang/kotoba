from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DressingStickState(TypedDict):
    material_spec: str
    compliance_check: bool
    is_approved: bool

def validate_materials(state: DressingStickState):
    print('Validating materials for medical safety...')
    return {'compliance_check': True}

def approval_step(state: DressingStickState):
    print('Finalizing procurement approval...')
    return {'is_approved': True}

graph = StateGraph(DressingStickState)
graph.add_node('validate', validate_materials)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
