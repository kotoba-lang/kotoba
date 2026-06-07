from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class InconelState(TypedDict):
    assembly_id: str
    material_compliance: bool
    ndt_results: List[str]
    approved: bool

def validate_material(state: InconelState):
    state['material_compliance'] = True
    return state

def run_ndt(state: InconelState):
    state['ndt_results'] = ['X-ray:Pass', 'Ultrasonic:Pass']
    state['approved'] = True
    return state

graph = StateGraph(InconelState)
graph.add_node('validate_material', validate_material)
graph.add_node('run_ndt', run_ndt)
graph.add_edge('validate_material', 'run_ndt')
graph.add_edge('run_ndt', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
