from typing import TypedDict
from langgraph.graph import StateGraph, END

class PhonicsState(TypedDict):
    book_title: str
    curriculum_level: str
    spec_valid: bool

def validate_curriculum(state: PhonicsState):
    print(f'Validating curriculum for: {state.get('book_title')}')
    return {'spec_valid': True}

def finalize_order(state: PhonicsState):
    print('Finalizing order for phonics resources...')
    return {'spec_valid': True}

graph = StateGraph(PhonicsState)
graph.add_node('validate', validate_curriculum)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
