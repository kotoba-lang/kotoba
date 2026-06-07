from typing import TypedDict
from langgraph.graph import StateGraph, END

class FuserState(TypedDict):
    model_number: str
    compatibility_check: bool
    is_refurbished: bool

def validate_model(state: FuserState):
    print(f'Validating model: {state.get('model_number')}')
    return {'compatibility_check': True}

def check_quality_standards(state: FuserState):
    print('Verifying safety certifications...')
    return {'is_refurbished': False}

graph = StateGraph(FuserState)
graph.add_node('validate', validate_model)
graph.add_node('certify', check_quality_standards)
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph.set_entry_point('validate')
graph = graph.compile()
