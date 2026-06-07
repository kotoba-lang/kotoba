from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalSpecState(TypedDict):
    material_compliance: bool
    sterilization_validated: bool
    final_approval: bool

def validate_material(state: SurgicalSpecState):
    state['material_compliance'] = True
    return state

def validate_sterilization(state: SurgicalSpecState):
    state['sterilization_validated'] = True
    return state

graph = StateGraph(SurgicalSpecState)
graph.add_node('material', validate_material)
graph.add_node('sterilization', validate_sterilization)
graph.set_entry_point('material')
graph.add_edge('material', 'sterilization')
graph.add_edge('sterilization', END)
graph = graph.compile()
