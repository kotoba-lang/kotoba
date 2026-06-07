from typing import TypedDict
from langgraph.graph import StateGraph, END

class RockerArmState(TypedDict):
    part_number: str
    material_certified: bool
    tolerance_check: bool
    approved: bool

def validate_specs(state: RockerArmState):
    state['material_certified'] = True
    state['tolerance_check'] = True
    return {'approved': True}

graph = StateGraph(RockerArmState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
