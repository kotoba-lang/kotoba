from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    material_type: str
    validation_status: bool

def validate_content(state: State):
    is_valid = state.get('material_type') in ['Book', 'E-book', 'Course']
    return {'validation_status': is_valid}

def process_procurement(state: State):
    print(f'Processing procurement for {state.get('material_type')}')
    return {'validation_status': True}

graph = StateGraph(State)
graph.add_node('validate', validate_content)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
