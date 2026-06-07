from typing import TypedDict
from langgraph.graph import StateGraph, END

class AutopsyToolState(TypedDict):
    tool_id: str
    material_compliance: bool
    sterilization_validated: bool
    approved: bool

def validate_material(state: AutopsyToolState):
    state['material_compliance'] = True
    return state

def check_sterilization(state: AutopsyToolState):
    state['sterilization_validated'] = True
    return state

def finalize_check(state: AutopsyToolState):
    state['approved'] = state.get('material_compliance') and state.get('sterilization_validated')
    return state

graph_builder = StateGraph(AutopsyToolState)
graph_builder.add_node('validate_material', validate_material)
graph_builder.add_node('check_sterilization', check_sterilization)
graph_builder.add_node('finalize', finalize_check)
graph_builder.set_entry_point('validate_material')
graph_builder.add_edge('validate_material', 'check_sterilization')
graph_builder.add_edge('check_sterilization', 'finalize')
graph_builder.add_edge('finalize', END)
graph = graph_builder.compile()
