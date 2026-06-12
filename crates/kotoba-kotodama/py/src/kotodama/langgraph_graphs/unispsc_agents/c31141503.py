from typing import TypedDict
from langgraph.graph import StateGraph, END

class GlassState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_optical_specs(state: GlassState):
    # Simulate CAD/Spec validation for glass molding
    specs = state.get('spec_data', {})
    state['validation_passed'] = 'Refractive Index' in specs and 'Tolerance' in specs
    return state

def manufacturing_workflow(state: GlassState):
    # Workflow step for molding process
    print('Initiating glass injection molding verification...')
    return state

graph = StateGraph(GlassState)
graph.add_node('validate', validate_optical_specs)
graph.add_node('molding', manufacturing_workflow)
graph.add_edge('validate', 'molding')
graph.add_edge('molding', END)
graph.set_entry_point('validate')
graph = graph.compile()
