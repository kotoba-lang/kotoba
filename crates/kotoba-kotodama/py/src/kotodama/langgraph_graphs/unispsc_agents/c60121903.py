from typing import TypedDict
from langgraph.graph import StateGraph, END

class CraftFurState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_fur_specs(state: CraftFurState):
    specs = state.get('spec_data', {})
    required = ['fiber_type', 'flame_retardant']
    is_compliant = all(k in specs for k in required)
    return {'is_compliant': is_compliant}

def process_procurement(state: CraftFurState):
    return state

graph = StateGraph(CraftFurState)
graph.add_node('validate', validate_fur_specs)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
