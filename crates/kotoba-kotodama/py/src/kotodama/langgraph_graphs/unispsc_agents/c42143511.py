from typing import TypedDict
from langgraph.graph import StateGraph, END

class CerumenToolState(TypedDict):
    part_number: str
    material_certified: bool
    sterilization_ok: bool
    qc_passed: bool

def validate_materials(state: CerumenToolState):
    state['material_certified'] = True
    return {'material_certified': True}

def verify_sterility(state: CerumenToolState):
    state['sterilization_ok'] = True
    return {'sterilization_ok': True}

def final_qc(state: CerumenToolState):
    state['qc_passed'] = state['material_certified'] and state['sterilization_ok']
    return {'qc_passed': state['qc_passed']}

graph = StateGraph(CerumenToolState)
graph.add_node('validate', validate_materials)
graph.add_node('sterility', verify_sterility)
graph.add_node('qc', final_qc)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', 'qc')
graph.add_edge('qc', END)
graph = graph.compile()
