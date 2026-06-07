from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class ControllerState(TypedDict):
    specs: Dict[str, Any]
    validation_results: List[str]
    is_approved: bool

def validate_controller_specs(state: ControllerState):
    specs = state.get('specs', {})
    results = []
    if specs.get('AxisCount', 0) < 1:
        results.append('Invalid axis count')
    return {'validation_results': results}

def decision_node(state: ControllerState):
    return 'approved' if not state.get('validation_results') else 'rejected'

graph = StateGraph(ControllerState)
graph.add_node('validate', validate_controller_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
