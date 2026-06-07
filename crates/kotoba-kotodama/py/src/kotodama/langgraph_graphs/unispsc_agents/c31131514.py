from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    material_spec: dict
    inspection_report: dict
    is_approved: bool

def validate_material(state: ForgingState):
    print('Validating chemical composition for tin alloy...')
    return {'is_approved': True}

def perform_dimensional_check(state: ForgingState):
    print('Executing dimensional tolerance check for open die forging...')
    return {'is_approved': True}

graph = StateGraph(ForgingState)
graph.add_node('validate', validate_material)
graph.add_node('dimensional_check', perform_dimensional_check)
graph.add_edge('validate', 'dimensional_check')
graph.add_edge('dimensional_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
