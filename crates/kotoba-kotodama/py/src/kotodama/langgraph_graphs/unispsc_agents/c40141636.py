from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ValveKitState(TypedDict):
    kit_id: str
    specifications: dict
    validation_results: List[str]
    approved: bool

def validate_specs(state: ValveKitState) -> ValveKitState:
    specs = state.get('specifications', {})
    results = []
    if 'pressure_rating' not in specs:
        results.append('Missing mandatory pressure rating')
    state['validation_results'] = results
    state['approved'] = len(results) == 0
    return state

def check_compliance(state: ValveKitState) -> ValveKitState:
    if state.get('approved', False):
        print('Checking material compliance with industry standards...')
    return state

graph = StateGraph(ValveKitState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
