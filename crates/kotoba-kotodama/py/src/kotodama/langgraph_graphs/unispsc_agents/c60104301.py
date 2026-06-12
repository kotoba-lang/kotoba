from typing import TypedDict
from langgraph.graph import StateGraph, END

class AstronomyModelState(TypedDict):
    model_type: str
    material_compliance: bool
    is_complex_assembly: bool

def validate_model_spec(state: AstronomyModelState):
    print(f'Validating specs for: {state.get('model_type')}')
    return {'material_compliance': True}

def check_assembly_complexity(state: AstronomyModelState):
    return {'is_complex_assembly': True}

graph = StateGraph(AstronomyModelState)
graph.add_node('validate', validate_model_spec)
graph.add_node('complexity_check', check_assembly_complexity)
graph.set_entry_point('validate')
graph.add_edge('validate', 'complexity_check')
graph.add_edge('complexity_check', END)
graph = graph.compile()
