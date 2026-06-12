from typing import TypedDict
from langgraph.graph import StateGraph, END

class InconelState(TypedDict):
    material_spec: str
    integrity_report: str
    compliance_validated: bool

def validate_material(state: InconelState):
    print('Validating Inconel grade and bonding specs')
    return {'compliance_validated': True}

def conduct_ndt(state: InconelState):
    print('Conducting ultrasonic non-destructive testing on bond interface')
    return {'integrity_report': 'Passed'}

graph = StateGraph(InconelState)
graph.add_node('validate', validate_material)
graph.add_node('ndt', conduct_ndt)
graph.set_entry_point('validate')
graph.add_edge('validate', 'ndt')
graph.add_edge('ndt', END)
graph = graph.compile()
