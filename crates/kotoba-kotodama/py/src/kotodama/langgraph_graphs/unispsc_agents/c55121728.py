from typing import TypedDict
from langgraph.graph import StateGraph, END

class SignageState(TypedDict):
    spec_data: dict
    is_verified: bool

def validate_materials(state: SignageState):
    print('Validating materials against specifications...')
    material = state.get('spec_data', {}).get('material', '')
    return {'is_verified': material != ''}

graph = StateGraph(SignageState)
graph.add_node('validate', validate_materials)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
