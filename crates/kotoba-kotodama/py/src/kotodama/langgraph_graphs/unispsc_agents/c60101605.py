from langgraph.graph import StateGraph, END
from typing import TypedDict

class RibbonState(TypedDict):
    spec: dict
    approved: bool

def validate_material(state: RibbonState):
    material = state.get('spec', {}).get('material')
    return {'approved': material in ['Silk', 'Satin', 'Polyester']}

def finalize_order(state: RibbonState):
    print('Ribbon procurement specification validated successfully.')
    return {}

graph = StateGraph(RibbonState)
graph.add_node('validate', validate_material)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')

graph = graph.compile()
