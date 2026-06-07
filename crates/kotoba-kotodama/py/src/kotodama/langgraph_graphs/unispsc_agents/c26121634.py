from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CableState(TypedDict):
    specs: dict
    validation_passed: bool
    error_logs: List[str]

def validate_copper_spec(state: CableState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('purity', 0) < 99.9:
        errors.append('Copper purity below standard.')
    return {'validation_passed': len(errors) == 0, 'error_logs': errors}

graph = StateGraph(CableState)
graph.add_node('validate', validate_copper_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
