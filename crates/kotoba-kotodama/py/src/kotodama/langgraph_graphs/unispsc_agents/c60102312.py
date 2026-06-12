from typing import TypedDict
from langgraph.graph import StateGraph, END

class TextbookState(TypedDict):
    title: str
    isbn: str
    is_verified: bool

def validate_resource(state: TextbookState) -> TextbookState:
    print(f'Validating resource: {state.get('title')}')
    return {'is_verified': len(state.get('isbn', '')) > 10}

def route_verification(state: TextbookState) -> str:
    return 'valid' if state.get('is_verified') else 'invalid'

graph = StateGraph(TextbookState)
graph.add_node('validator', validate_resource)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
