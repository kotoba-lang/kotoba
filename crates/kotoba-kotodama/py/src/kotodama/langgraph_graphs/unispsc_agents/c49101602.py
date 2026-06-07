from typing import TypedDict
from langgraph.graph import StateGraph, END

class SouvenirState(TypedDict):
    item_name: str
    compliance_passed: bool
    quality_score: int

def validate_branding(state: SouvenirState) -> SouvenirState:
    print(f'Validating branding for {state.get('item_name')}')
    return {'compliance_passed': True}

def check_quality(state: SouvenirState) -> SouvenirState:
    return {'quality_score': 95}

graph = StateGraph(SouvenirState)
graph.add_node('validate', validate_branding)
graph.add_node('inspect', check_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
