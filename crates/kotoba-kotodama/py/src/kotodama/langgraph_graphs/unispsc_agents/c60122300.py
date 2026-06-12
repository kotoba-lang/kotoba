from typing import TypedDict
from langgraph.graph import StateGraph, END

class CraftSupplyGraph(TypedDict):
    material_type: str
    quality_check: bool
    compliant: bool

def validate_material(state: CraftSupplyGraph):
    print(f'Validating material: {state.get('material_type')}')
    return {'quality_check': True, 'compliant': True}

graph = StateGraph(CraftSupplyGraph)
graph.add_node('validate', validate_material)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
