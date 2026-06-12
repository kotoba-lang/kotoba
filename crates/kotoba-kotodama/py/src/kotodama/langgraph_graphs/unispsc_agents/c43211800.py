from typing import TypedDict
from langgraph.graph import StateGraph, END

class DataInputAccessoryState(TypedDict):
    accessory_type: str
    material_compliance: bool
    ergonomic_standard: bool
    approved: bool

def validate_materials(state: DataInputAccessoryState) -> DataInputAccessoryState:
    state['material_compliance'] = True
    return state

def check_ergonomics(state: DataInputAccessoryState) -> DataInputAccessoryState:
    state['ergonomic_standard'] = True
    state['approved'] = state['material_compliance'] and state['ergonomic_standard']
    return state

graph = StateGraph(DataInputAccessoryState)
graph.add_node('ValidateMaterials', validate_materials)
graph.add_node('CheckErgonomics', check_ergonomics)
graph.set_entry_point('ValidateMaterials')
graph.add_edge('ValidateMaterials', 'CheckErgonomics')
graph.add_edge('CheckErgonomics', END)
graph = graph.compile()
